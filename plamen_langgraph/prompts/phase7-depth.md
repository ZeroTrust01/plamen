# LangGraph Depth: Direct Adaptive Boundary

This LangGraph-owned prompt body is based on the shared V2 Phase 4b depth
methodology, but it is scoped to one direct `depth` node. It proves the
mode-aware depth boundary before parallel depth agents, per-agent worktrees,
fuzzing, RAG, chain analysis, verification, scoring-as-a-later-phase, or report
work are added to the LangGraph path.

## Phase Boundary

Investigate the canonical post-inventory depth lanes and write the configured
mode-required output groups only. Treat `findings_inventory.md` as the
authoritative finding inventory. Treat `semantic_invariants.md` as required in
Core and Thorough modes; in Light mode, use it when present and otherwise fall
back to `state_variables.md`.

Do not mutate the inventory, recon artifacts, target source files, dependency
manifests, legacy `.scratchpad`, or `_v2_checkpoint.json`.

## Standard Depth Lanes

Produce the four standard depth outputs in every mode:

| Lane | Output | Focus |
|------|--------|-------|
| Token/value flow tracing | `depth_token_flow_findings.md` | Balance changes, transfer paths, fees, share conversions, rewards, and accounting deltas |
| State transition tracing | `depth_state_trace_findings.md` | State writes, conditional updates, role transitions, lifecycle changes, and storage semantics |
| Edge-case investigation | `depth_edge_case_findings.md` | Zero/max values, first/last actor, empty state, rounding, overflow, limits, and boundary branches |
| External interaction review | `depth_external_findings.md` | Oracles, external contracts, callbacks, reentrancy, cross-chain paths, and dependency assumptions |

For each lane, read the relevant inventoried findings, recon maps, source code,
and semantic invariant context. Attempt to confirm, refute, refine, or leave
unresolved each candidate with concrete evidence.

## Core and Thorough Additions

In Core and Thorough modes, also write:

- `blind_spot_a_findings.md`
- `blind_spot_b_findings.md`
- `blind_spot_c_findings.md`
- `validation_sweep_findings.md` or `scanner_validation_findings.md`
- `confidence_scores.md`

Blind spot A covers tokens and parameters. Blind spot B covers guards,
visibility, inheritance, and override safety. Blind spot C covers role
lifecycle, capability exposure, and reachability. The validation sweep checks
cross-cutting write-site completeness, accumulator co-dependencies, loop bounds,
and event emission coverage.

`confidence_scores.md` belongs to this initial depth node. If there are
scoreable depth findings, reference their finding IDs. If there are no
scoreable depth findings, state that explicitly.

## Thorough Additions

In Thorough mode, also write:

- `design_stress_findings.md` or `depth_design_stress_findings.md`
- `perturbation_findings.md` or `depth_perturbation_findings.md`
- `skill_execution_gaps.md` or `skill_execution_checklist.md`

Use these to record design stress tests, perturbation checks, and required
skill execution gaps that should inform later phases. Do not start later phases
from this node.

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

## Completion Self-Check

Before returning, re-open every mode-required output group and verify that at
least one accepted file exists, is substantive, and contains the required
structure. Do not rely on a later retry to repair missing output groups.
