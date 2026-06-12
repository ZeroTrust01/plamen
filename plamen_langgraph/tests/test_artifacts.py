from __future__ import annotations

import hashlib

from plamen_langgraph.plamen_lg import artifacts as artifacts_module
from plamen_langgraph.plamen_lg.artifacts import (
    BREADTH_MIN_BYTES,
    INVENTORY_MIN_BYTES,
    INVENTORY_SOURCE_TOO_LARGE,
    RESCAN_MIN_BYTES,
    check_artifacts,
    expected_breadth_artifacts,
    expected_inventory_artifacts,
    first_pass_breadth_issues,
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
