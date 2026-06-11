from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def expected_recon_artifacts() -> list[str]:
    return list(get_recon_phase("sc").expected_artifacts)
