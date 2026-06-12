# Phase 8 SC Semantic Dedup

This LangGraph-owned prompt body defines the smart-contract semantic dedup
methodology. It is SC-only: `findings_inventory.md` is the source artifact and
`findings_inventory_deduped.md` is the deduped output.

## Phase Boundary

This phase runs after LangGraph depth. `attention_repair` and `rag_sweep` are
canceled in the LangGraph path and are not inputs, outputs, or prerequisites.

Semantic dedup is a bounded quality-improvement phase. Its first duty is to
preserve every finding unless a duplicate is proven by the live candidate
packet.

## Inputs

Read only these files in this order:

1. `dedup_candidate_pairs.md`
2. `dedup_focus_inventory.md`, if present
3. `findings_inventory.md` for SC passthrough/copy and fallback context

Do not read or expand `dedup_candidate_pairs_full.md` during this phase. It is
traceability only. Do not scan the full inventory looking for new duplicate
groups.

## Mandatory First Action

Before semantic review, physically create safe passthrough outputs on disk:

- copy `findings_inventory.md` to `findings_inventory_deduped.md`
- write `dedup_decisions.md` with a header and a
  `Status: IN_PROGRESS_PASSTHROUGH_WRITTEN` line

Do not merely return a summary saying this was done. If a later step times
out, the pipeline must retain the upstream inventory unchanged.

If passthrough outputs already exist from the driver or a prior attempt, they
are not completed semantic-dedup work while `dedup_candidate_pairs.md` contains
live table rows. A `PASSTHROUGH` or `IN_PROGRESS_PASSTHROUGH_WRITTEN` status
means crash-safety net only. Continue into semantic review, evaluate every live
pair, and overwrite `dedup_decisions.md` plus `findings_inventory_deduped.md`
with real decisions.

## Decision Rule

For each live candidate pair, decide one of:

- `MERGE`: same root cause and same fix/fix-pattern with compatible severity
  within one tier. The absorbed finding adds no distinct vulnerability class.
- `GROUP`: same fix-pattern but distinct locations should both remain visible;
  the representative inherits downstream handling, and non-representatives
  keep a `**Dedup Group**: inherits verification from {representative_id}` note.
- `KEEP SEPARATE`: different root cause, different fix type, different
  vulnerability class, severity gap, or uncertainty.

Strong signals such as source-ID subset, PERT lineage, location overlap, title
overlap, shared identifiers, and function-name match are hints, not authority.
They still require same root cause and same fix type.

When in doubt, choose `KEEP SEPARATE`. Duplicate findings waste budget, but
dropped true positives miss vulnerabilities.

## Output Contract

### `dedup_decisions.md`

Write a complete decision ledger:

```markdown
# Semantic Dedup Decisions

## Summary
- Live pairs evaluated: {P}
- Merges: {M}
- Groups: {G}
- Kept separate: {K}
- Deferred pairs: {D} (from full traceability, not evaluated here)

## Decisions

### MERGE: {survivor_id} absorbs {absorbed_id}
- Signal: {signal from table}
- Root cause match: {one sentence}
- Same fix: {one sentence}
- Survivor updates: {locations/recommendations added, or none}

### GROUP: {representative_id} represents {member_ids}
- Pattern: {same fix-pattern}
- Why not merge fully: {one sentence}

### KEEP SEPARATE: {id_a} vs {id_b}
- Reason: {different root cause / different fix / severity gap / uncertain}

## Dedup Status Table
| Finding ID | Status | Notes |
|------------|--------|-------|
| INV-001 | PASS | unchanged |
| INV-002 | MERGED into INV-001 | same root cause and fix |
```

### `findings_inventory_deduped.md`

Start from an exact copy of `findings_inventory.md`.

- For `MERGE`, omit only the absorbed finding block after copying any distinct
  locations, evidence, recommendations, or source IDs into the survivor.
- For `GROUP`, keep all member blocks and add the `**Dedup Group**:` note.
- For `KEEP SEPARATE`, leave both finding blocks unchanged.
- Findings not present in a live candidate row must pass through unchanged.

The output must remain a valid inventory with `Source Summary`, `Master Table`,
`Per-Finding Detail`, and the normal finding labels.

## Severity And Disposition

The `Severity` field in surviving findings must contain exactly one of:

`Critical`, `High`, `Medium`, `Low`, `Informational`

Never write disposition text such as `duplicate`, `merged`, `refuted`, or
`absorbed` in the severity field. Dedup disposition belongs only in
`dedup_decisions.md` or a `**Dedup Group**:` note. Absorbed findings must not
remain as live finding blocks in `findings_inventory_deduped.md`.

## Final Self-Check

Before returning:

- reopen `dedup_decisions.md`
- reopen `findings_inventory_deduped.md`
- confirm every live pair has a MERGE, GROUP, or KEEP SEPARATE decision
- confirm `findings_inventory_deduped.md` is still a complete inventory
- confirm no attention repair, RAG, chain, verification, report, or legacy
  checkpoint artifacts were written
