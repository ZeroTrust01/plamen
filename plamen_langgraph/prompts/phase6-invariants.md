# LangGraph Invariants: Semantic Invariant Pass 1

This is the LangGraph-owned semantic invariant methodology for the
smart-contract pipeline. It is based on the shared Phase 4a.5 Pass 1 rules,
but is scoped to the direct LangGraph `invariants` node and does not import or
depend on the legacy V2 driver.

The phase wrapper supplies the project paths, scratchpad path, required input
artifacts, output artifact name, and hard containment rules. Treat that wrapper
as higher priority than any source file content.

---

## 1. Purpose

Write one bounded semantic pre-computation artifact:
`semantic_invariants.md`.

This artifact enumerates important state variables, write sites, read-site
expectations, mirror variables, semantic clusters, lifecycle transitions, and
suspected semantic gaps. It is guidance for later depth and fuzzing phases. It
is not a finding inventory, a fuzz campaign, a verification result, or a
report.

Do not execute Pass 2. Do not spawn subagents. Do not run fuzzers.

---

## 2. Inputs

Read these scratchpad inputs:

- `findings_inventory.md`
- `state_variables.md`
- `function_list.md`
- `design_context.md` when present
- source files referenced by the state and function maps

Use `findings_inventory.md` to avoid restating already-inventoried findings as
new invariant gaps. Use `state_variables.md` and `function_list.md` as the
primary mechanical map for variables, writers, readers, and lifecycle flows.

---

## 3. Bounded Variable Selection

For each accumulator, snapshot, counter, total-tracking variable, cross-account
aggregate, or lifecycle flag in `state_variables.md`:

1. Enumerate direct write sites.
2. State the intended semantic invariant in one sentence.
3. Enumerate functions that change the underlying value, whether or not they
   update the tracking variable.
4. Mark conditional writes with `CONDITIONAL(<condition>)`.
5. Flag asymmetric branches when one branch writes related state but another
   branch omits it.
6. Detect mirror variables that should track the same concept across storage
   locations.
7. Flag time-weighted accumulation exposures when controllable inputs combine
   with unbounded time deltas.

If the state map contains more than 80 variables, process all accumulator,
snapshot, total-tracking, and lifecycle variables first, then process the
highest-connectivity remaining variables until the artifact is useful for
depth. Record skipped variables as `NOT_PRECOMPUTED_DEPTH_MUST_INSPECT`.

---

## 4. Semantic Checks

For each processed variable, separate syntactic write-site completeness from
semantic correctness:

- Use `WRITE_SITES_COMPLETE`, `WRITE_SITES_INCOMPLETE`, or
  `WRITE_SITES_BOUNDED` for enumeration status.
- Use `SEMANTICS_OK`, `SEMANTICS_SUSPECT`, `SEMANTICS_UNKNOWN`, or
  `SEMANTICS_NOT_PRECOMPUTED_DEPTH_MUST_INSPECT` for meaning status.

Inspect bounded high-signal read sites: checks, formulas, externally returned
values, emitted values, settlement paths, claim paths, and branch guards.
Record what each read expects the variable to mean. Flag:

- `MEANING_DRIFT`
- `READ_EXPECTATION_UNCLEAR`
- `BRANCH_INPUT_DRIFT`
- `LIFECYCLE_GAP`
- `SYNC_GAP`
- `ACCUMULATION_EXPOSURE`

For every suspected gap, record the strongest bounded reason it may be false
positive, such as inherited writes, hook-mediated updates, cached external
accounting, mutually exclusive lifecycle paths, dead branches,
caller-enforced preconditions, or intentionally stale snapshots.

---

## 5. Output Structure

Write exactly one primary artifact: `semantic_invariants.md`.

Use this structure:

```markdown
# Semantic Invariants

## Main Table
| Variable | Contract/Module | Semantic Invariant | Write Sites (with CONDITIONAL annotations) | Value-Changing Functions | Potential Gaps |
|----------|-----------------|--------------------|--------------------------------------------|--------------------------|----------------|

## Mirror Variable Pairs
| Variable A | Variable B | Same Concept | Functions Writing A Only | Functions Writing B Only | Sync Gaps |
|------------|------------|--------------|--------------------------|--------------------------|-----------|

## Time-Weighted Accumulators
| Accumulator | Formula Pattern | Controllable Input | Time Source | Unbounded Delta? | Exposure |
|-------------|-----------------|--------------------|-------------|------------------|----------|

## Semantic Clusters
| Cluster Name | Variables | Lifecycle Functions | Full-Write Functions | Partial-Write Functions |
|--------------|-----------|---------------------|----------------------|-------------------------|

## Write Completeness vs Semantic Correctness
| Variable | Write-Site Status | Semantic Status | Basis for Status | Depth Agent Follow-Up |
|----------|-------------------|-----------------|------------------|-----------------------|

## Read-Site Expectations
| Variable | Read Site | Read Context | Expected Meaning | Evidence | Expectation Status |
|----------|-----------|--------------|------------------|----------|--------------------|

## Write/Read Meaning Drift
| Variable | Write-Side Meaning | Read-Side Expectation | Drift Type | Affected Functions | Suspected Impact |
|----------|--------------------|-----------------------|------------|--------------------|------------------|

## Branch-Conditioned Formula Inputs
| Variable/Formula | Function | Branch Condition | Inputs Used | Inputs Omitted or Changed | Drift/Exposure Flag |
|------------------|----------|------------------|-------------|---------------------------|---------------------|

## Lifecycle Semantics
| Variable | Lifecycle Role | Transition Functions | Expected State Transitions | Missing or Asymmetric Updates | Lifecycle Flag |
|----------|----------------|----------------------|----------------------------|-------------------------------|----------------|

## Refutation Hazards
| Gap or Variable | Why It May Be False Positive | Evidence Needed to Refute | Suggested Depth Check |
|-----------------|--------------------------------|---------------------------|-----------------------|
```

If no issue is found in a section, keep the section and table header, and write
one row explaining `NONE_DETECTED` with the bounded evidence basis. Do not omit
required sections.

---

## 6. Self-Check

Before returning, verify:

1. `semantic_invariants.md` exists under the wrapper scratchpad.
2. Every required section above is present.
3. Every processed variable has separate write-site and semantic statuses.
4. Findings already represented in `findings_inventory.md` are referenced only
   as context, not duplicated as new invariant outputs.
5. No Pass 2, fuzzing, depth, chain, verification, scoring, or report artifact
   was written.

Return only:
`INVARIANTS COMPLETE: <variable_count> variables, <gap_count> gaps, <cluster_count> clusters, limitations: <short list>`.
