from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import os
import uuid
from typing import Any, Callable

from .artifacts import (
    breadth_open_outputs,
    check_artifacts,
    check_depth_artifacts,
    depth_prerequisite_issues,
    expected_breadth_artifacts,
    expected_depth_artifacts,
    expected_sc_semantic_dedup_artifacts,
    expected_invariants_artifacts,
    expected_inventory_artifacts,
    first_pass_breadth_issues,
    invariants_prerequisite_issues,
    inventory_source_size_issues,
    rescan_prerequisite_issues,
    sc_semantic_dedup_prerequisite_issues,
    validate_phase_artifacts,
    validate_spawn_manifest_schema,
)
from .config import AuditConfig
from .dedup import finalize_sc_semantic_dedup, prepare_sc_semantic_dedup
from .phases import build_phase_prompt, expected_phase_artifacts
from .runner import CodexRunner
from .state import AuditState
from .store import StateStore, utc_now

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    END = "__end__"
    START = "__start__"
    StateGraph = None


SUPPORTED_TARGET_PHASES = {
    "recon",
    "instantiate",
    "breadth",
    "rescan",
    "inventory",
    "invariants",
    "depth",
    "sc_semantic_dedup",
}


def _output_paths(scratchpad: str | Path, phase_name: str) -> dict[str, Path]:
    sp = Path(scratchpad)
    return {
        "prompt_path": sp / f"_lg_{phase_name}_prompt.md",
        "stdout_path": sp / f"_lg_{phase_name}_stdout.log",
        "stderr_path": sp / f"_lg_{phase_name}_stderr.log",
        "events_path": sp / f"_lg_{phase_name}_events.jsonl",
        "last_message_path": sp / f"_lg_{phase_name}_last_message.md",
    }


class _SequentialGraph:
    def __init__(self, nodes: list[Callable[[AuditState], AuditState]]) -> None:
        self._nodes = nodes

    def invoke(self, state: AuditState) -> AuditState:
        current = state
        for node in self._nodes:
            current = node(current)
        return current


def _dedupe_issues(issues: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        if issue in seen:
            continue
        seen.add(issue)
        result.append(issue)
    return result


def _predecessors_for(phase_name: str, mode: str = "core") -> list[str]:
    if phase_name == "recon":
        return []
    if phase_name == "instantiate":
        return ["recon"]
    if phase_name == "breadth":
        return ["recon", "instantiate"]
    if phase_name == "rescan":
        return ["recon", "instantiate", "breadth"]
    if phase_name == "inventory":
        return ["recon", "instantiate", "breadth", "rescan"]
    if phase_name == "invariants":
        return ["recon", "instantiate", "breadth", "rescan", "inventory"]
    if phase_name == "depth":
        predecessors = ["recon", "instantiate", "breadth", "rescan", "inventory"]
        if mode in {"core", "thorough"}:
            predecessors.append("invariants")
        return predecessors
    if phase_name == "sc_semantic_dedup":
        predecessors = ["recon", "instantiate", "breadth", "rescan", "inventory"]
        if mode in {"core", "thorough"}:
            predecessors.append("invariants")
        predecessors.append("depth")
        return predecessors
    raise ValueError(f"unsupported target phase: {phase_name}")


def _direct_predecessor_for(phase_name: str, mode: str = "core") -> str | None:
    predecessors = _predecessors_for(phase_name, mode)
    return predecessors[-1] if predecessors else None


def _mode_gate_error(phase_name: str, mode: str) -> str | None:
    if phase_name == "invariants" and mode == "light":
        return "invariants phase is unavailable in light mode; use core or thorough"
    return None


def _phase_preconditions_met(phase_name: str, state: AuditState) -> bool:
    if state.get("status") != "succeeded":
        return False
    completed = set(state.get("completed_phases", []))
    return all(
        phase in completed
        for phase in _predecessors_for(phase_name, str(state.get("mode", "core")))
    )


@contextmanager
def _run_lock(scratchpad: str | Path):
    scratch = Path(scratchpad)
    scratch.mkdir(parents=True, exist_ok=True)
    lock_path = scratch / "_lg_run.lock"
    lock_fd: int | None = None
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, f"{os.getpid()}\n".encode("utf-8"))
    except FileExistsError as exc:
        raise RuntimeError(f"another plamen_langgraph run is active: {lock_path}") from exc
    try:
        yield
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _make_phase_node(
    phase_name: str,
    runner: Any | None = None,
    timeout_s: int = 3000,
) -> Callable[[AuditState], AuditState]:
    def phase_node(state: AuditState) -> AuditState:
        if phase_name != "recon" and not _phase_preconditions_met(phase_name, state):
            return state

        scratchpad = Path(state["scratchpad"])
        scratchpad.mkdir(parents=True, exist_ok=True)

        store = StateStore(state["db_path"])
        store.init_db()
        store.update_run_status(state["run_id"], "running")

        phase_run_id = f"{state['run_id']}:{phase_name}"
        started_at = utc_now()
        store.create_phase_run(
            phase_run_id,
            state["run_id"],
            phase_name,
            "running",
            started_at,
        )

        paths = _output_paths(scratchpad, phase_name)
        try:
            open_outputs: list[str] | None = None
            expected_artifacts = expected_phase_artifacts(
                phase_name,
                state["pipeline"],
            )
            if phase_name == "breadth":
                expected_artifacts = expected_breadth_artifacts(scratchpad)
                preflight_issues = validate_spawn_manifest_schema(scratchpad)
                if not expected_artifacts:
                    preflight_issues.append(
                        "spawn_manifest.md schema invalid: zero manifest-derived breadth outputs"
                    )
                if preflight_issues:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

                open_outputs = breadth_open_outputs(scratchpad)
                if not open_outputs:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    validation_issues = validate_phase_artifacts(
                        phase_name,
                        scratchpad,
                        artifacts["records"],
                    )
                    if validation_issues:
                        phase_status = "failed"
                        run_status = "failed"
                        error = "; ".join(_dedupe_issues(validation_issues))
                    else:
                        phase_status = "succeeded"
                        run_status = "succeeded"
                        error = None
                    store.update_phase_run(
                        phase_run_id,
                        phase_status,
                        returncode=0,
                        started_at=started_at,
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], run_status)
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = run_status
                    next_state["error"] = error
                    if phase_status == "succeeded":
                        completed = list(next_state.get("completed_phases", []))
                        if phase_name not in completed:
                            completed.append(phase_name)
                        next_state["completed_phases"] = completed
                        next_state["failed_phase"] = None
                    else:
                        next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            if phase_name == "rescan":
                preflight_issues = first_pass_breadth_issues(scratchpad)
                if preflight_issues:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            if phase_name == "inventory":
                expected_artifacts = expected_inventory_artifacts(scratchpad)
                preflight_issues = rescan_prerequisite_issues(scratchpad)
                preflight_issues.extend(inventory_source_size_issues(scratchpad))
                if preflight_issues:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            if phase_name == "invariants":
                expected_artifacts = expected_invariants_artifacts(scratchpad)
                preflight_issues = invariants_prerequisite_issues(scratchpad)
                if preflight_issues:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            if phase_name == "depth":
                expected_artifacts = expected_depth_artifacts(
                    str(state.get("mode", "core"))
                )
                preflight_issues = depth_prerequisite_issues(
                    scratchpad,
                    str(state.get("mode", "core")),
                )
                if preflight_issues:
                    artifacts = check_depth_artifacts(
                        scratchpad,
                        str(state.get("mode", "core")),
                    )
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            if phase_name == "sc_semantic_dedup":
                expected_artifacts = expected_sc_semantic_dedup_artifacts(scratchpad)
                preflight_issues = sc_semantic_dedup_prerequisite_issues(
                    scratchpad,
                    str(state.get("mode", "core")),
                )
                if preflight_issues:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    error = "; ".join(_dedupe_issues(preflight_issues))
                    store.update_phase_run(
                        phase_run_id,
                        "failed",
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], "failed")
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = "failed"
                    next_state["error"] = error
                    next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

                skipped, _skip_reason = prepare_sc_semantic_dedup(scratchpad)
                if skipped:
                    artifacts = check_artifacts(scratchpad, expected_artifacts)
                    store.record_artifacts(
                        state["run_id"],
                        phase_name,
                        artifacts["records"],
                    )
                    validation_issues = validate_phase_artifacts(
                        phase_name,
                        scratchpad,
                        artifacts["records"],
                        mode=str(state.get("mode", "core")),
                    )
                    if validation_issues or not artifacts["ok"]:
                        phase_status = "failed"
                        run_status = "failed"
                        error = "; ".join(
                            _dedupe_issues(
                                [
                                    f"missing {phase_name} artifacts: {name}"
                                    for name in artifacts["missing"]
                                ]
                                + validation_issues
                            )
                        )
                    else:
                        phase_status = "succeeded"
                        run_status = "succeeded"
                        error = None
                    store.update_phase_run(
                        phase_run_id,
                        phase_status,
                        returncode=0,
                        started_at=started_at,
                        finished_at=utc_now(),
                        error=error,
                    )
                    store.update_run_status(state["run_id"], run_status)
                    next_state = dict(state)
                    next_state["current_phase"] = phase_name
                    next_state["status"] = run_status
                    next_state["error"] = error
                    if phase_status == "succeeded":
                        completed = list(next_state.get("completed_phases", []))
                        if phase_name not in completed:
                            completed.append(phase_name)
                        next_state["completed_phases"] = completed
                        next_state["failed_phase"] = None
                    else:
                        next_state["failed_phase"] = phase_name
                    return next_state  # type: ignore[return-value]

            prompt = build_phase_prompt(
                phase_name,
                dict(state),
                open_outputs=open_outputs,
            )
            paths["prompt_path"].write_text(prompt, encoding="utf-8")

            active_runner = runner or CodexRunner()
            result = active_runner.run(
                prompt=prompt,
                project_root=state["project_root"],
                scratchpad=state["scratchpad"],
                output_paths=paths,
                timeout_s=timeout_s,
            )
            result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)

            if phase_name == "breadth":
                expected_artifacts = expected_breadth_artifacts(scratchpad)
            if phase_name == "inventory":
                expected_artifacts = expected_inventory_artifacts(scratchpad)
            if phase_name == "invariants":
                expected_artifacts = expected_invariants_artifacts(scratchpad)
            if phase_name == "depth":
                expected_artifacts = expected_depth_artifacts(
                    str(state.get("mode", "core"))
                )
                artifacts = check_depth_artifacts(
                    scratchpad,
                    str(state.get("mode", "core")),
                )
            elif phase_name == "sc_semantic_dedup":
                expected_artifacts = expected_sc_semantic_dedup_artifacts(scratchpad)
                artifacts = check_artifacts(scratchpad, expected_artifacts)
            else:
                artifacts = check_artifacts(scratchpad, expected_artifacts)
            store.record_artifacts(state["run_id"], phase_name, artifacts["records"])
            validation_issues = validate_phase_artifacts(
                phase_name,
                scratchpad,
                artifacts["records"],
                mode=str(state.get("mode", "core")),
            )
            artifact_issues = _dedupe_issues(
                [f"missing {phase_name} artifacts: {name}" for name in artifacts["missing"]]
                + validation_issues
            )

            timed_out = bool(result_dict.get("timed_out"))
            returncode = result_dict.get("returncode")
            error = result_dict.get("error")
            if (
                phase_name == "sc_semantic_dedup"
                and not timed_out
                and returncode == 0
                and artifacts["ok"]
                and not artifact_issues
            ):
                artifact_issues = _dedupe_issues(
                    artifact_issues + finalize_sc_semantic_dedup(scratchpad)
                )
            if timed_out:
                phase_status = "timeout"
                run_status = "failed"
            elif returncode != 0:
                phase_status = "failed"
                run_status = "failed"
                error = error or f"codex exec returned {returncode}"
            elif not artifacts["ok"] or artifact_issues:
                phase_status = "failed"
                run_status = "failed"
                error = "; ".join(artifact_issues)
            else:
                phase_status = "succeeded"
                run_status = "succeeded"

            store.update_phase_run(
                phase_run_id,
                phase_status,
                returncode=returncode,
                stdout_path=result_dict.get("stdout_path"),
                stderr_path=result_dict.get("stderr_path"),
                events_path=result_dict.get("events_path"),
                output_path=result_dict.get("last_message_path"),
                started_at=result_dict.get("started_at"),
                finished_at=result_dict.get("finished_at"),
                error=error,
            )
            store.update_run_status(state["run_id"], run_status)

            next_state = dict(state)
            next_state["current_phase"] = phase_name
            next_state["status"] = run_status
            next_state["error"] = error
            if phase_status == "succeeded":
                completed = list(next_state.get("completed_phases", []))
                if phase_name not in completed:
                    completed.append(phase_name)
                next_state["completed_phases"] = completed
                next_state["failed_phase"] = None
            else:
                next_state["failed_phase"] = phase_name
            return next_state  # type: ignore[return-value]
        except Exception as exc:
            error = str(exc)
            store.update_phase_run(
                phase_run_id,
                "failed",
                finished_at=utc_now(),
                error=error,
            )
            store.update_run_status(state["run_id"], "failed")
            next_state = dict(state)
            next_state["current_phase"] = phase_name
            next_state["status"] = "failed"
            next_state["error"] = error
            next_state["failed_phase"] = phase_name
            return next_state  # type: ignore[return-value]

    return phase_node


def build_graph(
    runner: Any | None = None,
    timeout_s: int = 3000,
    target_phase: str = "recon",
    mode: str = "core",
) -> Any:
    if target_phase not in SUPPORTED_TARGET_PHASES:
        raise ValueError(f"unsupported target phase: {target_phase}")
    recon_node = _make_phase_node("recon", runner, timeout_s)
    nodes = [("recon", recon_node)]
    tail_phases = {
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
        "sc_semantic_dedup",
    }
    if target_phase in tail_phases:
        nodes.append(("instantiate", _make_phase_node("instantiate", runner, timeout_s)))
    if target_phase in {
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
        "sc_semantic_dedup",
    }:
        nodes.append(("breadth", _make_phase_node("breadth", runner, timeout_s)))
    if target_phase in {"rescan", "inventory", "invariants", "depth", "sc_semantic_dedup"}:
        nodes.append(("rescan", _make_phase_node("rescan", runner, timeout_s)))
    if target_phase in {"inventory", "invariants", "depth", "sc_semantic_dedup"}:
        nodes.append(("inventory", _make_phase_node("inventory", runner, timeout_s)))
    if target_phase == "invariants" or (
        target_phase in {"depth", "sc_semantic_dedup"} and mode in {"core", "thorough"}
    ):
        nodes.append(("invariants", _make_phase_node("invariants", runner, timeout_s)))
    if target_phase in {"depth", "sc_semantic_dedup"}:
        nodes.append(("depth", _make_phase_node("depth", runner, timeout_s)))
    if target_phase == "sc_semantic_dedup":
        nodes.append(
            ("sc_semantic_dedup", _make_phase_node("sc_semantic_dedup", runner, timeout_s))
        )
    if StateGraph is None:
        return _SequentialGraph([node for _name, node in nodes])

    graph = StateGraph(AuditState)
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_edge(START, nodes[0][0])
    for (left, _left_node), (right, _right_node) in zip(nodes, nodes[1:]):
        graph.add_edge(left, right)
    graph.add_edge(nodes[-1][0], END)
    return graph.compile()


def initial_state(
    config: AuditConfig,
    run_id: str | None = None,
    target_phase: str = "recon",
    base_run_id: str | None = None,
    execution_mode: str = "prefix",
    completed_phases: list[str] | None = None,
) -> AuditState:
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "base_run_id": base_run_id,
        "project_root": config.project_root,
        "scratchpad": config.scratchpad,
        "db_path": config.db_path,
        "pipeline": config.pipeline,
        "mode": config.mode,
        "language": config.language,
        "execution_mode": execution_mode,
        "current_phase": target_phase if execution_mode == "single_node" else "recon",
        "target_phase": target_phase,
        "completed_phases": list(completed_phases or []),
        "failed_phase": None,
        "status": "pending",
        "error": None,
    }


def run_graph(
    config: AuditConfig,
    target_phase: str = "recon",
    runner: Any | None = None,
) -> AuditState:
    if target_phase not in SUPPORTED_TARGET_PHASES:
        raise ValueError(f"unsupported target phase: {target_phase}")
    mode_error = _mode_gate_error(target_phase, config.mode)
    if mode_error:
        state = initial_state(config, target_phase=target_phase)
        state["status"] = "failed"
        state["failed_phase"] = target_phase
        state["error"] = mode_error
        return state
    scratchpad = Path(config.scratchpad)
    scratchpad.mkdir(parents=True, exist_ok=True)
    with _run_lock(scratchpad):
        store = StateStore(config.db_path)
        store.init_db()

        state = initial_state(config, target_phase=target_phase)
        store.create_run(
            state["run_id"],
            config.project_root,
            config.scratchpad,
            target_phase,
            "pending",
            execution_mode="prefix",
        )
        active_runner = runner or CodexRunner(config.codex_bin)
        return build_graph(
            active_runner,
            timeout_s=config.timeout_s,
            target_phase=target_phase,
            mode=config.mode,
        ).invoke(state)


def run_recon_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="recon", runner=runner)


def run_instantiate_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="instantiate", runner=runner)


def run_breadth_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="breadth", runner=runner)


def run_rescan_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="rescan", runner=runner)


def run_inventory_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="inventory", runner=runner)


def run_invariants_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="invariants", runner=runner)


def run_depth_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="depth", runner=runner)


def run_sc_semantic_dedup_graph(
    config: AuditConfig,
    runner: Any | None = None,
) -> AuditState:
    return run_graph(config, target_phase="sc_semantic_dedup", runner=runner)


def _same_resolved_path(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def _failed_single_node_state(
    config: AuditConfig,
    phase_name: str,
    base_run_id: str | None,
    error: str,
) -> AuditState:
    state = initial_state(
        config,
        target_phase=phase_name,
        base_run_id=base_run_id,
        execution_mode="single_node",
    )
    state["status"] = "failed"
    state["failed_phase"] = phase_name
    state["error"] = error
    return state


def _base_phase_succeeded(store: StateStore, base_run_id: str, phase_name: str) -> bool:
    row = store.fetch_one(
        """
        select 1 from phase_runs
        where run_id = ? and phase_name = ? and status = 'succeeded'
        limit 1
        """,
        (base_run_id, phase_name),
    )
    return row is not None


def _phase_succeeded_in_run_chain(
    store: StateStore,
    base_run_id: str,
    phase_name: str,
) -> bool:
    current: str | None = base_run_id
    seen: set[str] = set()
    while current:
        if current in seen:
            return False
        seen.add(current)
        if _base_phase_succeeded(store, current, phase_name):
            return True
        row = store.fetch_one("select base_run_id from runs where id = ?", (current,))
        current = str(row["base_run_id"]) if row and row.get("base_run_id") else None
    return False


def _latest_successful_phase_run_id(
    store: StateStore,
    config: AuditConfig,
    phase_name: str,
) -> str | None:
    rows = store.fetch_all(
        """
        select r.id, r.project_root, r.scratchpad
        from runs r
        join phase_runs p on p.run_id = r.id
        where p.phase_name = ?
          and p.status = 'succeeded'
          and r.status = 'succeeded'
        order by coalesce(p.finished_at, r.updated_at, r.created_at) desc
        """,
        (phase_name,),
    )
    for row in rows:
        if not _same_resolved_path(str(row["project_root"]), config.project_root):
            continue
        if not _same_resolved_path(str(row["scratchpad"]), config.scratchpad):
            continue
        return str(row["id"])
    return None


def _validate_predecessor_artifacts(
    phase_name: str,
    scratchpad: str | Path,
) -> list[str]:
    artifacts = check_artifacts(
        scratchpad,
        expected_phase_artifacts(phase_name, "sc"),
    )
    issues = [
        f"missing {phase_name} artifacts: {name}"
        for name in artifacts["missing"]
    ]
    issues.extend(
        validate_phase_artifacts(
            phase_name,
            scratchpad,
            artifacts["records"],
        )
    )
    return _dedupe_issues(issues)


def _validate_single_node_prerequisites(
    config: AuditConfig,
    phase_name: str,
    base_run_id: str | None,
) -> tuple[list[str], str | None, list[str]]:
    predecessors = _predecessors_for(phase_name, config.mode)
    if not predecessors:
        return [], None, []

    store = StateStore(config.db_path)
    store.init_db()
    resolved_base_run_id = base_run_id
    if not resolved_base_run_id:
        direct_predecessor = _direct_predecessor_for(phase_name, config.mode)
        if direct_predecessor:
            resolved_base_run_id = _latest_successful_phase_run_id(
                store,
                config,
                direct_predecessor,
            )
        if not resolved_base_run_id:
            return (
                predecessors,
                None,
                [
                    f"no successful {direct_predecessor} run found for "
                    f"{phase_name} single-node mode"
                ],
            )

    base_run = store.fetch_one(
        "select * from runs where id = ?",
        (resolved_base_run_id,),
    )
    if not base_run:
        return (
            predecessors,
            resolved_base_run_id,
            [f"base run not found: {resolved_base_run_id}"],
        )
    issues: list[str] = []
    if not _same_resolved_path(str(base_run["project_root"]), config.project_root):
        issues.append("base run project_root does not match this config")
    if not _same_resolved_path(str(base_run["scratchpad"]), config.scratchpad):
        issues.append("base run scratchpad does not match this config")

    for predecessor in predecessors:
        if not _phase_succeeded_in_run_chain(store, resolved_base_run_id, predecessor):
            issues.append(f"base run chain lacks successful {predecessor} phase")

    depth_prerequisites_checked = False
    sc_dedup_prerequisites_checked = False
    for predecessor in predecessors:
        if phase_name == "sc_semantic_dedup" and predecessor in {
            "inventory",
            "invariants",
            "depth",
        }:
            if not sc_dedup_prerequisites_checked:
                issues.extend(
                    sc_semantic_dedup_prerequisite_issues(
                        config.scratchpad,
                        config.mode,
                    )
                )
                sc_dedup_prerequisites_checked = True
            continue
        if phase_name == "depth" and predecessor in {"inventory", "invariants"}:
            if not depth_prerequisites_checked:
                issues.extend(depth_prerequisite_issues(config.scratchpad, config.mode))
                depth_prerequisites_checked = True
            continue
        if (
            phase_name in {
                "rescan",
                "inventory",
                "invariants",
                "depth",
                "sc_semantic_dedup",
            }
            and predecessor == "breadth"
        ):
            issues.extend(first_pass_breadth_issues(config.scratchpad))
        elif (
            phase_name in {"inventory", "invariants", "depth", "sc_semantic_dedup"}
            and predecessor == "rescan"
        ):
            issues.extend(rescan_prerequisite_issues(config.scratchpad))
        elif phase_name == "invariants" and predecessor == "inventory":
            issues.extend(invariants_prerequisite_issues(config.scratchpad))
        else:
            issues.extend(_validate_predecessor_artifacts(predecessor, config.scratchpad))

    return predecessors, resolved_base_run_id, _dedupe_issues(issues)


def run_phase_node(
    config: AuditConfig,
    phase_name: str,
    base_run_id: str | None = None,
    runner: Any | None = None,
) -> AuditState:
    if phase_name not in SUPPORTED_TARGET_PHASES:
        raise ValueError(f"unsupported target phase: {phase_name}")
    mode_error = _mode_gate_error(phase_name, config.mode)
    if mode_error:
        return _failed_single_node_state(config, phase_name, base_run_id, mode_error)

    scratchpad = Path(config.scratchpad)
    scratchpad.mkdir(parents=True, exist_ok=True)
    with _run_lock(scratchpad):
        (
            predecessors,
            resolved_base_run_id,
            prerequisite_issues,
        ) = _validate_single_node_prerequisites(config, phase_name, base_run_id)
        if prerequisite_issues:
            return _failed_single_node_state(
                config,
                phase_name,
                resolved_base_run_id or base_run_id,
                "; ".join(prerequisite_issues),
            )

        store = StateStore(config.db_path)
        store.init_db()
        state = initial_state(
            config,
            target_phase=phase_name,
            base_run_id=resolved_base_run_id,
            execution_mode="single_node",
            completed_phases=predecessors,
        )
        if predecessors:
            state["status"] = "succeeded"
        store.create_run(
            state["run_id"],
            config.project_root,
            config.scratchpad,
            phase_name,
            "pending",
            base_run_id=resolved_base_run_id,
            execution_mode="single_node",
        )
        active_runner = runner or CodexRunner(config.codex_bin)
        return _make_phase_node(
            phase_name,
            active_runner,
            config.timeout_s,
        )(state)
