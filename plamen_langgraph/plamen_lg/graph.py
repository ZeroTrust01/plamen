from __future__ import annotations

from pathlib import Path
import os
import uuid
from typing import Any, Callable

from .artifacts import check_artifacts
from .config import AuditConfig
from .phases import build_recon_prompt, expected_recon_artifacts
from .runner import CodexRunner
from .state import AuditState
from .store import StateStore, utc_now

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    END = "__end__"
    START = "__start__"
    StateGraph = None


def _output_paths(scratchpad: str | Path) -> dict[str, Path]:
    sp = Path(scratchpad)
    return {
        "prompt_path": sp / "_lg_recon_prompt.md",
        "stdout_path": sp / "_lg_recon_stdout.log",
        "stderr_path": sp / "_lg_recon_stderr.log",
        "events_path": sp / "_lg_recon_events.jsonl",
        "last_message_path": sp / "_lg_recon_last_message.md",
    }


class _SequentialGraph:
    def __init__(self, node: Callable[[AuditState], AuditState]) -> None:
        self._node = node

    def invoke(self, state: AuditState) -> AuditState:
        return self._node(state)


def _make_recon_node(
    runner: Any | None = None,
    timeout_s: int = 3000,
) -> Callable[[AuditState], AuditState]:
    def recon_node(state: AuditState) -> AuditState:
        scratchpad = Path(state["scratchpad"])
        scratchpad.mkdir(parents=True, exist_ok=True)

        store = StateStore(state["db_path"])
        store.init_db()
        store.update_run_status(state["run_id"], "running")

        phase_run_id = f"{state['run_id']}:recon"
        started_at = utc_now()
        store.create_phase_run(phase_run_id, state["run_id"], "recon", "running", started_at)

        paths = _output_paths(scratchpad)
        try:
            prompt = build_recon_prompt(dict(state))
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

            artifacts = check_artifacts(scratchpad, expected_recon_artifacts())
            store.record_artifacts(state["run_id"], "recon", artifacts["records"])

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
            elif not artifacts["ok"]:
                phase_status = "failed"
                run_status = "failed"
                error = "missing recon artifacts: " + ", ".join(artifacts["missing"])
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
            next_state["status"] = run_status
            next_state["error"] = error
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
            next_state["status"] = "failed"
            next_state["error"] = error
            return next_state  # type: ignore[return-value]

    return recon_node


def build_graph(runner: Any | None = None, timeout_s: int = 3000) -> Any:
    recon_node = _make_recon_node(runner, timeout_s)
    if StateGraph is None:
        return _SequentialGraph(recon_node)

    graph = StateGraph(AuditState)
    graph.add_node("recon", recon_node)
    graph.add_edge(START, "recon")
    graph.add_edge("recon", END)
    return graph.compile()


def initial_state(config: AuditConfig, run_id: str | None = None) -> AuditState:
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "project_root": config.project_root,
        "scratchpad": config.scratchpad,
        "db_path": config.db_path,
        "pipeline": config.pipeline,
        "mode": config.mode,
        "language": config.language,
        "current_phase": "recon",
        "status": "pending",
        "error": None,
    }


def run_recon_graph(config: AuditConfig, runner: Any | None = None) -> AuditState:
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

        state = initial_state(config)
        store.create_run(
            state["run_id"],
            config.project_root,
            config.scratchpad,
            "recon",
            "pending",
        )
        active_runner = runner or CodexRunner(config.codex_bin)
        return build_graph(active_runner, timeout_s=config.timeout_s).invoke(state)
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
