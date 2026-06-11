from __future__ import annotations

import hashlib

from plamen_langgraph.plamen_lg.artifacts import (
    check_artifacts,
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
