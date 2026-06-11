from __future__ import annotations

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.phases import (
    build_recon_prompt,
    expected_recon_artifacts,
    get_recon_phase,
)


def test_langgraph_recon_prompt_is_direct_exec(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
    config = build_config(project, language="evm").to_dict()

    prompt = build_recon_prompt(config)

    assert prompt.startswith("# Plamen LangGraph Recon Direct-Execution Prompt")
    assert "generated directly by `plamen_langgraph`" in prompt
    assert "Do not spawn subagents" in prompt
    assert "Task(subagent_type=" not in prompt
    assert "ORCHESTRATOR SPLIT DIRECTIVE" not in prompt
    assert "BEGIN STANDALONE V2 PHASE PROMPT" not in prompt
    assert "Legacy prompt builder unavailable" not in prompt
    assert "Phase 2 should reuse the production prompt builder" not in prompt
    assert "{network_if_provided}" not in prompt
    assert "{scope_notes_if_provided}" not in prompt
    assert "per \u00c2\u00a7WRITE-THEN-VERIFY" not in prompt


def test_langgraph_recon_prompt_lists_gate_artifacts(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, language="evm").to_dict()

    prompt = build_recon_prompt(config)

    for name in expected_recon_artifacts():
        assert f"`{name}`" in prompt


def test_recon_phase_metadata_is_langgraph_owned():
    phase = get_recon_phase("sc")

    assert phase.name == "recon"
    assert phase.section_markers == ["LangGraph direct recon"]
    assert phase.expected_artifacts == expected_recon_artifacts()
