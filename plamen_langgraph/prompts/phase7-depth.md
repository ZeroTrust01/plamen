# Phase 7 Depth: Codex Subagent Orchestration

This LangGraph-owned prompt body defines the Phase 7 depth methodology for
Codex CLI. The parent worker is the Phase 7 orchestrator. It should use
Codex-native `spawn_agent` and `wait_agent` calls for independent depth work,
then verify the mode-required scratchpad outputs before returning.

## Phase Boundary

Phase 7 owns only depth investigation after inventory, and after semantic
invariants in Core and Thorough modes. Investigate inventoried findings, search
for blind spots, score initial confidence when required, and write only the
configured depth output groups.

Do not run RAG, chain analysis, verification, skeptic review, final scoring,
report indexing, report writing, or report assembly. Do not mutate inventory
inputs, recon artifacts, target source files, dependency manifests, legacy
`.scratchpad`, or `_v2_checkpoint.json`.

## Codex Subagent Rules

Core and Thorough modes must use Codex-native subagents for independent depth
lanes. Spawn all independent agents in a batch before waiting. Use
`wait_agent` for every spawned agent, then inspect the assigned output file.

Light mode may use smaller merged subagents to reduce cost, but each required
output file must still be written under the scratchpad.

Each subagent prompt must include:

- The assigned role and exact output filename.
- The scratchpad path and project root.
- The required input artifacts for the current mode.
- A containment rule: write only the assigned output file, do not read or edit
  other depth agent output files, do not start later pipeline phases, and stop
  after returning findings.
- The mandatory semantic checks and required output structure below.

Do not use legacy Claude-style subagent syntax. Use only Codex-native
`spawn_agent` and `wait_agent` orchestration. Do not create per-agent worktrees
or depend on checkpoint state.

## Standard Depth Agents

Produce the four standard depth outputs in every mode:

| Agent | Output | Focus |
|-------|--------|-------|
| depth-token-flow | `depth_token_flow_findings.md` | Balance changes, transfer paths, fees, share conversions, rewards, and accounting deltas |
| depth-state-trace | `depth_state_trace_findings.md` | State writes, conditional updates, role transitions, lifecycle changes, and storage semantics |
| depth-edge-case | `depth_edge_case_findings.md` | Zero/max values, first/last actor, empty state, rounding, overflow, limits, and boundary branches |
| depth-external | `depth_external_findings.md` | Oracles, external contracts, callbacks, reentrancy, cross-chain paths, and dependency assumptions |

Core and Thorough modes must spawn these four agents as separate subagents.
Light mode may merge token-flow with state-trace, and edge-case with external,
as long as both canonical output files from each merged role are written.

Each standard agent reads the relevant inventory rows, recon maps, source code,
`state_variables.md`, `function_list.md`, and semantic invariant context when
present or required by mode. Each agent should confirm, refute, refine, or
leave unresolved every assigned candidate with concrete evidence.

## Blind Spot Scanners

Core and Thorough modes must also produce these scanner outputs:

| Scanner | Output | Focus |
|---------|--------|-------|
| Scanner A | `blind_spot_a_findings.md` | Tokens, parameters, conversions, and caller-controlled values |
| Scanner B | `blind_spot_b_findings.md` | Guards, visibility, inheritance, modifiers, and override safety |
| Scanner C | `blind_spot_c_findings.md` | Role lifecycle, capability exposure, reachability, and untrusted call targets |

Spawn scanners as separate subagents in Core and Thorough modes unless Light
mode explicitly requires scanner files through the generated output group list.
Scanner outputs should explain what breadth likely missed, even when they find
no reportable issue.

## Validation Sweep

Core and Thorough modes must produce `validation_sweep_findings.md` or
`scanner_validation_findings.md`.

The validation sweep checks cross-cutting properties across all contracts:

- Write-site completeness for lifecycle, accounting, access, and accumulator
  variables.
- Accumulator co-dependencies and paired state updates.
- Loop and batch bounds, skipped entries, first/last item behavior, and empty
  state behavior.
- Event emission coverage for externally visible state changes.

## Confidence Scoring

Core and Thorough modes must produce `confidence_scores.md` after the standard
depth agents, scanners, and validation sweep complete.

For Core, use a 2-axis score:

```text
composite = Evidence * 0.5 + Analysis_Quality * 0.5
```

For Thorough, use a 4-axis score:

```text
composite = Evidence * 0.25 + Consensus * 0.25 + Analysis_Quality * 0.3 + RAG_Match * 0.2
```

This is initial depth confidence scoring, not final scoring. If no scoreable
depth findings exist, still write `confidence_scores.md` with an explicit
no-scoreable-findings statement.

## Thorough Additions

In Thorough mode, also write:

- `design_stress_findings.md` or `depth_design_stress_findings.md`
- `perturbation_findings.md` or `depth_perturbation_findings.md`
- `skill_execution_gaps.md` or `skill_execution_checklist.md`

Design stress testing checks design limits, parameter coherence, authority
assumptions, lifecycle constraints, and economic edge pressure. Perturbation
testing mutates confirmed depth findings with direction flips, boundary shifts,
role swaps, timing inversions, and parameter swaps to search for adjacent
vulnerabilities. The skill checklist verifies whether depth agents executed the
expected role methodology and records any gaps as depth-owned context only.

## Mandatory Semantic Checks

For every investigated candidate touching value movement, accounting,
authorization, lifecycle state, shares or claims, fees, limits, or guarded
arithmetic:

1. State the intended invariant in code-level terms and try to falsify it
   across reachable write paths.
2. Identify read sites where the value is trusted or consumed, then compare
   writer semantics against reader expectations.
3. For guarded arithmetic or branch-dependent updates, record condition,
   formula/effect, boundary inputs, and expected postcondition.
4. Do not mark a candidate safe, refuted, or by design without concrete intent
   evidence from specs, docs, tests, comments, interfaces, or consistent
   call/read-site behavior.

If intent proof is missing, classify the candidate as unresolved or
non-reportable with the missing proof and remaining risk recorded.

## Required Output Structure

Every required depth output must include:

- A role/title heading.
- Investigated candidates or an explicit no-finding rationale.
- Evidence references, including source locations when applicable.
- Verdict or disposition per reported item.
- Limitations or unresolved evidence gaps.

Use canonical severity only for live findings: Critical, High, Medium, Low, or
Informational. Put duplicate, absorbed, refuted, or unresolved/non-reportable
decisions in non-reportable sections instead of using disposition text as
severity.

Use a canonical `## Investigated Candidates` section in every non-confidence
depth output. If no candidate is assigned or no reportable issue is confirmed,
write the explicit no-finding or non-reportable rationale in that section.

## Completion Self-Check

Before returning, re-open every mode-required output group and verify that at
least one accepted file exists, is substantive, and contains the required
structure. Repair missing, empty, stub, or structurally incomplete assigned
outputs before returning. Do not rely on a later retry to repair missing output
groups.
