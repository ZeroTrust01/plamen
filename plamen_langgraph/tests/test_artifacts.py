from __future__ import annotations

import hashlib

from plamen_langgraph.plamen_lg.artifacts import check_artifacts


def test_artifact_checker_records_present_and_missing(tmp_path):
    scratch = tmp_path / ".scratchpad"
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

