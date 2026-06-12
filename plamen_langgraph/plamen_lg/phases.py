from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Any

from .artifacts import (
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
    rescan_outputs,
)


RECON_ARTIFACTS = [
    "recon_summary.md",
    "design_context.md",
    "attack_surface.md",
    "state_variables.md",
    "function_list.md",
    "contract_inventory.md",
    "template_recommendations.md",
    "detected_patterns.md",
    "setter_list.md",
    "emit_list.md",
    "build_status.md",
]


@dataclass(frozen=True)
class SimplePhase:
    name: str
    section_markers: list[str]
    expected_artifacts: list[str]
    base_timeout_s: int
    critical: bool = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _langgraph_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _langgraph_prompt_path(filename: str) -> Path:
    return _langgraph_root() / "prompts" / filename


def _load_sc_phases() -> list[Any] | None:
    scripts_dir = _repo_root() / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from plamen_types import SC_PHASES  # type: ignore
    except Exception:
        return None
    return list(SC_PHASES)


def _none_if_blank(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "(none)"


def _render_required_artifacts() -> str:
    rows = [
        (
            "recon_summary.md",
            "Clean handoff with target, scope, language, key components, "
            "risk themes, selected templates, build status, and artifact list.",
        ),
        (
            "design_context.md",
            "Protocol purpose, actors, trust assumptions, core invariants, "
            "and operational implications.",
        ),
        (
            "attack_surface.md",
            "Externally callable flows, privileged flows, cross-contract and "
            "external dependency surfaces, and high-risk state transitions.",
        ),
        (
            "state_variables.md",
            "Important storage variables grouped by contract with meaning, "
            "writers, readers, constraints, and accounting role.",
        ),
        (
            "function_list.md",
            "In-scope functions with contract, visibility, mutability, access "
            "control, key state reads/writes, external calls, and purpose.",
        ),
        (
            "contract_inventory.md",
            "In-scope contracts/interfaces/libraries with path, inheritance, "
            "upgradeability/proxy role, and security relevance.",
        ),
        (
            "template_recommendations.md",
            "Detected analysis lanes and required templates with trigger, "
            "reason, instantiation parameters, and binding manifest.",
        ),
        (
            "detected_patterns.md",
            "Pattern flags such as ORACLE, ERC4626, CROSS_CHAIN, HAS_SIGNATURES, "
            "STORAGE_LAYOUT, MIXED_DECIMALS, TEMPORAL, and NOT DETECTED entries.",
        ),
        (
            "setter_list.md",
            "Admin/configuration setters and permissionless state modifiers, "
            "including role, state changed, bounds, and event coverage.",
        ),
        (
            "emit_list.md",
            "Events and emit sites with contract, function, parameters, and "
            "missing-event observations for state changes.",
        ),
        (
            "build_status.md",
            "Framework detection, commands attempted, build/test/static-analysis "
            "availability, dependency state, and explicit skip/failure reasons.",
        ),
    ]
    return "\n".join(f"- `{name}`: {description}" for name, description in rows)


def get_recon_phase(pipeline: str = "sc") -> Any:
    if pipeline != "sc":
        raise ValueError("Phase 1 supports only SC recon")
    return SimplePhase(
        name="recon",
        section_markers=[
            "LangGraph direct recon",
        ],
        expected_artifacts=list(RECON_ARTIFACTS),
        base_timeout_s=3000,
        critical=True,
    )


def get_phase(name: str, pipeline: str = "sc") -> Any:
    if pipeline != "sc":
        raise ValueError("LangGraph Phase 2 supports only the smart-contract pipeline: sc")
    if name == "rescan":
        return SimplePhase(
            name="rescan",
            section_markers=["LangGraph rescan"],
            expected_artifacts=["analysis_rescan_*.md", "analysis_percontract_*.md"],
            base_timeout_s=4800,
            critical=True,
        )
    if name == "inventory":
        return SimplePhase(
            name="inventory",
            section_markers=["LangGraph inventory"],
            expected_artifacts=["findings_inventory.md"],
            base_timeout_s=3600,
            critical=True,
        )
    if name == "invariants":
        return SimplePhase(
            name="invariants",
            section_markers=["LangGraph invariants"],
            expected_artifacts=["semantic_invariants.md"],
            base_timeout_s=4800,
            critical=False,
        )
    if name == "depth":
        return SimplePhase(
            name="depth",
            section_markers=["LangGraph depth"],
            expected_artifacts=["depth_*_findings.md"],
            base_timeout_s=7200,
            critical=True,
        )
    phases = _load_sc_phases()
    if phases:
        for phase in phases:
            if phase.name == name:
                return phase

    if name == "recon":
        return get_recon_phase(pipeline)
    if name == "instantiate":
        return SimplePhase(
            name="instantiate",
            section_markers=["Phase 2: Orchestrator Instantiation"],
            expected_artifacts=["spawn_manifest.md"],
            base_timeout_s=600,
            critical=True,
        )
    if name == "breadth":
        return SimplePhase(
            name="breadth",
            section_markers=["Phase 3: Parallel Analysis"],
            expected_artifacts=["analysis_*.md"],
            base_timeout_s=10800,
            critical=True,
        )
    raise ValueError(f"unsupported LangGraph phase: {name}")


def expected_phase_artifacts(name: str, pipeline: str = "sc") -> list[str]:
    return list(get_phase(name, pipeline).expected_artifacts)


def _read_phase2_methodology() -> str:
    return _langgraph_prompt_path("phase2-instantiate.md").read_text(encoding="utf-8")


def _read_phase3_methodology() -> str:
    return _langgraph_prompt_path("phase3-breadth.md").read_text(encoding="utf-8")


def _read_phase4_methodology() -> str:
    return _langgraph_prompt_path("phase4-rescan.md").read_text(encoding="utf-8")


def _read_inventory_methodology() -> str:
    return _langgraph_prompt_path("phase5-inventory.md").read_text(encoding="utf-8")


def _read_invariants_methodology() -> str:
    return _langgraph_prompt_path("phase6-invariants.md").read_text(encoding="utf-8")


def _read_depth_methodology() -> str:
    return _langgraph_prompt_path("phase7-depth.md").read_text(encoding="utf-8")


def build_recon_prompt(config: dict[str, Any]) -> str:
    """Build a direct-execution prompt for the LangGraph recon worker.

    This intentionally avoids the legacy V1/V2 prompt builder. LangGraph runs a
    single `codex exec` subprocess, so the prompt must be executable directly
    and must not contain orchestrator-only Task templates or future-phase
    control flow.
    """
    phase = get_recon_phase(str(config.get("pipeline", "sc")))
    required_names = "\n".join(f"- `{name}`" for name in phase.expected_artifacts)
    required_contract = _render_required_artifacts()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    docs = _none_if_blank(
        config.get("docs_path")
        or config.get("docs_path_or_url_if_provided")
        or config.get("documentation")
    )
    scope_file = _none_if_blank(
        config.get("scope_file") or config.get("scope_file_if_provided")
    )
    scope_notes = _none_if_blank(
        config.get("scope_notes") or config.get("scope_notes_if_provided")
    )
    network = _none_if_blank(config.get("network") or config.get("network_if_provided"))
    subsystem_scope = _none_if_blank(config.get("subsystem_scope"))

    return f"""# Plamen LangGraph Recon Direct-Execution Prompt

You are running only the `recon` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; do not use
or infer instructions from legacy orchestrator prompts, V1 wizard flow, or
future phases.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Documentation: `{docs}`
- Scope file: `{scope_file}`
- Scope notes: `{scope_notes}`
- Network: `{network}`
- Subsystem scope: `{subsystem_scope}`

## Hard Scope

1. Execute recon only. Do not run breadth, inventory, depth, verification,
   scoring, report, or any later phase.
2. Do not spawn subagents. This is a single direct `codex exec` worker.
3. Write recon artifacts directly under the scratchpad path above.
4. Do not edit target source files, dependency manifests, Foundry/Hardhat
   configuration, git metadata, or dependency directories. Build tools may
   create normal cache/output directories, but do not apply fixes or install
   dependencies during recon.
5. Prefer bounded local inspection with `rg`, `find`, `ls`, and line-bounded
   file reads. Exclude `.git`, `.lg_scratchpad`, `.scratchpad`, `out`,
   `cache`, `node_modules`, and vendored dependency directories from broad
   source surveys unless needed to identify imports.
6. If a tool, dependency, build, MCP server, network lookup, or external
   service is unavailable, record `UNAVAILABLE` with the exact reason and
   continue. Do not retry unavailable tools more than once.

## Required Output Contract

Create or refresh every required artifact below. Each file must contain
substantive best-known content. It may include `UNAVAILABLE` or `NOT DETECTED`
when accurate, but it must not contain TODO, TBD, placeholder tokens,
draft-only markers, or empty sections.

Required files:
{required_names}

Artifact content contract:
{required_contract}

Optional helper files are allowed only after the required files are on track:
`meta_buffer.md`, `call_graph.md`, `caller_map.md`, `callee_map.md`,
`state_write_map.md`, `function_summary.md`, `static_analysis.md`,
`test_results.md`, `event_definitions.md`, `external_interfaces.md`,
`modifiers.md`, and `constraint_variables.md`. These helper files do not
replace the required files.

## Execution Plan

1. Confirm the scratchpad exists and list any prior recon artifacts. Treat
   existing files as seeds, not as authoritative final output.
2. Inspect repository shape and scope:
   - detect framework and language;
   - identify in-scope source roots and obvious excluded/vendor roots;
   - count contracts and approximate source size;
   - read README, config, remappings, package files, and deployment/config
     files when present.
3. Produce or refresh mechanical recon:
   - contract inventory;
   - function list;
   - state variable map;
   - event/emit list;
   - setter/admin list.
4. Produce interpretive recon:
   - design context and trust model;
   - attack surface and external dependencies;
   - detected patterns and recommended analysis templates.
5. Build/static-analysis status:
   - detect Foundry or Hardhat;
   - run a bounded build command only if dependencies are already present and
     the command is likely to complete;
   - do not install missing dependencies or modify config to make the build
     pass;
   - record command, result, stdout/stderr summary, and reason for any skip.
6. Finalize `recon_summary.md` last. It must list all produced artifacts and
   clearly state remaining recon limitations.

## Pattern Checklist

Check for these patterns and record YES/NO/UNAVAILABLE in
`detected_patterns.md` with evidence paths:

- ORACLE: Chainlink, TWAP, price feeds, sequencer uptime, staleness/deviation.
- ERC4626 or share accounting: deposit, mint, withdraw, redeem, shares,
  virtual balances, rewards, first depositor behavior.
- CROSS_CHAIN or CROSS_CHAIN_MSG: LayerZero, OFT/OApp, CCIP, bridge peers,
  lzReceive, compose, refund, send/receive paths.
- HAS_SIGNATURES: EIP-712, ECDSA, ecrecover, permit, nonces, domain separator.
- STORAGE_LAYOUT: proxy, UUPS, upgradeable contracts, delegatecall, storage
  gaps, assembly storage access.
- ACCESS_CONTROL: roles, owner/admin/timelock, keeper/operator/custodian roles.
- MIXED_DECIMALS: 1e6, 1e8, 1e18, token decimals, feed decimals, mulDiv.
- TEMPORAL: deadlines, valid-until, periods, windows, vesting, delays.
- BALANCE_DEPENDENT: balanceOf(this), direct donations, excess recovery.
- EXTERNAL_DEPENDENCY: tokens, Aave/DEX/vaults, sanctions providers, oracles.
- BATCH_OR_QUEUE: loops over token IDs, pending ranges, withdrawal queues.
- PAUSE_FREEZE_SANCTIONS: transfer restrictions, blocked users, quarantine.

## Return

After all required artifacts are written, return exactly one concise summary:
`RECON COMPLETE: <contract_count> contracts, <dependency_count> dependencies, <template_count> templates recommended, limitations: <short list>`.
"""


def build_instantiate_prompt(config: dict[str, Any]) -> str:
    """Build a direct-execution prompt for the LangGraph instantiate worker.

    The instantiate worker only translates recon artifacts into the
    `spawn_manifest.md` breadth contract. It must not inherit legacy
    orchestrator prompt behavior, compose subagent prompts, or load skill files.
    """
    phase = get_phase("instantiate", str(config.get("pipeline", "sc")))
    methodology = _read_phase2_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    required_recon = "\n".join(f"- `{name}`" for name in expected_recon_artifacts())
    required_outputs = "\n".join(f"- `{name}`" for name in phase.expected_artifacts)

    return f"""# Plamen LangGraph Instantiate Direct-Execution Prompt

You are running only the `instantiate` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
manifest planning procedure below only to produce the `spawn_manifest.md`
contract consumed by the breadth phase.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`

## Hard Scope

1. Execute instantiate only. Do not run breadth, inventory, depth,
   verification, scoring, report, or any later phase.
2. Do not call Task, launch subagents, or create breadth outputs.
3. Read recon artifacts from the scratchpad as inputs. Required recon inputs:
{required_recon}
4. Do not load external prompt files, agent definitions, skill files, MCP
   servers, network sources, legacy checkpoints, or installation-local paths.
5. Write only the required Phase 2 output and optional `_lg_` debug notes under
   the scratchpad.
6. Required Phase 2 outputs:
{required_outputs}
7. Do not edit target source files, dependency manifests, git metadata, legacy
   `.scratchpad`, or `_v2_checkpoint.json`.

## Output Contract

`spawn_manifest.md` must be a machine-readable Markdown contract. The first
Markdown table containing both `Template` and `Required?` columns must be the
breadth-agent AGENT table. Every `AGENT` row needs a unique agent identifier
and a distinct first-pass `analysis_*.md` expected output.
Do not include `verify_*.md`, `analysis_rescan_*.md`,
`analysis_percontract_*.md`, `analysis_merged_into_*.md`, inventory, depth,
chain, verification, scoring, or report artifacts in the AGENT table.

## Manifest Planning Procedure

{methodology}

## Return

After `spawn_manifest.md` is written and re-read for self-checking, return
exactly one concise summary:
`INSTANTIATE COMPLETE: <agent_count> breadth agents queued, manifest: spawn_manifest.md, limitations: <short list>`.
"""


def build_breadth_prompt(
    config: dict[str, Any],
    open_outputs: list[str] | None = None,
) -> str:
    """Build a direct-execution prompt for manifest-exact breadth work."""
    methodology = _read_phase3_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    expected_outputs = expected_breadth_artifacts(scratchpad)
    expected_list = (
        "\n".join(f"- `{name}`" for name in expected_outputs)
        if expected_outputs
        else "- `(none parsed; fail before running if this remains true)`"
    )
    open_list = (
        "\n".join(f"- `{name}`" for name in open_outputs)
        if open_outputs
        else "- `(none; all manifest-derived outputs are already substantial)`"
    )

    return f"""# Plamen LangGraph Breadth Direct-Execution Prompt

You are running only the `breadth` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
breadth execution procedure below only to produce manifest-derived first-pass
analysis outputs.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Required input artifact: `spawn_manifest.md`
- Breadth minimum output size: `{BREADTH_MIN_BYTES}` bytes

## Manifest-Derived Expected Outputs

`spawn_manifest.md` is authoritative. The breadth phase is complete only when
every file in this list exists under the scratchpad and is at least
`{BREADTH_MIN_BYTES}` bytes:

{expected_list}

## Current Open Outputs

Create or refresh only these missing/stub expected outputs during this run:

{open_list}

## Hard Scope

1. Execute breadth only. Do not run re-scan, per-contract review, inventory,
   semantic invariants, depth, RAG, chain analysis, verification, scoring,
   report index, report writing, or report assembly.
2. Read `spawn_manifest.md`, recon artifacts, and target source files as needed
   for breadth analysis.
3. Write only manifest-derived first-pass `analysis_*.md` outputs,
   `violations.md`, and optional `_lg_` debug notes under the scratchpad.
4. Do not write `analysis_rescan_*.md`, `analysis_percontract_*.md`,
   `analysis_merged_into_*.md`, inventory, depth, chain, verification,
   scoring, or report artifacts.
5. Do not edit target source files, dependency manifests, git metadata, legacy
   `.scratchpad`, or `_v2_checkpoint.json`.
6. Do not treat the manifest `Status` column as completion evidence. Completion
   comes from filesystem existence and size only.
7. Do not invent extra breadth output filenames. Non-manifest `analysis_*.md`
   files do not count toward completion.
8. Available parallel worker tools are optional. If no such tool is available,
   perform the open breadth analyses sequentially and still write exactly the
   manifest-derived outputs.

## Breadth Execution Procedure

{methodology}

## Return

After every manifest-derived output exists and is at least
`{BREADTH_MIN_BYTES}` bytes, return exactly one concise summary:
`BREADTH COMPLETE: <output_count> manifest outputs complete, limitations: <short list>`.
"""


def build_rescan_prompt(config: dict[str, Any]) -> str:
    """Build a direct-execution prompt for mandatory rescan work."""
    methodology = _read_phase4_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    first_pass_outputs = expected_breadth_artifacts(scratchpad)
    first_pass_list = (
        "\n".join(f"- `{name}`" for name in first_pass_outputs)
        if first_pass_outputs
        else "- `(none parsed; fail before running if this remains true)`"
    )
    existing_owned = rescan_outputs(scratchpad)
    existing_owned_list = (
        "\n".join(f"- `{name}`" for name in existing_owned)
        if existing_owned
        else "- `(none)`"
    )

    return f"""# Plamen LangGraph Rescan Direct-Execution Prompt

You are running only the `rescan` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
rescan procedure below only to produce bounded additional discovery outputs.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Required input artifact: `spawn_manifest.md`
- Rescan minimum output size: `{RESCAN_MIN_BYTES}` bytes

## First-Pass Exclusion Set

Read the first-pass breadth outputs listed below before writing new findings.
They are the exclusion set for this phase; do not duplicate their root causes,
locations, or same-location title variants.

{first_pass_list}

## Existing Rescan-Owned Outputs

On retry, existing substantial rescan-owned outputs may be preserved. Refresh
only when they are incomplete, stub-like, or materially wrong.

{existing_owned_list}

## Hard Scope

1. Execute rescan only. Do not run inventory, semantic invariants, depth, RAG,
   chain analysis, verification, scoring, report index, report writing, or
   report assembly.
2. This phase is mandatory after successful first-pass breadth in every mode.
   Do not skip it because the configured mode is `light` or `core`.
3. Do not call Task, launch subagents, or delegate work to other workers.
4. Read `spawn_manifest.md`, first-pass breadth outputs, recon artifacts, and
   target source files as needed for additional discovery.
5. Write only `analysis_rescan_*.md`, `analysis_percontract_*.md`,
   `violations.md`, and optional `_lg_` debug notes under the scratchpad.
6. Do not write new first-pass `analysis_*.md` files, inventory, depth, chain,
   verification, scoring, or report artifacts.
7. Do not edit target source files, dependency manifests, git metadata, legacy
   `.scratchpad`, or `_v2_checkpoint.json`.
8. Produce at least one `analysis_rescan_*.md` file and at least one
   `analysis_percontract_*.md` file. Each output must be substantive and at
   least `{RESCAN_MIN_BYTES}` bytes.

## Rescan Execution Procedure

{methodology}

## Return

After the additional discovery outputs are written and self-checked, return
exactly one concise summary:
`RESCAN COMPLETE: <rescan_count> rescan outputs, <percontract_count> per-contract outputs, limitations: <short list>`.
"""


def build_inventory_prompt(
    config: dict[str, Any],
    source_files: list[str] | None = None,
) -> str:
    """Build a direct-execution prompt for single-phase inventory synthesis."""
    methodology = _read_inventory_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    sources = (
        list(source_files)
        if source_files is not None
        else inventory_source_files(str(config.get("scratchpad") or ""))
    )
    source_list = (
        "\n".join(f"- `{name}`" for name in sources)
        if sources
        else "- `(none; fail before running if this remains true)`"
    )
    scratch_root = Path(str(config.get("scratchpad") or ""))
    total_source_bytes = 0
    for name in sources:
        path = scratch_root / name
        if path.is_file():
            total_source_bytes += path.stat().st_size

    return f"""# Plamen LangGraph Inventory Direct-Execution Prompt

You are running only the `inventory` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
inventory methodology below only to consolidate discovery outputs into one
canonical `findings_inventory.md`.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Required output artifact: `findings_inventory.md`
- Inventory minimum output size: `{INVENTORY_MIN_BYTES}` bytes
- Inventory source file count: `{len(sources)}`
- Inventory source byte total: `{total_source_bytes}`
- Inventory source file limit: `{INVENTORY_MAX_SOURCE_FILES}`
- Inventory source byte limit: `{INVENTORY_MAX_SOURCE_BYTES}`

## Authoritative Discovery Source Files

The source list below is authoritative. Do not invent additional discovery
source files, skip listed files, or read stale legacy `.scratchpad` discovery
outputs as inventory inputs.

{source_list}

## Hard Scope

1. Execute inventory only. Do not run semantic invariants, depth, RAG, chain
   analysis, verification, scoring, report index, report writing, or report
   assembly.
2. Read recon artifacts and the authoritative discovery source files above as
   read-only inputs.
3. Write only `findings_inventory.md`, `violations.md`, and optional `_lg_`
   debug notes under the scratchpad.
4. Do not write `findings_inventory_chunk_*.md`,
   `inventory_shard_plan.md`, or `inventory_chunk_*.manifest.md`.
5. Do not edit target source files, dependency manifests, git metadata, legacy
   `.scratchpad`, or `_v2_checkpoint.json`.
6. Do not call Task, launch subagents, or delegate work to other workers.
7. The `Source Summary` section must include one row for every authoritative
   discovery source file listed above.
8. The final `findings_inventory.md` must include `Source Summary`,
   `Master Table`, `Per-Finding Detail`, and these field labels:
   `Finding ID`, `Title`, `Severity`, `Verdict`, `Location`, `Source IDs`,
   `Root Cause`, and `Preferred Tag`.

## Inventory Methodology

{methodology}

## Return

After `findings_inventory.md` is written and self-checked, return exactly one
concise summary:
`INVENTORY COMPLETE: <source_count> source files consolidated, <finding_count> findings inventoried, limitations: <short list>`.
"""


def build_invariants_prompt(config: dict[str, Any]) -> str:
    """Build a direct-execution prompt for semantic invariant Pass 1."""
    methodology = _read_invariants_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core"))
    pipeline = _none_if_blank(config.get("pipeline", "sc"))

    return f"""# Plamen LangGraph Invariants Direct-Execution Prompt

You are running only the `invariants` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
invariants methodology below only to perform semantic invariant Pass 1 and
write one canonical `semantic_invariants.md`.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Required input artifacts: `findings_inventory.md`, `state_variables.md`, `function_list.md`
- Required output artifact: `semantic_invariants.md`
- Invariants minimum output size: `{INVARIANTS_MIN_BYTES}` bytes

## Hard Scope

1. Execute semantic invariant Pass 1 only. Do not execute Thorough Pass 2.
2. This phase runs only in Core and Thorough modes. If the configured mode is
   `light`, stop and report that semantic invariants are unavailable in Light
   mode.
3. Do not call Task, launch subagents, or delegate work to other workers.
4. Read recon artifacts, `findings_inventory.md`, `state_variables.md`,
   `function_list.md`, and referenced target source files as needed.
5. Write only `semantic_invariants.md`, `violations.md`, and optional `_lg_`
   debug notes under the scratchpad.
6. Do not write `invariant_fuzz_results.md`, `semantic_invariants_p2.md`,
   depth, chain, verification, scoring, report, or any Pass 2 artifact.
7. Do not edit target source files, dependency manifests, git metadata, legacy
   `.scratchpad`, or `_v2_checkpoint.json`.
8. Do not add new findings to `findings_inventory.md`. Already-inventoried
   findings are context for prioritizing invariant gaps, not outputs to
   duplicate.

## Invariants Methodology

{methodology}
"""


def build_depth_prompt(
    config: dict[str, Any],
    required_outputs: list[list[str]] | None = None,
) -> str:
    """Build a direct-execution prompt for the initial adaptive depth boundary."""
    methodology = _read_depth_methodology().strip()
    project_root = _none_if_blank(config.get("project_root"))
    scratchpad = _none_if_blank(config.get("scratchpad"))
    db_path = _none_if_blank(config.get("db_path"))
    language = _none_if_blank(config.get("language", "evm"))
    mode = _none_if_blank(config.get("mode", "core")).lower()
    pipeline = _none_if_blank(config.get("pipeline", "sc"))
    groups = (
        [list(group) for group in required_outputs]
        if required_outputs is not None
        else expected_depth_artifact_groups(mode)
    )
    output_groups = "\n".join(
        f"- {' or '.join(f'`{name}`' for name in group)}" for group in groups
    )
    required_inputs = [
        "`findings_inventory.md`",
        "`state_variables.md`",
        "`function_list.md`",
        "recon artifacts",
    ]
    if mode in {"core", "thorough"}:
        required_inputs.insert(1, "`semantic_invariants.md`")
    else:
        required_inputs.append(
            "`semantic_invariants.md` if present, otherwise use `state_variables.md`"
        )
    required_inputs_text = "\n".join(f"- {name}" for name in required_inputs)

    return f"""# Plamen LangGraph Depth Direct-Execution Prompt

You are running only the `depth` phase of Plamen's smart-contract audit
pipeline. This prompt is generated directly by `plamen_langgraph`; use the
depth methodology below only to investigate inventoried findings and write the
mode-required depth output set.

## Configuration

- Project root: `{project_root}`
- Scratchpad: `{scratchpad}`
- LangGraph database: `{db_path}`
- Pipeline: `{pipeline}`
- Mode: `{mode}`
- Language: `{language}`
- Depth minimum output size: `{DEPTH_MIN_BYTES}` bytes

## Required Input Artifacts

{required_inputs_text}

Light mode must not require semantic invariants. Core and Thorough mode must
consume `semantic_invariants.md` before writing depth outputs.

## Mode-Required Output Groups

Each bullet below is a required artifact group. For groups with aliases, write
at least one accepted filename from that group under the scratchpad.

{output_groups}

## Hard Scope

1. Execute depth only. Do not run RAG, chain analysis, verification,
   skeptic/crossbatch review, final scoring, report index, report writing, or
   report assembly.
2. Do not call Task, launch subagents, create per-agent worktrees, or depend on
   legacy checkpoint state. This is one direct LangGraph worker.
3. Read `findings_inventory.md`, recon artifacts, `semantic_invariants.md` when
   present or required by mode, `state_variables.md`, `function_list.md`, and
   referenced target source files as needed.
4. Write only the mode-required depth outputs, `confidence_scores.md` when
   required, `adaptive_loop_log.md` if useful, `violations.md`, and optional
   `_lg_` debug notes under the scratchpad.
5. Do not write `rag_validation.md`, `chain_hypotheses.md`, `verify_*.md`,
   `verification_*.md`, `report_*.md`, `AUDIT_REPORT.md`,
   `_v2_checkpoint.json`, or files under legacy `.scratchpad`.
6. Every required depth output must include a role/title heading,
   investigated candidates or an explicit no-finding rationale, evidence
   references, verdict/disposition, and limitations or unresolved evidence
   gaps.
7. If Core or Thorough mode finds no scoreable findings, still write
   `confidence_scores.md` with an explicit no-scoreable-findings statement.

## Depth Methodology

{methodology}

## Return

After all mode-required depth outputs are written and self-checked, return
exactly one concise summary:
`DEPTH COMPLETE: <output_count> required outputs complete, limitations: <short list>`.
"""


def build_phase_prompt(
    name: str,
    config: dict[str, Any],
    open_outputs: list[str] | None = None,
) -> str:
    if name == "recon":
        return build_recon_prompt(config)
    if name == "instantiate":
        return build_instantiate_prompt(config)
    if name == "breadth":
        return build_breadth_prompt(config, open_outputs=open_outputs)
    if name == "rescan":
        return build_rescan_prompt(config)
    if name == "inventory":
        return build_inventory_prompt(config)
    if name == "invariants":
        return build_invariants_prompt(config)
    if name == "depth":
        return build_depth_prompt(config)
    raise ValueError(f"unsupported LangGraph phase: {name}")


def expected_recon_artifacts() -> list[str]:
    return list(get_recon_phase("sc").expected_artifacts)
