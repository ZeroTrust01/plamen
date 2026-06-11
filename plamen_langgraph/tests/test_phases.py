from __future__ import annotations

from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.phases import (
    build_breadth_prompt,
    build_instantiate_prompt,
    build_recon_prompt,
    expected_phase_artifacts,
    expected_recon_artifacts,
    get_phase,
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


def test_instantiate_phase_metadata_uses_canonical_sc_phase():
    phase = get_phase("instantiate", "sc")

    assert phase.name == "instantiate"
    assert phase.section_markers == ["Phase 2: Orchestrator Instantiation"]
    assert expected_phase_artifacts("instantiate") == ["spawn_manifest.md"]


def test_langgraph_instantiate_prompt_uses_direct_manifest_methodology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, language="evm").to_dict()

    prompt = build_instantiate_prompt(config)

    assert prompt.startswith("# Plamen LangGraph Instantiate Direct-Execution Prompt")
    assert "Phase 2: Manifest Instantiation" in prompt
    assert "## Step 2f: Self-Check" in prompt
    assert "`spawn_manifest.md` must be a machine-readable Markdown contract" in prompt
    assert "Do not call Task, launch subagents, or create breadth outputs" in prompt
    assert "Do not load external prompt files, agent definitions, skill files" in prompt
    assert "Task(subagent_type=" not in prompt
    assert "V2 driver's Phase 2 subprocess" not in prompt
    assert "BEFORE spawning agents" not in prompt
    assert "SKILL.md" not in prompt
    assert "~/.codex/plamen" not in prompt
    assert "MCP Timeout Directive" not in prompt
    assert "Skill Bindings" not in prompt
    assert "_v2_checkpoint.json" in prompt


def test_breadth_phase_metadata_uses_canonical_sc_phase():
    phase = get_phase("breadth", "sc")

    assert phase.name == "breadth"
    assert phase.section_markers == ["Phase 3: Parallel Analysis"]
    assert expected_phase_artifacts("breadth") == ["analysis_*.md"]


def test_langgraph_breadth_prompt_wraps_phase3_methodology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = project / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "spawn_manifest.md").write_text(
        """# Spawn Manifest

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |
""",
        encoding="utf-8",
    )
    config = build_config(project, language="evm").to_dict()

    prompt = build_breadth_prompt(config, open_outputs=["analysis_core_state.md"])

    assert prompt.startswith("# Plamen LangGraph Breadth Direct-Execution Prompt")
    assert "Phase 3: Parallel Breadth Analysis" in prompt
    assert "`spawn_manifest.md` is authoritative" in prompt
    assert "`analysis_core_state.md`" in prompt
    assert "Do not run re-scan, per-contract review, inventory" in prompt
    assert "Do not write `analysis_rescan_*.md`" in prompt
    assert "_v2_checkpoint.json" in prompt
