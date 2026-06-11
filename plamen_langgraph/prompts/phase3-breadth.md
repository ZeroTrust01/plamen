# Phase 3: Manifest-Exact Breadth Analysis

> **Loaded by**: `plamen_langgraph` direct-execution breadth worker.
> **Purpose**: Produce only the first-pass `analysis_*.md` files named by
> `spawn_manifest.md`.

---

## Step 3a: Read The Manifest Contract

`spawn_manifest.md` is authoritative for Phase 3. Parse the first markdown table
with both `Template` and `Required?` columns and build `EXPECTED_OUTPUTS` from
rows that represent breadth AGENT work.

Rules:

- Include only rows with `Row Type = AGENT` or an equivalent breadth work row
  accepted by the parser.
- Ignore notes, non-agent binding rows, methodology rows, checklists, merged
  rows, and optional rows that do not own a first-pass output.
- Use the explicit `Expected Output` filename when present.
- Otherwise derive `analysis_<focus_area>.md`.
- Treat the manifest `Status` column as advisory only; filesystem existence and
  size are the completion source of truth.

---

## Step 3b: Limit This Run To Open Outputs

Use the current open-output list from the prompt wrapper as the work queue. If
the wrapper says no outputs are open, re-check the expected files and return
only after the manifest-derived outputs are all present and substantial.

For every open output:

1. Write exactly the manifest-derived filename under the scratchpad.
2. Keep the output first-pass breadth only.
3. Do not invent substitute names such as `analysis_1.md`.
4. Do not create later-phase artifacts.

Available parallel worker tools may be used in bounded batches, but they are
optional. If no such tool is available, complete the open outputs sequentially
in this direct worker.

---

## Step 3c: Output File Contract

Each open breadth lane writes one markdown file:

```text
{SCRATCHPAD}/analysis_<focus_area>.md
```

The manifest `Expected Output` column overrides derived naming. Each output
must be at least the configured breadth minimum size and should include:

- focus area and scope reviewed;
- concrete file/function references;
- candidate findings or reviewed surfaces;
- severity and confidence for candidate findings;
- assumptions, limitations, and follow-up questions.

If no issue is confirmed for a lane, still write a substantive review of the
surfaces checked and why no candidate finding was retained.

---

## Step 3d: Scope Containment

Breadth may read:

- `spawn_manifest.md`;
- recon artifacts;
- target source files and local project configuration needed for the assigned
  breadth lane.

Breadth must not:

- edit target source files, dependency manifests, git metadata, or legacy
  `.scratchpad`;
- run re-scan, per-contract review, inventory, semantic invariants, depth, RAG,
  chain analysis, verification, scoring, or report work;
- write `analysis_rescan_*.md`, `analysis_percontract_*.md`,
  `analysis_merged_into_*.md`, inventory, depth, chain, verification, scoring,
  or report artifacts;
- treat non-manifest `analysis_*.md` files as completion evidence.

If an overreach artifact already exists or is accidentally produced, record the
problem in `{SCRATCHPAD}/violations.md`; do not count the overreach artifact as
Phase 3 completion.

---

## Step 3e: Completion Loop

Before returning:

1. Re-parse `spawn_manifest.md`.
2. Rebuild the manifest-derived expected output list.
3. Confirm every expected output exists under the scratchpad.
4. Confirm every expected output is at least the configured breadth minimum
   size.
5. Confirm no required expected output was replaced by a non-manifest file.
6. Confirm later-phase artifacts were not written as breadth outputs.

If any expected output is missing or too small, complete that exact output and
run the loop again. Exit only when the manifest-derived output set is complete.

Optional manifest status updates are allowed only after the corresponding file
exists and is substantial. Status updates are not required for completion.
