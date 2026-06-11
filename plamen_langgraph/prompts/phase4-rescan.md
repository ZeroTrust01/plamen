# LangGraph Rescan: Mandatory Additional Discovery

> **Loaded by**: The LangGraph `rescan` node.
> **Mode gate**: Always run after successful first-pass breadth.
> **Purpose**: Reduce first-pass attention blind spots before inventory by
> performing a fresh gap-oriented pass and a focused per-contract/cluster pass.

---

## Phase Position

This phase runs after first-pass breadth and before inventory. Inventory has
not run yet.

The later inventory phase consumes:

- manifest-derived first-pass breadth outputs;
- `analysis_rescan_*.md` outputs from this phase; and
- `analysis_percontract_*.md` outputs from this phase.

This subprocess does not merge findings or produce inventory artifacts.

---

## Execution Boundary

Execute this phase directly in the current Codex worker. Do not spawn subagents,
do not call Task, and do not hand work to separate workers. The goal is bounded
additional discovery, not a new pipeline.

You may read:

- `spawn_manifest.md`;
- manifest-derived first-pass `analysis_*.md` breadth outputs;
- recon artifacts such as `contract_inventory.md`, `attack_surface.md`,
  `design_context.md`, `state_variables.md`, and `function_list.md`;
- target source files and local configuration needed to understand reviewed
  code.

Do not edit target source files, dependency manifests, git metadata, legacy
`.scratchpad`, `_v2_checkpoint.json`, inventory, depth, verification, scoring,
chain, or report artifacts.

---

## Exclusion And Retry Rules

First-pass breadth findings are the primary exclusion set. Before writing any
finding, compare it against the first-pass outputs:

- Do not report the same root cause.
- Do not report the same code location with only a renamed title.
- Do not report a same-effect variant unless the triggering path, affected
  state, or exploit precondition is materially different.

On retry, existing `analysis_rescan_*.md` and `analysis_percontract_*.md`
outputs may be preserved only if they are substantive, complete, and consistent
with this prompt. Use prior same-phase outputs for retry continuity and
intra-phase de-duplication, not as a reason to skip required coverage.

---

## Work Plan

### Step 1: Build The Gap Map

Read `spawn_manifest.md` and the manifest-derived first-pass breadth outputs.
Create a compact mental gap map:

- first-pass lanes with many findings that may have consumed attention;
- lanes, files, functions, or state variables with little or no discussion;
- cross-function or cross-contract flows split across breadth outputs;
- findings whose root cause suggests nearby unchecked variants;
- recon-identified attack surfaces that first-pass breadth did not cover.

Use this map to choose the fresh re-scan scope. Do not copy first-pass analysis
into the output except as short exclusion evidence.

### Step 2: Perform Mandatory Re-Scan

Write at least one `analysis_rescan_*.md` file. Use a stable descriptive name,
preferably `analysis_rescan_gap_review.md` unless an existing substantial file
already uses a better scoped name.

The re-scan must inspect under-covered surfaces and cross-check at least three
of these blind-spot classes when applicable:

1. Cross-function state inconsistencies.
2. Asymmetric operations such as deposit/withdraw, lock/unlock, mint/burn,
   create/consume, stake/unstake, bridge send/receive.
3. Parameter encoding, normalization, or hashing mismatches between paired
   functions.
4. Economic edge cases at zero state, first user, last user, max value, fee
   rounding, stale price, or mixed-decimal boundaries.
5. Time-dependent state that can become stale across operation sequences.
6. Privileged or semi-trusted role actions that bypass assumptions used by
   public flows.
7. External dependency behavior that first-pass breadth treated as idealized.

If no new finding survives de-duplication, the output is still required. In that
case, write a substantive negative review that lists reviewed files/functions,
the blind-spot classes checked, and why no candidate was retained.

### Step 3: Perform Mandatory Per-Contract Or Cluster Review

Write at least one `analysis_percontract_*.md` file. Use
`contract_inventory.md` when available to group contracts by inheritance,
library dependency, proxy/implementation relationship, or tightly coupled state.

For each selected contract or cluster, review:

1. Every externally callable or privileged function in the cluster.
2. State writes and whether paired reads/writes remain consistent.
3. Branches that skip updates, emit events conditionally, or depend on stale
   cached values.
4. Boundary values and zero-state behavior.
5. Cross-contract boundary assumptions from the cluster's perspective.

If no meaningful contract cluster can be derived, write
`analysis_percontract_scope_review.md` with a substantive explanation of the
fallback source files reviewed, why clustering was not applicable, and what
per-file checks were performed.

### Step 4: De-Duplicate And Self-Check

Before returning:

1. Re-read the files you wrote.
2. Confirm every retained finding has a specific source location.
3. Confirm retained findings do not duplicate first-pass breadth findings.
4. Confirm per-contract findings do not duplicate re-scan findings unless the
   per-contract output explicitly marks them as duplicate context rather than a
   new finding.
5. Confirm each required output is substantive and at least the configured
   minimum output size.

---

## Finding Format

Use this structure for each retained finding:

```markdown
### [RS-1] or [PC-1] Concise title

- Verdict: Candidate
- Severity: Critical | High | Medium | Low | Informational
- Location: path/to/file.ext:line
- Root cause: one sentence
- Trigger/path: concrete call sequence or state condition
- Impact: concrete security consequence
- Evidence: code references and reasoning
- Duplicate check: why this is not already covered by first-pass breadth
```

If a candidate is rejected during self-check, either omit it or place it under a
short `Rejected Candidates` section with the reason. Do not present rejected or
duplicate items as new findings.

---

## Output Contract

Primary outputs owned by this phase:

- at least one `analysis_rescan_*.md`;
- at least one `analysis_percontract_*.md`.

The prompt wrapper also permits `violations.md` and optional `_lg_` debug notes
when needed, but those files do not satisfy the output contract.

Do not create any other artifact family. When the required files are written and
self-checked, return and stop. The Python phase graph routes all later phases.
