from __future__ import annotations

from plamen_langgraph.plamen_lg import phases as phase_module
from plamen_langgraph.plamen_lg.config import build_config
from plamen_langgraph.plamen_lg.phases import (
    build_breadth_prompt,
    build_depth_prompt,
    build_instantiate_prompt,
    build_invariants_prompt,
    build_inventory_prompt,
    build_recon_prompt,
    build_rescan_prompt,
    expected_phase_artifacts,
    expected_recon_artifacts,
    get_phase,
    get_recon_phase,
)


def test_langgraph_methodology_prompts_are_local_to_langgraph():
    root = phase_module._repo_root()
    readers = {
        "phase2-instantiate.md": phase_module._read_phase2_methodology,
        "phase3-breadth.md": phase_module._read_phase3_methodology,
        "phase4-rescan.md": phase_module._read_phase4_methodology,
    }

    for filename, reader in readers.items():
        langgraph_path = phase_module._langgraph_prompt_path(filename)
        legacy_path = root / "prompts" / "shared" / "v2" / filename

        assert "plamen_langgraph/prompts" in langgraph_path.as_posix()
        assert langgraph_path.exists()
        assert legacy_path.exists()
        assert reader() == langgraph_path.read_text(encoding="utf-8")


def test_inventory_methodology_is_langgraph_owned():
    langgraph_path = phase_module._langgraph_prompt_path("phase5-inventory.md")
    shared_path = (
        phase_module._repo_root()
        / "prompts"
        / "shared"
        / "v2"
        / "phase4a-inventory-base.md"
    )

    assert "plamen_langgraph/prompts" in langgraph_path.as_posix()
    assert langgraph_path.exists()
    assert shared_path.exists()
    assert phase_module._read_inventory_methodology() == langgraph_path.read_text(
        encoding="utf-8"
    )
    assert phase_module._read_inventory_methodology() != shared_path.read_text(
        encoding="utf-8"
    )


def test_invariants_methodology_is_langgraph_owned():
    langgraph_path = phase_module._langgraph_prompt_path("phase6-invariants.md")
    shared_path = (
        phase_module._repo_root()
        / "prompts"
        / "shared"
        / "v2"
        / "phase4a5-invariants.md"
    )

    assert "plamen_langgraph/prompts" in langgraph_path.as_posix()
    assert langgraph_path.exists()
    assert shared_path.exists()
    assert phase_module._read_invariants_methodology() == langgraph_path.read_text(
        encoding="utf-8"
    )
    assert phase_module._read_invariants_methodology() != shared_path.read_text(
        encoding="utf-8"
    )


def test_depth_methodology_is_langgraph_owned():
    langgraph_path = phase_module._langgraph_prompt_path("phase7-depth.md")
    shared_path = (
        phase_module._repo_root()
        / "prompts"
        / "shared"
        / "v2"
        / "phase4b-depth.md"
    )

    assert "plamen_langgraph/prompts" in langgraph_path.as_posix()
    assert langgraph_path.exists()
    assert shared_path.exists()
    assert phase_module._read_depth_methodology() == langgraph_path.read_text(
        encoding="utf-8"
    )
    assert phase_module._read_depth_methodology() != shared_path.read_text(
        encoding="utf-8"
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


def test_langgraph_breadth_prompt_uses_direct_manifest_methodology(tmp_path):
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
    assert "Phase 3: Manifest-Exact Breadth Analysis" in prompt
    assert "`spawn_manifest.md` is authoritative" in prompt
    assert "`analysis_core_state.md`" in prompt
    assert "Do not run re-scan, per-contract review, inventory" in prompt
    assert "Do not write `analysis_rescan_*.md`" in prompt
    assert "Available parallel worker tools are optional" in prompt
    assert "V2 driver's Phase 3 subprocess" not in prompt
    assert "Task calls" not in prompt
    assert "Every Task prompt" not in prompt
    assert "close completed agents" not in prompt
    assert "Mode-Specific Agent Counts" not in prompt
    assert "opus" not in prompt
    assert "sonnet" not in prompt
    assert "haiku" not in prompt
    assert "Claude" not in prompt
    assert "_v2_checkpoint.json" in prompt


def test_rescan_phase_metadata_is_langgraph_owned():
    phase = get_phase("rescan", "sc")

    assert phase.name == "rescan"
    assert phase.section_markers == ["LangGraph rescan"]
    assert expected_phase_artifacts("rescan") == [
        "analysis_rescan_*.md",
        "analysis_percontract_*.md",
    ]


def test_langgraph_rescan_prompt_uses_direct_mandatory_methodology(tmp_path):
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
    config = build_config(project, language="evm", mode="core").to_dict()

    prompt = build_rescan_prompt(config)

    assert prompt.startswith("# Plamen LangGraph Rescan Direct-Execution Prompt")
    assert "LangGraph Rescan: Mandatory Additional Discovery" in prompt
    assert "`analysis_core_state.md`" in prompt
    assert "This phase is mandatory after successful first-pass breadth" in prompt
    assert "Do not call Task, launch subagents, or delegate work" in prompt
    assert "Write only `analysis_rescan_*.md`, `analysis_percontract_*.md`" in prompt
    assert "Do not write new first-pass `analysis_*.md` files" in prompt
    assert "Primary outputs owned by this phase" in prompt
    assert "V2 driver's `rescan` subprocess" not in prompt
    assert "Task(" not in prompt
    assert "_v2_checkpoint.json" in prompt


def test_inventory_phase_metadata_is_langgraph_owned():
    phase = get_phase("inventory", "sc")

    assert phase.name == "inventory"
    assert phase.section_markers == ["LangGraph inventory"]
    assert expected_phase_artifacts("inventory") == ["findings_inventory.md"]


def test_langgraph_inventory_prompt_uses_single_phase_methodology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratch = project / ".lg_scratchpad"
    scratch.mkdir()
    (scratch / "analysis_core_state.md").write_text("breadth", encoding="utf-8")
    (scratch / "analysis_rescan_gap_review.md").write_text("rescan", encoding="utf-8")
    config = build_config(project, language="evm", mode="core").to_dict()

    prompt = build_inventory_prompt(
        config,
        source_files=["analysis_core_state.md", "analysis_rescan_gap_review.md"],
    )

    assert prompt.startswith("# Plamen LangGraph Inventory Direct-Execution Prompt")
    assert "LangGraph Inventory: Single-Phase Consolidation" in prompt
    assert "`analysis_core_state.md`" in prompt
    assert "`analysis_rescan_gap_review.md`" in prompt
    assert "Required output artifact: `findings_inventory.md`" in prompt
    assert "The source list below is authoritative" in prompt
    assert "Write only `findings_inventory.md`, `violations.md`" in prompt
    assert "Do not write `findings_inventory_chunk_*.md`" in prompt
    assert "Do not run semantic invariants, depth, RAG, chain" in prompt
    assert "Do not call Task, launch subagents" in prompt
    assert "_v2_checkpoint.json" in prompt


def test_invariants_phase_metadata_is_langgraph_owned():
    phase = get_phase("invariants", "sc")

    assert phase.name == "invariants"
    assert phase.section_markers == ["LangGraph invariants"]
    assert expected_phase_artifacts("invariants") == ["semantic_invariants.md"]
    assert phase.critical is False


def test_langgraph_invariants_prompt_uses_pass1_methodology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, language="evm", mode="core").to_dict()

    prompt = build_invariants_prompt(config)

    assert prompt.startswith("# Plamen LangGraph Invariants Direct-Execution Prompt")
    assert "LangGraph Invariants: Semantic Invariant Pass 1" in prompt
    assert "Required output artifact: `semantic_invariants.md`" in prompt
    assert "Execute semantic invariant Pass 1 only" in prompt
    assert "Do not execute Thorough Pass 2" in prompt
    assert "Do not call Task, launch subagents" in prompt
    assert "Write only `semantic_invariants.md`, `violations.md`" in prompt
    assert "Do not write `invariant_fuzz_results.md`" in prompt
    assert "findings_inventory.md" in prompt
    assert "state_variables.md" in prompt
    assert "function_list.md" in prompt
    assert "_v2_checkpoint.json" in prompt


def test_depth_phase_metadata_is_langgraph_owned():
    phase = get_phase("depth", "sc")

    assert phase.name == "depth"
    assert phase.section_markers == ["LangGraph depth"]
    assert expected_phase_artifacts("depth") == ["depth_*_findings.md"]
    assert phase.base_timeout_s == 7200


def test_langgraph_depth_prompt_uses_mode_aware_direct_methodology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config = build_config(project, language="evm", mode="thorough").to_dict()

    prompt = build_depth_prompt(config)

    assert prompt.startswith("# Plamen LangGraph Depth Direct-Execution Prompt")
    assert "LangGraph Depth: Direct Adaptive Boundary" in prompt
    assert "`findings_inventory.md`" in prompt
    assert "`semantic_invariants.md`" in prompt
    assert "`depth_token_flow_findings.md`" in prompt
    assert "`confidence_scores.md`" in prompt
    assert "`design_stress_findings.md` or `depth_design_stress_findings.md`" in prompt
    assert "Do not call Task, launch subagents" in prompt
    assert "Do not write `rag_validation.md`" in prompt
    assert "role/title heading" in prompt
    assert "_v2_checkpoint.json" in prompt
