from __future__ import annotations

from dataclasses import dataclass

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.graph import run_graph, run_instantiate_graph, run_recon_graph
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


VALID_SPAWN_MANIFEST = """# Spawn Manifest

## Breadth Agents
| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_access_control.md | QUEUED |

**Gate Check**: All REQUIRED templates have agents? YES
"""


class FakeRunner:
    def __init__(
        self,
        write_artifacts: bool = True,
        returncode: int = 0,
        write_instantiate_artifact: bool = True,
        manifest_text: str = VALID_SPAWN_MANIFEST,
    ) -> None:
        self.write_artifacts = write_artifacts
        self.returncode = returncode
        self.write_instantiate_artifact = write_instantiate_artifact
        self.manifest_text = manifest_text
        self.calls = []

    def run(self, prompt, project_root, scratchpad, output_paths, timeout_s):
        phase = "instantiate" if "_lg_instantiate_" in str(output_paths["stdout_path"]) else "recon"
        self.calls.append(
            {
                "phase": phase,
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
        if phase == "recon" and self.write_artifacts:
            for name in expected_recon_artifacts():
                (output_paths["stdout_path"].parent / name).write_text(
                    f"# {name}\n\nsubstantive mocked recon artifact.\n",
                    encoding="utf-8",
                )
        if phase == "instantiate" and self.write_instantiate_artifact:
            (output_paths["stdout_path"].parent / "spawn_manifest.md").write_text(
                self.manifest_text,
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
    assert runner.calls[0]["phase"] == "recon"
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_recon_prompt.md").exists()
    assert (scratch / "_lg_recon_stdout.log").exists()
    assert (scratch / "_lg_recon_stderr.log").exists()
    assert (scratch / "_lg_recon_events.jsonl").exists()
    assert (scratch / "_lg_recon_last_message.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

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


def test_mocked_instantiate_runs_recon_then_instantiate(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_instantiate_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == ["recon", "instantiate"]
    assert [call["phase"] for call in runner.calls] == ["recon", "instantiate"]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_recon_prompt.md").exists()
    assert (scratch / "_lg_instantiate_prompt.md").exists()
    assert (scratch / "spawn_manifest.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one("select phase, status from runs where id = ?", (state["run_id"],))
    phases = store.fetch_all(
        "select phase_name, status, returncode from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts where run_id = ?",
        (state["run_id"],),
    )

    assert run == {"phase": "instantiate", "status": "succeeded"}
    assert phases == [
        {"phase_name": "recon", "status": "succeeded", "returncode": 0},
        {"phase_name": "instantiate", "status": "succeeded", "returncode": 0},
    ]
    assert any(
        row["phase_name"] == "instantiate"
        and row["path"].endswith("spawn_manifest.md")
        and row["exists"] == 1
        for row in artifacts
    )


def test_instantiate_is_skipped_when_recon_fails(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(write_artifacts=False)

    state = run_graph(config, target_phase="instantiate", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "recon"
    assert [call["phase"] for call in runner.calls] == ["recon"]

    store = StateStore(config.db_path)
    phase_rows = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    assert phase_rows == [{"phase_name": "recon"}]


def test_missing_spawn_manifest_marks_instantiate_failed(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=False)

    state = run_instantiate_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "instantiate"
    assert "spawn_manifest.md" in (state["error"] or "")

    store = StateStore(config.db_path)
    phase = store.fetch_one(
        "select status from phase_runs where run_id = ? and phase_name = 'instantiate'",
        (state["run_id"],),
    )
    missing = store.fetch_one(
        "select [exists] from artifacts where run_id = ? and phase_name = 'instantiate'",
        (state["run_id"],),
    )
    assert phase == {"status": "failed"}
    assert missing == {"exists": 0}


def test_invalid_spawn_manifest_marks_instantiate_failed(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        manifest_text="# Spawn Manifest\n\nThis is prose without the required table.\n",
    )

    state = run_instantiate_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "instantiate"
    assert "schema invalid" in (state["error"] or "")
