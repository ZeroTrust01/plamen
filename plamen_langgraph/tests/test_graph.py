from __future__ import annotations

from dataclasses import dataclass

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.graph import run_recon_graph
from plamen_langgraph.plamen_lg.phases import expected_recon_artifacts
from plamen_langgraph.plamen_lg.store import StateStore


@dataclass
class FakeResult:
    stdout_path: str
    stderr_path: str
    events_path: str
    last_message_path: str
    returncode: int = 0
    started_at: str = "2026-01-01T00:00:00+00:00"
    finished_at: str = "2026-01-01T00:00:01+00:00"
    duration_s: float = 1.0
    timed_out: bool = False
    error: str | None = None

    def to_dict(self):
        return self.__dict__.copy()


class FakeRunner:
    def __init__(self, write_artifacts: bool = True, returncode: int = 0) -> None:
        self.write_artifacts = write_artifacts
        self.returncode = returncode
        self.calls = []

    def run(self, prompt, project_root, scratchpad, output_paths, timeout_s):
        self.calls.append(
            {
                "prompt": prompt,
                "project_root": project_root,
                "scratchpad": scratchpad,
                "timeout_s": timeout_s,
            }
        )
        output_paths["stdout_path"].write_text('{"event":"done"}\n', encoding="utf-8")
        output_paths["stderr_path"].write_text("", encoding="utf-8")
        output_paths["events_path"].write_text('{"event":"done"}\n', encoding="utf-8")
        output_paths["last_message_path"].write_text("done\n", encoding="utf-8")
        if self.write_artifacts:
            for name in expected_recon_artifacts():
                (output_paths["stdout_path"].parent / name).write_text(
                    f"# {name}\n\nsubstantive mocked recon artifact.\n",
                    encoding="utf-8",
                )
        return FakeResult(
            stdout_path=str(output_paths["stdout_path"]),
            stderr_path=str(output_paths["stderr_path"]),
            events_path=str(output_paths["events_path"]),
            last_message_path=str(output_paths["last_message_path"]),
            returncode=self.returncode,
        )


def test_mocked_successful_recon_marks_run_succeeded(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    config = build_config(project)
    runner = FakeRunner(write_artifacts=True)

    state = run_recon_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert len(runner.calls) == 1
    scratch = project / ".scratchpad"
    assert (scratch / "_lg_recon_prompt.md").exists()
    assert (scratch / "_lg_recon_stdout.log").exists()
    assert (scratch / "_lg_recon_stderr.log").exists()
    assert (scratch / "_lg_recon_events.jsonl").exists()
    assert (scratch / "_lg_recon_last_message.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one("select phase, status from runs where id = ?", (state["run_id"],))
    phase = store.fetch_one(
        "select phase_name, status, returncode from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    artifacts = store.fetch_all("select * from artifacts where run_id = ?", (state["run_id"],))
    assert run == {"phase": "recon", "status": "succeeded"}
    assert phase == {"phase_name": "recon", "status": "succeeded", "returncode": 0}
    assert len(artifacts) == len(expected_recon_artifacts())
    assert all(row["exists"] == 1 for row in artifacts)


def test_missing_recon_artifacts_marks_run_failed(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)

    state = run_recon_graph(config, runner=FakeRunner(write_artifacts=False))

    assert state["status"] == "failed"
    assert "missing recon artifacts" in (state["error"] or "")

    store = StateStore(config.db_path)
    run = store.fetch_one("select status from runs where id = ?", (state["run_id"],))
    phase = store.fetch_one("select status from phase_runs where run_id = ?", (state["run_id"],))
    missing = store.fetch_all(
        "select * from artifacts where run_id = ? and [exists] = 0",
        (state["run_id"],),
    )
    assert run == {"status": "failed"}
    assert phase == {"status": "failed"}
    assert len(missing) == len(expected_recon_artifacts())
