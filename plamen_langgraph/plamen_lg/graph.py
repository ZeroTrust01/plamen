from __future__ import annotations

from pathlib import Path
import os
import uuid
from typing import Any, Callable

from .artifacts import check_artifacts, validate_phase_artifacts
from .config import AuditConfig
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


SUPPORTED_TARGET_PHASES = {"recon", "instantiate"}


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


def _make_phase_node(
    phase_name: str,
    runner: Any | None = None,
    timeout_s: int = 3000,
) -> Callable[[AuditState], AuditState]:
    def phase_node(state: AuditState) -> AuditState:
        if phase_name == "instantiate" and (
            state.get("status") != "succeeded"
            or "recon" not in state.get("completed_phases", [])
        ):
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
            prompt = build_phase_prompt(phase_name, dict(state))
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

            artifacts = check_artifacts(
                scratchpad,
                expected_phase_artifacts(phase_name, state["pipeline"]),
            )
            store.record_artifacts(state["run_id"], phase_name, artifacts["records"])
            validation_issues = validate_phase_artifacts(
                phase_name,
                scratchpad,
                artifacts["records"],
            )
            artifact_issues = _dedupe_issues(
                [f"missing {phase_name} artifacts: {name}" for name in artifacts["missing"]]
                + validation_issues
            )

            timed_out = bool(result_dict.get("timed_out"))
            returncode = result_dict.get("returncode")
            error = result_dict.get("error")
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
) -> Any:
    if target_phase not in SUPPORTED_TARGET_PHASES:
        raise ValueError(f"unsupported target phase: {target_phase}")
    recon_node = _make_phase_node("recon", runner, timeout_s)
    nodes = [("recon", recon_node)]
    if target_phase == "instantiate":
        nodes.append(("instantiate", _make_phase_node("instantiate", runner, timeout_s)))
    if StateGraph is None:
        return _SequentialGraph([node for _name, node in nodes])

    graph = StateGraph(AuditState)
    for name, node in nodes:
        graph.add_node(name, node)
    graph.add_edge(START, "recon")
    if target_phase == "instantiate":
        graph.add_edge("recon", "instantiate")
        graph.add_edge("instantiate", END)
    else:
        graph.add_edge("recon", END)
    return graph.compile()


def initial_state(
    config: AuditConfig,
    run_id: str | None = None,
    target_phase: str = "recon",
) -> AuditState:
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "project_root": config.project_root,
        "scratchpad": config.scratchpad,
        "db_path": config.db_path,
        "pipeline": config.pipeline,
        "mode": config.mode,
        "language": config.language,
        "current_phase": "recon",
        "target_phase": target_phase,
        "completed_phases": [],
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
    scratchpad = Path(config.scratchpad)
    scratchpad.mkdir(parents=True, exist_ok=True)
    lock_path = scratchpad / "_lg_run.lock"
    lock_fd: int | None = None
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, f"{os.getpid()}\n".encode("utf-8"))
    except FileExistsError as exc:
        raise RuntimeError(f"another plamen_langgraph run is active: {lock_path}") from exc

    try:
        store = StateStore(config.db_path)
        store.init_db()

        state = initial_state(config, target_phase=target_phase)
        store.create_run(
            state["run_id"],
            config.project_root,
            config.scratchpad,
            target_phase,
            "pending",
        )
        active_runner = runner or CodexRunner(config.codex_bin)
        return build_graph(
            active_runner,
            timeout_s=config.timeout_s,
            target_phase=target_phase,
        ).invoke(state)
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def run_recon_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="recon", runner=runner)


def run_instantiate_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
    return run_graph(config, target_phase="instantiate", runner=runner)
