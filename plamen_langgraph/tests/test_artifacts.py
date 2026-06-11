from __future__ import annotations

import hashlib

from plamen_langgraph.plamen_lg.artifacts import (
    BREADTH_MIN_BYTES,
    RESCAN_MIN_BYTES,
    check_artifacts,
    expected_breadth_artifacts,
    first_pass_breadth_issues,
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
