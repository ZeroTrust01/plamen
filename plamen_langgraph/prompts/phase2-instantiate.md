# Phase 2: Manifest Instantiation

> **Loaded by**: `plamen_langgraph` direct-execution instantiate worker.
> **Purpose**: Convert Phase 1 recon artifacts into the `spawn_manifest.md`
> contract consumed by the breadth phase.

---

## Step 2a: Read Recon Inputs

Use the scratchpad recon artifacts as the only planning source. The primary
input is `template_recommendations.md`; use the remaining recon artifacts only
to clarify names, risk themes, affected contracts, and limitations.

Do not load external prompt files, agent definitions, skill files, MCP servers,
network sources, or legacy checkpoints. Phase 2 plans manifest rows only; it
does not instantiate worker prompts.

---

## Step 2b: Derive Breadth Lanes

Extract candidate breadth lanes from `template_recommendations.md`:

1. Prefer rows under `## Recommended Analysis Lanes`.
2. If that table is incomplete, use the `## Binding Manifest` template keys.
3. Treat a lane as required when it is marked `Required? = YES`,
   `Required = YES`, or when no required/optional marker is present.
4. Skip only lanes explicitly marked `NO`, `OPTIONAL`, `SKIP`, or `MERGED`.
5. Preserve project-specific lane names. They are analysis lanes, not paths to
   external templates.

If no lanes can be parsed, create a minimal manifest with:

- `CORE_STATE`
- `ACCESS_CONTROL`
- one `EXTERNAL_DEPENDENCY` lane when recon identifies external dependencies

Record this fallback in the manifest notes.

---

## Step 2c: Choose Agent Rows

Prefer one breadth agent per distinct required lane. Do not force the run into a
fixed target count when recon identified more distinct lanes; coverage is more
important than matching an advisory range.

Use these advisory ranges only for the notes section:

| Project shape | Advisory breadth rows |
|---------------|-----------------------|
| Simple (<5 deps, <2000 lines) | 3 |
| Medium (5-10 deps, 2000-5000 lines) | 5-7 |
| Complex (>10 deps or >5000 lines) | 7-9 |

Merge lanes only when they are clear duplicates or when one row is explicitly
marked as merged into another. Never merge lanes merely because the advisory
range is lower than the required lane count.

---

## Step 2d: Name Outputs

For each AGENT row:

1. Assign a stable unique agent id: `B1`, `B2`, `B3`, ...
2. Convert the lane name to a lowercase underscore focus area.
3. Set expected output to `analysis_<focus_area>.md`.
4. Keep expected outputs unique and first-pass breadth-only.

Examples:

- `ACCESS_CONTROL_ROLE_GRAPH` -> `analysis_access_control_role_graph.md`
- `ORACLE_STALENESS_DEVIATION_DECIMALS` ->
  `analysis_oracle_staleness_deviation_decimals.md`

---

## Step 2e: Write The Manifest

Write `{scratchpad}/spawn_manifest.md` with this structure:

```markdown
# Spawn Manifest

## Breadth Agents

| Row Type | Template | Required? | Agent ID | Focus Area | Expected Output | Status |
|----------|----------|-----------|----------|------------|-----------------|--------|
| AGENT | CORE_STATE | YES | B1 | core_state | analysis_core_state.md | QUEUED |

**Gate Check**: All REQUIRED templates have agents? YES
```

`spawn_manifest.md` is a machine-read contract, not narrative notes. Rules:

- The first markdown table in the file with both `Template` and `Required?`
  columns MUST be the breadth-agent AGENT table shown above.
- Put breadth agents only in rows with `Row Type = AGENT`.
- Every `AGENT` row MUST have `Required? = YES`, a unique `Agent ID`, a
  non-empty `Focus Area`, and an `Expected Output` filename matching
  `analysis_<focus>.md`.
- Do NOT put `verify_*.md`, `analysis_rescan_*.md`,
  `analysis_percontract_*.md`, `analysis_merged_into_*.md`, inventory, depth,
  chain, verification, scoring, or report artifacts in the AGENT table.
- Optional notes sections are allowed after the AGENT table, but they must not
  introduce extra AGENT rows or later-phase artifacts.

---

## Step 2f: Self-Check

Before returning:

1. Re-read `spawn_manifest.md`.
2. Confirm every required lane has exactly one AGENT row unless explicitly
   merged in the source input.
3. Confirm AGENT ids are unique.
4. Confirm expected outputs are unique `analysis_*.md` files.
5. Confirm no later-phase artifacts appear in the AGENT table.

If any check fails, fix the manifest before returning.
