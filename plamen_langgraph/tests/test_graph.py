from __future__ import annotations

from dataclasses import dataclass

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.artifacts import (
    BREADTH_MIN_BYTES,
    DEPTH_MIN_BYTES,
    INVARIANTS_MIN_BYTES,
    INVENTORY_MAX_SOURCE_BYTES,
    INVENTORY_MAX_SOURCE_FILES,
    INVENTORY_MIN_BYTES,
    RESCAN_MIN_BYTES,
    expected_breadth_artifacts,
    expected_depth_artifact_groups,
    inventory_source_files,
)
from plamen_langgraph.plamen_lg.graph import (
    run_depth_graph,
    run_breadth_graph,
    run_graph,
    run_instantiate_graph,
    run_invariants_graph,
    run_inventory_graph,
    run_phase_node,
    run_recon_graph,
    run_rescan_graph,
    run_sc_verify_queue_graph,
)
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
        write_breadth_artifacts: bool = True,
        write_rescan_artifacts: bool = True,
        write_inventory_artifact: bool = True,
        write_invariants_artifact: bool = True,
        write_depth_artifacts: bool = True,
        manifest_text: str = VALID_SPAWN_MANIFEST,
        returncodes: dict[str, int] | None = None,
    ) -> None:
        self.write_artifacts = write_artifacts
        self.returncode = returncode
        self.write_instantiate_artifact = write_instantiate_artifact
        self.write_breadth_artifacts = write_breadth_artifacts
        self.write_rescan_artifacts = write_rescan_artifacts
        self.write_inventory_artifact = write_inventory_artifact
        self.write_invariants_artifact = write_invariants_artifact
        self.write_depth_artifacts = write_depth_artifacts
        self.manifest_text = manifest_text
        self.returncodes = returncodes or {}
        self.calls = []

    def run(self, prompt, project_root, scratchpad, output_paths, timeout_s):
        stdout_path = str(output_paths["stdout_path"])
        if "_lg_depth_" in stdout_path:
            phase = "depth"
        elif "_lg_invariants_" in stdout_path:
            phase = "invariants"
        elif "_lg_inventory_" in stdout_path:
            phase = "inventory"
        elif "_lg_rescan_" in stdout_path:
            phase = "rescan"
        elif "_lg_breadth_" in stdout_path:
            phase = "breadth"
        elif "_lg_instantiate_" in stdout_path:
            phase = "instantiate"
        else:
            phase = "recon"
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
        if phase == "breadth" and self.write_breadth_artifacts:
            for name in expected_breadth_artifacts(output_paths["stdout_path"].parent):
                (output_paths["stdout_path"].parent / name).write_text(
                    f"# {name}\n\n" + ("x" * BREADTH_MIN_BYTES),
                    encoding="utf-8",
                )
        if phase == "rescan" and self.write_rescan_artifacts:
            (output_paths["stdout_path"].parent / "analysis_rescan_gap_review.md").write_text(
                "# Rescan gap review\n\n" + ("new rescan evidence " * RESCAN_MIN_BYTES),
                encoding="utf-8",
            )
            (
                output_paths["stdout_path"].parent
                / "analysis_percontract_scope_review.md"
            ).write_text(
                "# Per-contract scope review\n\n"
                + ("new per-contract evidence " * RESCAN_MIN_BYTES),
                encoding="utf-8",
            )
        if phase == "inventory" and self.write_inventory_artifact:
            write_inventory_artifact(output_paths["stdout_path"].parent)
        if phase == "invariants" and self.write_invariants_artifact:
            write_invariants_artifact(output_paths["stdout_path"].parent)
        if phase == "depth" and self.write_depth_artifacts:
            if "Mode: `thorough`" in prompt:
                mode = "thorough"
            elif "Mode: `light`" in prompt:
                mode = "light"
            else:
                mode = "core"
            write_depth_artifacts(output_paths["stdout_path"].parent, mode)
        return FakeResult(
            stdout_path=str(output_paths["stdout_path"]),
            stderr_path=str(output_paths["stderr_path"]),
            events_path=str(output_paths["events_path"]),
            last_message_path=str(output_paths["last_message_path"]),
            returncode=self.returncodes.get(phase, self.returncode),
        )


def write_recon_artifacts(scratch) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    for name in expected_recon_artifacts():
        (scratch / name).write_text(
            f"# {name}\n\nsubstantive seeded recon artifact.\n",
            encoding="utf-8",
        )


def write_breadth_artifacts(scratch) -> None:
    for name in expected_breadth_artifacts(scratch):
        (scratch / name).write_text(
            f"# {name}\n\n" + ("seeded breadth artifact " * BREADTH_MIN_BYTES),
            encoding="utf-8",
        )


def write_rescan_artifacts(scratch) -> None:
    (scratch / "analysis_rescan_gap_review.md").write_text(
        "# Rescan gap review\n\n" + ("seeded rescan artifact " * RESCAN_MIN_BYTES),
        encoding="utf-8",
    )
    (scratch / "analysis_percontract_scope_review.md").write_text(
        "# Per-contract scope review\n\n"
        + ("seeded per-contract artifact " * RESCAN_MIN_BYTES),
        encoding="utf-8",
    )


def inventory_body(source_files: list[str]) -> str:
    source_rows = "\n".join(
        f"| {name} | 1 | 1 | 1 |" for name in source_files
    )
    return (
        "# Findings Inventory\n\n"
        "## Source Summary\n\n"
        "| Source File | Pre-Dedup Findings | Post-Dedup Findings | Notes |\n"
        "|-------------|--------------------|---------------------|-------|\n"
        f"{source_rows}\n\n"
        "## Master Table\n\n"
        "| # | Finding ID | Title | Severity | Verdict | Location | Source IDs | Root Cause | Preferred Tag |\n"
        "|---|------------|-------|----------|---------|----------|------------|------------|---------------|\n"
        "| 1 | [CS-1] | Example issue | Medium | CONFIRMED | src/A.sol:1 | B1 | Missing validation | [CODE] |\n\n"
        "## Per-Finding Detail\n\n"
        "### [CS-1] Example issue\n\n"
        "Finding ID: [CS-1]\n"
        "Title: Example issue\n"
        "Severity: Medium\n"
        "Verdict: CONFIRMED\n"
        "Location: src/A.sol:1\n"
        "Source IDs: B1\n"
        "Root Cause: Missing validation.\n"
        "Preferred Tag: [CODE]\n\n"
        + ("Detailed preserved evidence. " * INVENTORY_MIN_BYTES)
    )


def write_inventory_artifact(scratch) -> None:
    (scratch / "findings_inventory.md").write_text(
        inventory_body(inventory_source_files(scratch)),
        encoding="utf-8",
    )


def invariants_body() -> str:
    return (
        "# Semantic Invariants\n\n"
        "## Main Table\n\n"
        "| Variable | Contract/Module | Semantic Invariant | Write Sites (with CONDITIONAL annotations) | Value-Changing Functions | Potential Gaps |\n"
        "|----------|-----------------|--------------------|--------------------------------------------|--------------------------|----------------|\n"
        "| totalAssets | Vault | totalAssets tracks managed assets | Vault.sol:10 | deposit, withdraw | NONE_DETECTED |\n\n"
        "## Mirror Variable Pairs\n\n"
        "| Variable A | Variable B | Same Concept | Functions Writing A Only | Functions Writing B Only | Sync Gaps |\n"
        "|------------|------------|--------------|--------------------------|--------------------------|-----------|\n"
        "| totalAssets | cachedAssets | Asset accounting | none | none | NONE_DETECTED |\n\n"
        "## Time-Weighted Accumulators\n\n"
        "| Accumulator | Formula Pattern | Controllable Input | Time Source | Unbounded Delta? | Exposure |\n"
        "|-------------|-----------------|--------------------|-------------|------------------|----------|\n"
        "| rewardIndex | value * time_delta | stake | block.timestamp | NO | NONE_DETECTED |\n\n"
        "## Semantic Clusters\n\n"
        "| Cluster Name | Variables | Lifecycle Functions | Full-Write Functions | Partial-Write Functions |\n"
        "|--------------|-----------|---------------------|----------------------|-------------------------|\n"
        "| vault accounting | totalAssets, totalSupply | deposit, withdraw | deposit, withdraw | none |\n\n"
        "## Write Completeness vs Semantic Correctness\n\n"
        "| Variable | Write-Site Status | Semantic Status | Basis for Status | Depth Agent Follow-Up |\n"
        "|----------|-------------------|-----------------|------------------|-----------------------|\n"
        "| totalAssets | WRITE_SITES_COMPLETE | SEMANTICS_OK | writers and reads align | none |\n\n"
        "## Read-Site Expectations\n\n"
        "| Variable | Read Site | Read Context | Expected Meaning | Evidence | Expectation Status |\n"
        "|----------|-----------|--------------|------------------|----------|--------------------|\n"
        "| totalAssets | Vault.sol:20 | share price | managed assets | code trace | CLEAR |\n\n"
        "## Write/Read Meaning Drift\n\n"
        "| Variable | Write-Side Meaning | Read-Side Expectation | Drift Type | Affected Functions | Suspected Impact |\n"
        "|----------|--------------------|-----------------------|------------|--------------------|------------------|\n"
        "| totalAssets | managed assets | managed assets | NONE_DETECTED | none | none |\n\n"
        "## Branch-Conditioned Formula Inputs\n\n"
        "| Variable/Formula | Function | Branch Condition | Inputs Used | Inputs Omitted or Changed | Drift/Exposure Flag |\n"
        "|------------------|----------|------------------|-------------|---------------------------|---------------------|\n"
        "| totalAssets | deposit | none | amount | none | NONE_DETECTED |\n\n"
        "## Lifecycle Semantics\n\n"
        "| Variable | Lifecycle Role | Transition Functions | Expected State Transitions | Missing or Asymmetric Updates | Lifecycle Flag |\n"
        "|----------|----------------|----------------------|----------------------------|-------------------------------|----------------|\n"
        "| totalAssets | accumulated | deposit, withdraw | increase/decrease | none | NONE_DETECTED |\n\n"
        "## Refutation Hazards\n\n"
        "| Gap or Variable | Why It May Be False Positive | Evidence Needed to Refute | Suggested Depth Check |\n"
        "|-----------------|--------------------------------|---------------------------|-----------------------|\n"
        "| totalAssets | no suspected gap | none | none |\n\n"
        + ("Semantic invariant evidence. " * INVARIANTS_MIN_BYTES)
    )


def write_invariants_artifact(scratch) -> None:
    (scratch / "semantic_invariants.md").write_text(
        invariants_body(),
        encoding="utf-8",
    )


def depth_body(title: str, finding_id: str = "[DT-1]") -> str:
    return (
        f"# {title}\n\n"
        "## Investigated Candidates\n\n"
        f"- Candidate {finding_id}: reviewed inventory source CS-1 and related code paths.\n\n"
        "## Evidence\n\n"
        "- Source location: src/A.sol:10-20. Reference: findings_inventory.md CS-1.\n\n"
        "## Verdict\n\n"
        f"- {finding_id}: UNRESOLVED pending stronger exploitability evidence.\n\n"
        "## Limitations\n\n"
        "- Limitations: no live deployment configuration was available; unresolved evidence gap recorded.\n\n"
        + ("Depth evidence. " * DEPTH_MIN_BYTES)
    )


def confidence_body() -> str:
    return (
        "# Confidence Scores\n\n"
        "| Finding ID | Confidence | Rationale |\n"
        "|------------|------------|-----------|\n"
        "| [DT-1] | Medium | Evidence references support a plausible issue. |\n\n"
        + ("Confidence evidence. " * DEPTH_MIN_BYTES)
    )


def write_depth_artifacts(scratch, mode: str = "core") -> None:
    for group in expected_depth_artifact_groups(mode):
        name = group[0]
        if name == "confidence_scores.md":
            (scratch / name).write_text(confidence_body(), encoding="utf-8")
            continue
        (scratch / name).write_text(
            depth_body(name.replace("_", " ").replace(".md", "").title()),
            encoding="utf-8",
        )


def seed_base_run(
    config,
    run_id: str,
    phases: list[str],
    base_run_id: str | None = None,
    execution_mode: str = "prefix",
) -> None:
    scratch = config.scratchpad
    store = StateStore(config.db_path)
    store.init_db()
    store.create_run(
        run_id,
        config.project_root,
        scratch,
        phases[-1] if phases else "recon",
        "succeeded",
        base_run_id=base_run_id,
        execution_mode=execution_mode,
    )
    for phase in phases:
        phase_run_id = f"{run_id}:{phase}"
        store.create_phase_run(phase_run_id, run_id, phase)
        store.update_phase_run(phase_run_id, "succeeded", returncode=0)


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


def test_mocked_breadth_runs_recon_instantiate_then_breadth(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_breadth_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == ["recon", "instantiate", "breadth"]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_breadth_prompt.md").exists()
    assert (scratch / "analysis_core_state.md").exists()
    assert (scratch / "analysis_access_control.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name, status from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    breadth_artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts where run_id = ? and phase_name = 'breadth'",
        (state["run_id"],),
    )

    assert run == {
        "phase": "breadth",
        "execution_mode": "prefix",
        "base_run_id": None,
        "status": "succeeded",
    }
    assert phases == [
        {"phase_name": "recon", "status": "succeeded"},
        {"phase_name": "instantiate", "status": "succeeded"},
        {"phase_name": "breadth", "status": "succeeded"},
    ]
    assert len(breadth_artifacts) == 2
    assert all(row["exists"] == 1 for row in breadth_artifacts)


def test_breadth_is_skipped_when_instantiate_fails(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        manifest_text="# Spawn Manifest\n\nInvalid.\n",
    )

    state = run_graph(config, target_phase="breadth", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "instantiate"
    assert [call["phase"] for call in runner.calls] == ["recon", "instantiate"]

    store = StateStore(config.db_path)
    phase_rows = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    assert phase_rows == [{"phase_name": "recon"}, {"phase_name": "instantiate"}]


def test_breadth_prefix_stops_when_recon_fails(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(write_artifacts=False)

    state = run_graph(config, target_phase="breadth", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "recon"
    assert [call["phase"] for call in runner.calls] == ["recon"]

    store = StateStore(config.db_path)
    phase_rows = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    assert phase_rows == [{"phase_name": "recon"}]


def test_missing_breadth_output_marks_breadth_failed(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=False,
    )

    state = run_breadth_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "breadth"
    assert "missing breadth artifact: analysis_core_state.md" in (state["error"] or "")


def test_single_node_breadth_uses_successful_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    seed_base_run(config, "base-run", ["recon", "instantiate"])
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "breadth", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["breadth"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    base = store.fetch_one("select status from runs where id = ?", ("base-run",))
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "breadth",
        "execution_mode": "single_node",
        "base_run_id": "base-run",
        "status": "succeeded",
    }
    assert base == {"status": "succeeded"}
    assert phases == [{"phase_name": "breadth"}]


def test_single_node_breadth_infers_latest_successful_instantiate_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    seed_base_run(config, "instantiate-run", ["recon", "instantiate"])
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "breadth", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "instantiate-run"
    assert [call["phase"] for call in runner.calls] == ["breadth"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "breadth",
        "execution_mode": "single_node",
        "base_run_id": "instantiate-run",
        "status": "succeeded",
    }


def test_single_node_instantiate_uses_successful_recon_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon"])
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=True)

    state = run_phase_node(config, "instantiate", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["instantiate"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "instantiate",
        "execution_mode": "single_node",
        "base_run_id": "base-run",
        "status": "succeeded",
    }
    assert phases == [{"phase_name": "instantiate"}]


def test_single_node_instantiate_requires_successful_recon_and_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    seed_base_run(config, "base-run", [])
    runner = FakeRunner()

    state = run_phase_node(config, "instantiate", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "successful recon" in (state["error"] or "")
    assert runner.calls == []


def test_single_node_breadth_requires_valid_spawn_manifest(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project)
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text("# invalid\n", encoding="utf-8")
    seed_base_run(config, "base-run", ["recon", "instantiate"])
    runner = FakeRunner()

    state = run_phase_node(config, "breadth", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "spawn_manifest.md" in (state["error"] or "")
    assert runner.calls == []


def test_rescan_runs_in_core_mode(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_graph(config, target_phase="rescan", runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
    ]


def test_mocked_rescan_runs_full_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_rescan_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_rescan_prompt.md").exists()
    assert (scratch / "analysis_rescan_gap_review.md").exists()
    assert (scratch / "analysis_percontract_scope_review.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name, status from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    rescan_artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts "
        "where run_id = ? and phase_name = 'rescan'",
        (state["run_id"],),
    )

    assert run == {
        "phase": "rescan",
        "execution_mode": "prefix",
        "base_run_id": None,
        "status": "succeeded",
    }
    assert phases == [
        {"phase_name": "recon", "status": "succeeded"},
        {"phase_name": "instantiate", "status": "succeeded"},
        {"phase_name": "breadth", "status": "succeeded"},
        {"phase_name": "rescan", "status": "succeeded"},
    ]
    assert len(rescan_artifacts) == 2
    assert all(row["exists"] == 1 for row in rescan_artifacts)


def test_rescan_fails_when_outputs_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=False,
    )

    state = run_rescan_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "rescan"
    assert "missing rescan artifact family" in (state["error"] or "")
    assert "missing per-contract artifact family" in (state["error"] or "")


def test_single_node_rescan_uses_successful_breadth_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth"])
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "rescan", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["rescan"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "rescan",
        "execution_mode": "single_node",
        "base_run_id": "base-run",
        "status": "succeeded",
    }
    assert phases == [{"phase_name": "rescan"}]


def test_single_node_rescan_infers_latest_successful_breadth_run_chain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    seed_base_run(config, "instantiate-run", ["recon", "instantiate"])
    seed_base_run(
        config,
        "breadth-run",
        ["breadth"],
        base_run_id="instantiate-run",
        execution_mode="single_node",
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "rescan", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "breadth-run"
    assert [call["phase"] for call in runner.calls] == ["rescan"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "rescan",
        "execution_mode": "single_node",
        "base_run_id": "breadth-run",
        "status": "succeeded",
    }


def test_single_node_rescan_requires_successful_breadth_and_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    seed_base_run(config, "base-run", ["recon", "instantiate"])
    runner = FakeRunner()

    state = run_phase_node(config, "rescan", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "successful breadth" in (state["error"] or "")
    assert "missing first-pass breadth artifact" in (state["error"] or "")
    assert runner.calls == []


def test_mocked_inventory_runs_full_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_inventory_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_inventory_prompt.md").exists()
    assert (scratch / "findings_inventory.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name, status from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    inventory_artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts "
        "where run_id = ? and phase_name = 'inventory'",
        (state["run_id"],),
    )

    assert run == {
        "phase": "inventory",
        "execution_mode": "prefix",
        "base_run_id": None,
        "status": "succeeded",
    }
    assert phases == [
        {"phase_name": "recon", "status": "succeeded"},
        {"phase_name": "instantiate", "status": "succeeded"},
        {"phase_name": "breadth", "status": "succeeded"},
        {"phase_name": "rescan", "status": "succeeded"},
        {"phase_name": "inventory", "status": "succeeded"},
    ]
    assert len(inventory_artifacts) == 1
    assert inventory_artifacts[0]["phase_name"] == "inventory"
    assert inventory_artifacts[0]["path"].endswith("findings_inventory.md")
    assert inventory_artifacts[0]["exists"] == 1


def test_inventory_is_skipped_when_rescan_fails(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=False,
    )

    state = run_graph(config, target_phase="inventory", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "rescan"
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
    ]


def test_inventory_fails_when_output_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=True,
        write_inventory_artifact=False,
    )

    state = run_inventory_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "inventory"
    assert "missing inventory artifact: findings_inventory.md" in (state["error"] or "")


def test_single_node_inventory_uses_successful_rescan_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth", "rescan"])
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "inventory", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["inventory"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "inventory",
        "execution_mode": "single_node",
        "base_run_id": "base-run",
        "status": "succeeded",
    }
    assert phases == [{"phase_name": "inventory"}]


def test_single_node_inventory_infers_latest_successful_rescan_run_chain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    seed_base_run(config, "instantiate-run", ["recon", "instantiate"])
    seed_base_run(
        config,
        "breadth-run",
        ["breadth"],
        base_run_id="instantiate-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "rescan-run",
        ["rescan"],
        base_run_id="breadth-run",
        execution_mode="single_node",
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "inventory", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "rescan-run"
    assert [call["phase"] for call in runner.calls] == ["inventory"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "inventory",
        "execution_mode": "single_node",
        "base_run_id": "rescan-run",
        "status": "succeeded",
    }


def test_single_node_inventory_requires_successful_rescan_and_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth"])
    runner = FakeRunner()

    state = run_phase_node(config, "inventory", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "successful rescan" in (state["error"] or "")
    assert "missing rescan artifact family" in (state["error"] or "")
    assert runner.calls == []


def _large_spawn_manifest(count: int) -> str:
    rows = "\n".join(
        "| AGENT | CORE_STATE | YES | B{idx} | focus_{idx} | analysis_focus_{idx}.md | QUEUED |".format(
            idx=idx
        )
        for idx in range(count)
    )
    return (
        "# Spawn Manifest\n\n"
        "| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |\n"
        "|----------|----------|-----------|----------|------------|-----------------|--------|\n"
        f"{rows}\n"
    )


def test_inventory_source_count_limit_fails_before_runner(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    source_count = INVENTORY_MAX_SOURCE_FILES + 1
    (scratch / "spawn_manifest.md").write_text(
        _large_spawn_manifest(source_count),
        encoding="utf-8",
    )
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth", "rescan"])
    runner = FakeRunner()

    state = run_phase_node(config, "inventory", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert (
        "inventory source set too large; needs sharded inventory support"
        in (state["error"] or "")
    )
    assert runner.calls == []
    assert not (scratch / "_lg_inventory_prompt.md").exists()


def test_inventory_source_byte_limit_fails_before_runner(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    for name in expected_breadth_artifacts(scratch):
        (scratch / name).write_text(
            "x" * (INVENTORY_MAX_SOURCE_BYTES + 1),
            encoding="utf-8",
        )
    write_rescan_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth", "rescan"])
    runner = FakeRunner()

    state = run_phase_node(config, "inventory", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert (
        "inventory source set too large; needs sharded inventory support"
        in (state["error"] or "")
    )
    assert runner.calls == []
    assert not (scratch / "_lg_inventory_prompt.md").exists()


def test_mocked_invariants_runs_full_prefix_in_core_mode(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_invariants_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_invariants_prompt.md").exists()
    assert (scratch / "semantic_invariants.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name, status from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    invariants_artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts "
        "where run_id = ? and phase_name = 'invariants'",
        (state["run_id"],),
    )

    assert run == {
        "phase": "invariants",
        "execution_mode": "prefix",
        "base_run_id": None,
        "status": "succeeded",
    }
    assert phases == [
        {"phase_name": "recon", "status": "succeeded"},
        {"phase_name": "instantiate", "status": "succeeded"},
        {"phase_name": "breadth", "status": "succeeded"},
        {"phase_name": "rescan", "status": "succeeded"},
        {"phase_name": "inventory", "status": "succeeded"},
        {"phase_name": "invariants", "status": "succeeded"},
    ]
    assert len(invariants_artifacts) == 1
    assert invariants_artifacts[0]["phase_name"] == "invariants"
    assert invariants_artifacts[0]["path"].endswith("semantic_invariants.md")
    assert invariants_artifacts[0]["exists"] == 1


def test_invariants_runs_full_prefix_in_thorough_mode(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_graph(config, target_phase="invariants", runner=runner)

    assert state["status"] == "succeeded"
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
    ]


def test_invariants_light_mode_fails_before_runner_and_phase_rows(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="light")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_graph(config, target_phase="invariants", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "invariants"
    assert "unavailable in light mode" in (state["error"] or "")
    assert runner.calls == []

    assert not (project / ".lg_scratchpad" / "plamen_lg.sqlite").exists()


def test_invariants_is_skipped_when_inventory_fails(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=True,
        write_inventory_artifact=False,
    )

    state = run_graph(config, target_phase="invariants", runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "inventory"
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
    ]


def test_invariants_fails_when_output_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=True,
        write_inventory_artifact=True,
        write_invariants_artifact=False,
    )

    state = run_invariants_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "invariants"
    assert "missing invariants artifact: semantic_invariants.md" in (state["error"] or "")


def test_single_node_invariants_uses_successful_inventory_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    seed_base_run(
        config,
        "base-run",
        ["recon", "instantiate", "breadth", "rescan", "inventory"],
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "invariants", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["invariants"]

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )

    assert run == {
        "phase": "invariants",
        "execution_mode": "single_node",
        "base_run_id": "base-run",
        "status": "succeeded",
    }
    assert phases == [{"phase_name": "invariants"}]


def test_single_node_invariants_infers_latest_successful_inventory_run_chain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    seed_base_run(config, "instantiate-run", ["recon", "instantiate"])
    seed_base_run(
        config,
        "breadth-run",
        ["breadth"],
        base_run_id="instantiate-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "rescan-run",
        ["rescan"],
        base_run_id="breadth-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "inventory-run",
        ["inventory"],
        base_run_id="rescan-run",
        execution_mode="single_node",
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "invariants", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "inventory-run"
    assert [call["phase"] for call in runner.calls] == ["invariants"]


def test_single_node_invariants_requires_successful_inventory_and_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    seed_base_run(config, "base-run", ["recon", "instantiate", "breadth", "rescan"])
    runner = FakeRunner()

    state = run_phase_node(config, "invariants", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "successful inventory" in (state["error"] or "")
    assert "missing inventory artifact: findings_inventory.md" in (state["error"] or "")
    assert runner.calls == []


def test_mocked_depth_light_runs_without_invariants(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="light")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_depth_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "depth",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "depth",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "_lg_depth_prompt.md").exists()
    assert (scratch / "depth_token_flow_findings.md").exists()
    assert not (scratch / "semantic_invariants.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    phases = store.fetch_all(
        "select phase_name, status from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    depth_artifacts = store.fetch_all(
        "select phase_name, path, [exists] from artifacts "
        "where run_id = ? and phase_name = 'depth'",
        (state["run_id"],),
    )

    assert phases == [
        {"phase_name": "recon", "status": "succeeded"},
        {"phase_name": "instantiate", "status": "succeeded"},
        {"phase_name": "breadth", "status": "succeeded"},
        {"phase_name": "rescan", "status": "succeeded"},
        {"phase_name": "inventory", "status": "succeeded"},
        {"phase_name": "depth", "status": "succeeded"},
    ]
    assert len(depth_artifacts) == 4
    assert all(row["exists"] == 1 for row in depth_artifacts)


def test_mocked_depth_core_runs_after_invariants(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_depth_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
    ]

    store = StateStore(config.db_path)
    depth_artifacts = store.fetch_all(
        "select path, [exists] from artifacts where run_id = ? and phase_name = 'depth'",
        (state["run_id"],),
    )
    assert len(depth_artifacts) == 9
    assert any(row["path"].endswith("confidence_scores.md") for row in depth_artifacts)
    assert all(row["exists"] == 1 for row in depth_artifacts)


def test_mocked_depth_thorough_requires_extra_groups(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="thorough")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_depth_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
    ]

    store = StateStore(config.db_path)
    depth_artifacts = store.fetch_all(
        "select path, [exists] from artifacts where run_id = ? and phase_name = 'depth'",
        (state["run_id"],),
    )
    assert len(depth_artifacts) == 12
    assert any(
        row["path"].endswith("design_stress_findings.md")
        for row in depth_artifacts
    )
    assert any(
        row["path"].endswith("perturbation_findings.md")
        for row in depth_artifacts
    )
    assert any(
        row["path"].endswith("skill_execution_gaps.md")
        for row in depth_artifacts
    )


def test_depth_is_skipped_when_invariants_fail_in_core(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=True,
        write_inventory_artifact=True,
        write_invariants_artifact=False,
    )

    state = run_depth_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "invariants"
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
    ]


def test_depth_fails_when_outputs_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="light")
    runner = FakeRunner(
        write_artifacts=True,
        write_instantiate_artifact=True,
        write_breadth_artifacts=True,
        write_rescan_artifacts=True,
        write_inventory_artifact=True,
        write_depth_artifacts=False,
    )

    state = run_depth_graph(config, runner=runner)

    assert state["status"] == "failed"
    assert state["failed_phase"] == "depth"
    assert "missing depth artifact group: depth_token_flow_findings.md" in (
        state["error"] or ""
    )


def test_single_node_depth_light_uses_successful_inventory_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="light")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    seed_base_run(
        config,
        "base-run",
        ["recon", "instantiate", "breadth", "rescan", "inventory"],
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "depth", base_run_id="base-run", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert [call["phase"] for call in runner.calls] == ["depth"]

    store = StateStore(config.db_path)
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    assert phases == [{"phase_name": "depth"}]


def test_single_node_depth_core_infers_latest_successful_invariants_run_chain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    write_invariants_artifact(scratch)
    seed_base_run(config, "instantiate-run", ["recon", "instantiate"])
    seed_base_run(
        config,
        "breadth-run",
        ["breadth"],
        base_run_id="instantiate-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "rescan-run",
        ["rescan"],
        base_run_id="breadth-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "inventory-run",
        ["inventory"],
        base_run_id="rescan-run",
        execution_mode="single_node",
    )
    seed_base_run(
        config,
        "invariants-run",
        ["invariants"],
        base_run_id="inventory-run",
        execution_mode="single_node",
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(config, "depth", runner=runner)

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "invariants-run"
    assert [call["phase"] for call in runner.calls] == ["depth"]


def test_single_node_depth_core_requires_successful_invariants_and_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    seed_base_run(
        config,
        "base-run",
        ["recon", "instantiate", "breadth", "rescan", "inventory"],
    )
    runner = FakeRunner()

    state = run_phase_node(config, "depth", base_run_id="base-run", runner=runner)

    assert state["status"] == "failed"
    assert "successful invariants" in (state["error"] or "")
    assert "missing invariants artifact: semantic_invariants.md" in (
        state["error"] or ""
    )
    assert runner.calls == []


def test_mocked_sc_verify_queue_core_runs_prefix_without_verifier_runner(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_sc_verify_queue_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
        "sc_verify_queue",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "invariants",
        "depth",
    ]
    scratch = project / ".lg_scratchpad"
    assert (scratch / "verification_queue.md").exists()
    assert (scratch / "verification_queue.json").exists()
    assert (scratch / "verification_queue_medium_a.md").exists()
    assert (scratch / "verification_queue_medium_a.json").exists()
    assert (scratch / "_lg_sc_verify_queue_last_message.md").exists()
    assert not (scratch / "_v2_checkpoint.json").exists()
    assert not (project / ".scratchpad").exists()

    store = StateStore(config.db_path)
    run = store.fetch_one(
        "select phase, execution_mode, base_run_id, status from runs where id = ?",
        (state["run_id"],),
    )
    phases = store.fetch_all(
        "select phase_name, status, returncode from phase_runs where run_id = ? order by started_at",
        (state["run_id"],),
    )
    queue_artifacts = store.fetch_all(
        "select path, [exists] from artifacts where run_id = ? and phase_name = 'sc_verify_queue'",
        (state["run_id"],),
    )

    assert run == {
        "phase": "sc_verify_queue",
        "execution_mode": "prefix",
        "base_run_id": None,
        "status": "succeeded",
    }
    assert phases[-1] == {
        "phase_name": "sc_verify_queue",
        "status": "succeeded",
        "returncode": 0,
    }
    assert any(row["path"].endswith("verification_queue.md") for row in queue_artifacts)
    assert all(row["exists"] == 1 for row in queue_artifacts)


def test_sc_verify_queue_light_prefix_skips_invariants(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="light")
    runner = FakeRunner(write_artifacts=True, write_instantiate_artifact=True)

    state = run_sc_verify_queue_graph(config, runner=runner)

    assert state["status"] == "succeeded"
    assert state["completed_phases"] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "depth",
        "sc_verify_queue",
    ]
    assert [call["phase"] for call in runner.calls] == [
        "recon",
        "instantiate",
        "breadth",
        "rescan",
        "inventory",
        "depth",
    ]


def test_single_node_sc_verify_queue_uses_successful_depth_base_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    write_invariants_artifact(scratch)
    write_depth_artifacts(scratch, "core")
    seed_base_run(
        config,
        "base-run",
        [
            "recon",
            "instantiate",
            "breadth",
            "rescan",
            "inventory",
            "invariants",
            "depth",
        ],
    )
    runner = FakeRunner(write_artifacts=False, write_instantiate_artifact=False)

    state = run_phase_node(
        config,
        "sc_verify_queue",
        base_run_id="base-run",
        runner=runner,
    )

    assert state["status"] == "succeeded"
    assert state["execution_mode"] == "single_node"
    assert state["base_run_id"] == "base-run"
    assert runner.calls == []
    assert (scratch / "verification_queue.md").exists()
    assert (scratch / "verification_queue_crithigh.md").exists()

    store = StateStore(config.db_path)
    phases = store.fetch_all(
        "select phase_name from phase_runs where run_id = ?",
        (state["run_id"],),
    )
    assert phases == [{"phase_name": "sc_verify_queue"}]


def test_single_node_sc_verify_queue_requires_depth_outputs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, mode="core")
    scratch = project / ".lg_scratchpad"
    write_recon_artifacts(scratch)
    (scratch / "spawn_manifest.md").write_text(VALID_SPAWN_MANIFEST, encoding="utf-8")
    write_breadth_artifacts(scratch)
    write_rescan_artifacts(scratch)
    write_inventory_artifact(scratch)
    write_invariants_artifact(scratch)
    seed_base_run(
        config,
        "base-run",
        [
            "recon",
            "instantiate",
            "breadth",
            "rescan",
            "inventory",
            "invariants",
            "depth",
        ],
    )
    runner = FakeRunner()

    state = run_phase_node(
        config,
        "sc_verify_queue",
        base_run_id="base-run",
        runner=runner,
    )

    assert state["status"] == "failed"
    assert "missing depth artifact group: depth_token_flow_findings.md" in (
        state["error"] or ""
    )
    assert runner.calls == []
    assert not (scratch / "verification_queue.md").exists()
