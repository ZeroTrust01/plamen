from __future__ import annotations

import hashlib

from plamen_langgraph.plamen_lg import artifacts as artifacts_module
from plamen_langgraph.plamen_lg.artifacts import (
    BREADTH_MIN_BYTES,
    DEPTH_MIN_BYTES,
    INVARIANTS_MIN_BYTES,
    INVENTORY_MIN_BYTES,
    INVENTORY_SOURCE_TOO_LARGE,
    RESCAN_MIN_BYTES,
    check_artifacts,
    depth_prerequisite_issues,
    expected_breadth_artifacts,
    expected_depth_artifact_groups,
    expected_invariants_artifacts,
    expected_inventory_artifacts,
    first_pass_breadth_issues,
    invariants_prerequisite_issues,
    inventory_source_files,
    inventory_source_size_issues,
    validate_phase_artifacts,
    validate_spawn_manifest_schema,
)


def test_artifact_checker_records_present_and_missing(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    artifact = scratch / "recon_summary.md"
    artifact.write_text("recon body", encoding="utf-8")

    result = check_artifacts(scratch, ["recon_summary.md", "missing.md"])

    assert result["ok"] is False
    assert result["missing"] == ["missing.md"]
    assert result["present"][0]["path"] == str(artifact)
    assert result["present"][0]["size_bytes"] == len("recon body")
    assert result["present"][0]["sha256"] == hashlib.sha256(b"recon body").hexdigest()
    assert any(record["exists"] is False for record in result["records"])


def test_spawn_manifest_schema_accepts_valid_agent_table(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

## Breadth Agents
| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_access_control.md | QUEUED |

**Gate Check**: All REQUIRED templates have agents? YES
""",
        encoding="utf-8",
    )

    assert validate_spawn_manifest_schema(scratch) == []
    assert validate_phase_artifacts("instantiate", scratch, []) == []


def test_spawn_manifest_schema_rejects_duplicate_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_core.md | QUEUED |
""",
        encoding="utf-8",
    )

    issues = validate_spawn_manifest_schema(scratch)

    assert any("duplicate output file" in issue for issue in issues)


def test_spawn_manifest_schema_rejects_downstream_artifacts(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | verify_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )

    issues = validate_spawn_manifest_schema(scratch)

    assert any("non-breadth artifact" in issue for issue in issues)
    assert any("analysis_*.md output" in issue for issue in issues)


def test_expected_breadth_artifacts_are_manifest_exact(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_access_control.md | QUEUED |
| SKILL | ORACLE | YES | S1 | oracle checks | merged into B2 | BOUND |
""",
        encoding="utf-8",
    )

    assert expected_breadth_artifacts(scratch) == [
        "analysis_core_state.md",
        "analysis_access_control.md",
    ]


def test_breadth_validator_requires_every_manifest_output(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_access_control.md | QUEUED |
""",
        encoding="utf-8",
    )
    (scratch / "analysis_core_state.md").write_text(
        "x" * BREADTH_MIN_BYTES,
        encoding="utf-8",
    )
    (scratch / "analysis_extra.md").write_text(
        "x" * BREADTH_MIN_BYTES,
        encoding="utf-8",
    )

    issues = validate_phase_artifacts("breadth", scratch, [])

    assert any("missing breadth artifact: analysis_access_control.md" in issue for issue in issues)


def test_breadth_validator_rejects_stub_and_forbidden_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )
    (scratch / "analysis_core_state.md").write_text("too short", encoding="utf-8")
    (scratch / "verify_core.md").write_text("overreach", encoding="utf-8")

    issues = validate_phase_artifacts("breadth", scratch, [])

    assert any("stub breadth artifact: analysis_core_state.md" in issue for issue in issues)
    assert any("forbidden later-phase artifact" in issue for issue in issues)


def test_first_pass_breadth_issues_allow_existing_rescan_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )
    (scratch / "analysis_core_state.md").write_text(
        "x" * BREADTH_MIN_BYTES,
        encoding="utf-8",
    )
    (scratch / "analysis_rescan_gap_review.md").write_text(
        "x" * RESCAN_MIN_BYTES,
        encoding="utf-8",
    )

    assert first_pass_breadth_issues(scratch) == []


def test_rescan_validator_requires_owned_families_and_substantial_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )
    (scratch / "analysis_core_state.md").write_text(
        "x" * BREADTH_MIN_BYTES,
        encoding="utf-8",
    )
    (scratch / "analysis_rescan_gap_review.md").write_text("too short", encoding="utf-8")

    issues = validate_phase_artifacts("rescan", scratch, [])

    assert any("missing per-contract artifact family" in issue for issue in issues)
    assert any("stub rescan artifact: analysis_rescan_gap_review.md" in issue for issue in issues)


def test_rescan_validator_rejects_duplicate_and_forbidden_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    scratch.mkdir()
    first_pass_body = "# First pass\n\n" + ("same finding body " * BREADTH_MIN_BYTES)
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )
    (scratch / "analysis_core_state.md").write_text(first_pass_body, encoding="utf-8")
    (scratch / "analysis_rescan_duplicate.md").write_text(first_pass_body, encoding="utf-8")
    (scratch / "analysis_percontract_scope_review.md").write_text(
        "x" * RESCAN_MIN_BYTES,
        encoding="utf-8",
    )
    (scratch / "analysis_unowned_extra.md").write_text(
        "x" * RESCAN_MIN_BYTES,
        encoding="utf-8",
    )
    (scratch / "verify_core.md").write_text("downstream", encoding="utf-8")

    issues = validate_phase_artifacts("rescan", scratch, [])

    assert any("duplicates first-pass breadth output" in issue for issue in issues)
    assert any("outside rescan-owned families" in issue for issue in issues)
    assert any("analysis_unowned_extra.md" in issue for issue in issues)
    assert any("verify_core.md" in issue for issue in issues)


def _write_inventory_prerequisites(scratch):
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
| AGENT | ACCESS_CONTROL | YES | B2 | access_control | analysis_access_control.md | QUEUED |
""",
        encoding="utf-8",
    )
    for name in expected_breadth_artifacts(scratch):
        (scratch / name).write_text(
            f"# {name}\n\n" + ("breadth evidence " * BREADTH_MIN_BYTES),
            encoding="utf-8",
        )
    (scratch / "analysis_rescan_gap_review.md").write_text(
        "# Rescan\n\n" + ("rescan evidence " * RESCAN_MIN_BYTES),
        encoding="utf-8",
    )
    (scratch / "analysis_percontract_scope_review.md").write_text(
        "# Per contract\n\n" + ("per contract evidence " * RESCAN_MIN_BYTES),
        encoding="utf-8",
    )


def _valid_inventory_body(source_files: list[str]) -> str:
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


def _valid_invariants_body() -> str:
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


def _valid_depth_body(title: str, finding_id: str = "[DT-1]") -> str:
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


def _valid_confidence_body() -> str:
    return (
        "# Confidence Scores\n\n"
        "| Finding ID | Confidence | Rationale |\n"
        "|------------|------------|-----------|\n"
        "| [DT-1] | Medium | Evidence references support a plausible issue. |\n\n"
        + ("Confidence evidence. " * DEPTH_MIN_BYTES)
    )


def _write_depth_outputs(scratch, mode: str = "core", aliases: dict[str, str] | None = None):
    aliases = aliases or {}
    for group in expected_depth_artifact_groups(mode):
        name = aliases.get(group[0], group[0])
        if name == "confidence_scores.md":
            (scratch / name).write_text(_valid_confidence_body(), encoding="utf-8")
        else:
            (scratch / name).write_text(
                _valid_depth_body(name.replace("_", " ").replace(".md", "").title()),
                encoding="utf-8",
            )


def test_inventory_source_files_are_authoritative_discovery_set(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)
    (scratch / "analysis_extra.md").write_text("ignored", encoding="utf-8")
    (scratch / "verify_core.md").write_text("ignored", encoding="utf-8")

    assert inventory_source_files(scratch) == [
        "analysis_core_state.md",
        "analysis_access_control.md",
        "analysis_percontract_scope_review.md",
        "analysis_rescan_gap_review.md",
    ]
    assert expected_inventory_artifacts(scratch) == ["findings_inventory.md"]


def test_inventory_source_size_gate_fails_closed(tmp_path, monkeypatch):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)
    monkeypatch.setattr(artifacts_module, "INVENTORY_MAX_SOURCE_FILES", 1)

    assert inventory_source_size_issues(scratch) == [INVENTORY_SOURCE_TOO_LARGE]

    monkeypatch.setattr(artifacts_module, "INVENTORY_MAX_SOURCE_FILES", 99)
    monkeypatch.setattr(artifacts_module, "INVENTORY_MAX_SOURCE_BYTES", 1)

    assert inventory_source_size_issues(scratch) == [INVENTORY_SOURCE_TOO_LARGE]


def test_inventory_validator_accepts_structurally_complete_inventory(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)
    (scratch / "findings_inventory.md").write_text(
        _valid_inventory_body(inventory_source_files(scratch)),
        encoding="utf-8",
    )

    assert validate_phase_artifacts("inventory", scratch, []) == []


def test_inventory_validator_requires_sections_fields_and_source_accounting(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)
    (scratch / "findings_inventory.md").write_text(
        "# Findings Inventory\n\n## Source Summary\n\nanalysis_core_state.md\n\n"
        + ("x" * INVENTORY_MIN_BYTES),
        encoding="utf-8",
    )

    issues = validate_phase_artifacts("inventory", scratch, [])

    assert any("missing required section: Master Table" in issue for issue in issues)
    assert any("missing required field label: Finding ID" in issue for issue in issues)
    assert any("missing discovery source: analysis_access_control.md" in issue for issue in issues)


def test_inventory_validator_rejects_legacy_shards_and_later_phase_files(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)
    (scratch / "findings_inventory.md").write_text(
        _valid_inventory_body(inventory_source_files(scratch)),
        encoding="utf-8",
    )
    (scratch / "inventory_shard_plan.md").write_text("legacy shard", encoding="utf-8")
    (scratch / "inventory_chunk_a.manifest.md").write_text("legacy manifest", encoding="utf-8")
    (scratch / "findings_inventory_chunk_a.md").write_text("legacy chunk", encoding="utf-8")
    (scratch / "depth_token_flow.md").write_text("downstream", encoding="utf-8")
    (scratch / "verify_core.md").write_text("downstream", encoding="utf-8")

    issues = validate_phase_artifacts("inventory", scratch, [])

    assert any("forbidden later-phase or legacy" in issue for issue in issues)
    assert any("inventory_shard_plan.md" in issue for issue in issues)
    assert any("findings_inventory_chunk_a.md" in issue for issue in issues)
    assert any("verify_core.md" in issue for issue in issues)


def _write_invariants_prerequisites(scratch):
    _write_inventory_prerequisites(scratch)
    (scratch / "findings_inventory.md").write_text(
        _valid_inventory_body(inventory_source_files(scratch)),
        encoding="utf-8",
    )
    (scratch / "state_variables.md").write_text(
        "# State Variables\n\n| Variable | Contract | Meaning |\n|----------|----------|---------|\n| totalAssets | Vault | managed assets |\n",
        encoding="utf-8",
    )
    (scratch / "function_list.md").write_text(
        "# Function List\n\n| Function | Contract | Purpose |\n|----------|----------|---------|\n| deposit | Vault | add assets |\n",
        encoding="utf-8",
    )


def test_invariants_prerequisite_issues_require_inventory_and_recon_inputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_inventory_prerequisites(scratch)

    issues = invariants_prerequisite_issues(scratch)

    assert any("missing inventory artifact: findings_inventory.md" in issue for issue in issues)
    assert any("missing invariants input artifact: state_variables.md" in issue for issue in issues)
    assert any("missing invariants input artifact: function_list.md" in issue for issue in issues)


def test_invariants_validator_accepts_structurally_complete_artifact(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    (scratch / "semantic_invariants.md").write_text(
        _valid_invariants_body(),
        encoding="utf-8",
    )

    assert expected_invariants_artifacts(scratch) == ["semantic_invariants.md"]
    assert validate_phase_artifacts("invariants", scratch, []) == []


def test_invariants_validator_requires_sections_fields_and_size(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    (scratch / "semantic_invariants.md").write_text("too short", encoding="utf-8")

    issues = validate_phase_artifacts("invariants", scratch, [])

    assert any("stub invariants artifact: semantic_invariants.md" in issue for issue in issues)

    (scratch / "semantic_invariants.md").write_text(
        "# Semantic Invariants\n\n## Main Table\n\nVariable\n"
        + ("x" * INVARIANTS_MIN_BYTES),
        encoding="utf-8",
    )

    issues = validate_phase_artifacts("invariants", scratch, [])

    assert any(
        "semantic_invariants.md missing required section: Mirror Variable Pairs" in issue
        for issue in issues
    )
    assert any(
        "semantic_invariants.md missing required field label: Contract/Module" in issue
        for issue in issues
    )


def test_invariants_validator_rejects_downstream_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    (scratch / "semantic_invariants.md").write_text(
        _valid_invariants_body(),
        encoding="utf-8",
    )
    (scratch / "invariant_fuzz_results.md").write_text("fuzz", encoding="utf-8")
    (scratch / "depth_token_flow_findings.md").write_text("depth", encoding="utf-8")
    (scratch / "verify_core.md").write_text("verify", encoding="utf-8")

    issues = validate_phase_artifacts("invariants", scratch, [])

    assert any("forbidden downstream artifact" in issue for issue in issues)
    assert any("invariant_fuzz_results.md" in issue for issue in issues)
    assert any("depth_token_flow_findings.md" in issue for issue in issues)
    assert any("verify_core.md" in issue for issue in issues)


def test_expected_depth_artifact_groups_are_mode_aware():
    light = expected_depth_artifact_groups("light")
    core = expected_depth_artifact_groups("core")
    thorough = expected_depth_artifact_groups("thorough")

    assert ["depth_token_flow_findings.md"] in light
    assert ["confidence_scores.md"] not in light
    assert ["confidence_scores.md"] in core
    assert ["design_stress_findings.md", "depth_design_stress_findings.md"] in thorough
    assert ["skill_execution_gaps.md", "skill_execution_checklist.md"] in thorough


def test_depth_prerequisites_are_mode_aware(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)

    light_issues = depth_prerequisite_issues(scratch, "light")
    core_issues = depth_prerequisite_issues(scratch, "core")

    assert not any("semantic_invariants.md" in issue for issue in light_issues)
    assert any("missing invariants artifact: semantic_invariants.md" in issue for issue in core_issues)

    (scratch / "semantic_invariants.md").write_text(
        _valid_invariants_body(),
        encoding="utf-8",
    )

    assert depth_prerequisite_issues(scratch, "core") == []


def test_depth_validator_accepts_light_outputs_without_invariants(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    _write_depth_outputs(scratch, "light")

    assert validate_phase_artifacts("depth", scratch, [], mode="light") == []


def test_depth_validator_accepts_alias_groups(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    (scratch / "semantic_invariants.md").write_text(
        _valid_invariants_body(),
        encoding="utf-8",
    )
    _write_depth_outputs(
        scratch,
        "thorough",
        aliases={
            "validation_sweep_findings.md": "scanner_validation_findings.md",
            "design_stress_findings.md": "depth_design_stress_findings.md",
            "perturbation_findings.md": "depth_perturbation_findings.md",
            "skill_execution_gaps.md": "skill_execution_checklist.md",
        },
    )

    assert validate_phase_artifacts("depth", scratch, [], mode="thorough") == []


def test_depth_validator_rejects_missing_stub_incomplete_and_forbidden_outputs(tmp_path):
    scratch = tmp_path / ".lg_scratchpad"
    _write_invariants_prerequisites(scratch)
    (scratch / "semantic_invariants.md").write_text(
        _valid_invariants_body(),
        encoding="utf-8",
    )
    _write_depth_outputs(scratch, "core")
    (scratch / "depth_edge_case_findings.md").write_text("too short", encoding="utf-8")
    (scratch / "depth_external_findings.md").write_text(
        "# External\n\nEvidence only.\n" + ("x" * DEPTH_MIN_BYTES),
        encoding="utf-8",
    )
    (scratch / "rag_validation.md").write_text("downstream", encoding="utf-8")
    (scratch / "_v2_checkpoint.json").write_text("{}", encoding="utf-8")

    issues = validate_phase_artifacts("depth", scratch, [], mode="core")

    assert any("stub depth artifact: depth_edge_case_findings.md" in issue for issue in issues)
    assert any("depth_external_findings.md missing investigated candidates" in issue for issue in issues)
    assert any("forbidden downstream or legacy" in issue for issue in issues)
    assert any("rag_validation.md" in issue for issue in issues)
    assert any("_v2_checkpoint.json" in issue for issue in issues)
