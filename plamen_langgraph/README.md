# Plamen LangGraph Audit Prefix

This package is an experimental LangGraph execution path for Plamen. Phase 1
supports the smart-contract `recon` phase. Phase 2 extends the same isolated
path to the supported prefix `recon -> instantiate`. Phase 3 extends it to
`recon -> instantiate -> breadth` with manifest-exact first-pass breadth
artifacts. The `rescan` node extends the prefix to the mandatory re-scan and
per-contract review phase. The `inventory` node extends the prefix to
`recon -> instantiate -> breadth -> rescan -> inventory` and writes one
canonical `findings_inventory.md`. The package intentionally lives outside the
legacy driver. The `invariants` node extends the Core/Thorough prefix to
`recon -> instantiate -> breadth -> rescan -> inventory -> invariants` and
writes one semantic invariant Pass 1 artifact, `semantic_invariants.md`.
The `depth` node extends the prefix to the first adaptive depth boundary:
Light mode runs `recon -> instantiate -> breadth -> rescan -> inventory ->
depth`, while Core and Thorough run `recon -> instantiate -> breadth ->
rescan -> inventory -> invariants -> depth`. The `sc_semantic_dedup` node
extends the prefix directly after depth. LangGraph intentionally cancels
`attention_repair` and `rag_sweep`; they are not predecessors, outputs, or
completion evidence for semantic dedup.

LangGraph-owned prompt bodies live in `plamen_langgraph/prompts/`. The legacy
driver keeps using `prompts/shared/v2/`; these copies are intentionally separate
so LangGraph prompt changes do not silently change the legacy V2 route.

Run:

```bash
python -m plamen_langgraph.cli recon /path/to/project
python -m plamen_langgraph.cli instantiate /path/to/project
python -m plamen_langgraph.cli breadth /path/to/project
python -m plamen_langgraph.cli rescan /path/to/project
python -m plamen_langgraph.cli inventory /path/to/project
python -m plamen_langgraph.cli invariants /path/to/project --mode core
python -m plamen_langgraph.cli depth /path/to/project --mode light
python -m plamen_langgraph.cli depth /path/to/project --mode core
python -m plamen_langgraph.cli sc_semantic_dedup /path/to/project --mode light
python -m plamen_langgraph.cli sc_semantic_dedup /path/to/project --mode core
```

`instantiate` always runs `recon` first. `breadth` always runs `recon` and
`instantiate` first. `rescan` always runs `recon`, `instantiate`, and `breadth`
first. `inventory` always runs `recon`, `instantiate`, `breadth`, and `rescan`
first. `invariants` always runs `recon`, `instantiate`, `breadth`, `rescan`,
and `inventory` first in Core and Thorough modes. Light mode rejects
`invariants` before calling Codex. If an upstream phase fails, downstream
phases do not call Codex and do not create phase rows.

`depth` runs in every mode. Light mode does not invoke or require
`invariants`; it consumes `findings_inventory.md` and falls back to
`state_variables.md` when `semantic_invariants.md` is absent. Core and
Thorough mode require a successful `invariants` predecessor and a valid
`semantic_invariants.md` before depth starts.

`sc_semantic_dedup` runs in every mode after successful depth. Light mode runs
`recon -> instantiate -> breadth -> rescan -> inventory -> depth ->
sc_semantic_dedup`; Core and Thorough run `recon -> instantiate -> breadth ->
rescan -> inventory -> invariants -> depth -> sc_semantic_dedup`.

For failed-tail recovery, single-node mode infers the latest successful direct
predecessor from the LangGraph state DB before running only the requested node:

```bash
python -m plamen_langgraph.cli breadth /path/to/project \
  --single-node

python -m plamen_langgraph.cli rescan /path/to/project \
  --single-node

python -m plamen_langgraph.cli inventory /path/to/project \
  --single-node

python -m plamen_langgraph.cli invariants /path/to/project \
  --single-node

python -m plamen_langgraph.cli depth /path/to/project \
  --single-node

python -m plamen_langgraph.cli sc_semantic_dedup /path/to/project \
  --single-node
```

Pass `--base-run-id <run-id>` only when you need to override the inferred
predecessor run. Inventory single-node mode infers the latest successful
`rescan` run for the same project and scratchpad, then validates the completed
discovery chain before invoking Codex. Invariants single-node mode infers the
latest successful `inventory` run for the same project and scratchpad, then
validates the completed discovery and inventory chain before invoking Codex.
Depth single-node mode infers the latest successful direct predecessor for the
same project and scratchpad: `inventory` in Light mode, `invariants` in Core
and Thorough mode. SC semantic dedup single-node mode infers the latest
successful `depth` run for the same project and scratchpad.

Before inventory invokes Codex, it revalidates breadth and rescan artifacts and
checks the discovery source set against the configured single-pass limits. If
the source file count or total source bytes are too large, the phase fails
closed with `inventory source set too large; needs sharded inventory support`
and does not call Codex.

Before invariants invokes Codex, it revalidates inventory structure plus the
required recon inputs `state_variables.md` and `function_list.md`.
`semantic_invariants.md` must include every required semantic invariant section
and table label. `invariant_fuzz_results.md`, Pass 2, depth, verification,
scoring, and report artifacts do not satisfy invariants completion.

Before depth invokes Codex, it revalidates inventory structure, recon fallback
inputs, and Core/Thorough semantic invariants. Depth writes only the
mode-required depth outputs, `confidence_scores.md` when required,
`adaptive_loop_log.md` if useful, `violations.md`, and `_lg_` debug files.
RAG, chain, verification, report, and legacy checkpoint artifacts do not
satisfy depth completion.

Before SC semantic dedup invokes Codex, LangGraph revalidates depth
prerequisites and writes a bounded LangGraph-owned candidate packet:
`dedup_candidate_pairs.md` and, when useful, `dedup_focus_inventory.md`.
If there are no candidate pairs and no `LIKELY-DUP` tags, the node writes a
deterministic passthrough `dedup_decisions.md` and
`findings_inventory_deduped.md` without invoking Codex. After a successful
semantic-dedup run, LangGraph validates `findings_inventory_deduped.md`, backs
up the previous inventory to `findings_inventory_pre_dedup.md`, swaps the
deduped file into `findings_inventory.md`, and writes a lightweight
`finding_records.json`. `attention_repair_summary.md`, `rag_validation.md`,
chain, verification, report, and legacy checkpoint artifacts do not satisfy
SC semantic dedup completion.

Useful options:

```bash
python -m plamen_langgraph.cli recon /path/to/project \
  --mode core \
  --pipeline sc \
  --language auto \
  --db /path/to/project/.lg_scratchpad/plamen_lg.sqlite
```

The new path writes only LangGraph debug/state files under the target
project's `.lg_scratchpad`:

- `plamen_lg.sqlite`
- `_lg_recon_prompt.md`
- `_lg_recon_stdout.log`
- `_lg_recon_stderr.log`
- `_lg_recon_events.jsonl`
- `_lg_recon_last_message.md`
- `_lg_instantiate_prompt.md`
- `_lg_instantiate_stdout.log`
- `_lg_instantiate_stderr.log`
- `_lg_instantiate_events.jsonl`
- `_lg_instantiate_last_message.md`
- `_lg_breadth_prompt.md`
- `_lg_breadth_stdout.log`
- `_lg_breadth_stderr.log`
- `_lg_breadth_events.jsonl`
- `_lg_breadth_last_message.md`
- `_lg_rescan_prompt.md`
- `_lg_rescan_stdout.log`
- `_lg_rescan_stderr.log`
- `_lg_rescan_events.jsonl`
- `_lg_rescan_last_message.md`
- `_lg_inventory_prompt.md`
- `_lg_inventory_stdout.log`
- `_lg_inventory_stderr.log`
- `_lg_inventory_events.jsonl`
- `_lg_inventory_last_message.md`
- `_lg_invariants_prompt.md`
- `_lg_invariants_stdout.log`
- `_lg_invariants_stderr.log`
- `_lg_invariants_events.jsonl`
- `_lg_invariants_last_message.md`
- `_lg_depth_prompt.md`
- `_lg_depth_stdout.log`
- `_lg_depth_stderr.log`
- `_lg_depth_events.jsonl`
- `_lg_depth_last_message.md`
- `_lg_sc_semantic_dedup_prompt.md`
- `_lg_sc_semantic_dedup_stdout.log`
- `_lg_sc_semantic_dedup_stderr.log`
- `_lg_sc_semantic_dedup_events.jsonl`
- `_lg_sc_semantic_dedup_last_message.md`
- `spawn_manifest.md`
- manifest-derived first-pass `analysis_*.md` files
- `analysis_rescan_*.md` files
- `analysis_percontract_*.md` files
- `findings_inventory.md`
- `semantic_invariants.md`
- mode-required depth artifacts such as `depth_token_flow_findings.md`,
  `depth_state_trace_findings.md`, `depth_edge_case_findings.md`,
  `depth_external_findings.md`, scanner/blind-spot outputs,
  `confidence_scores.md`, and Thorough-only stress/perturbation/skill outputs
- `dedup_candidate_pairs.md`
- `dedup_focus_inventory.md` when live candidate pairs exist
- `dedup_decisions.md`
- `findings_inventory_deduped.md`
- `findings_inventory_pre_dedup.md` after a successful swap
- `finding_records.json` after a successful swap

It does not update legacy checkpoints such as `_v2_checkpoint.json` or write
to the legacy `.scratchpad` directory unless `--scratchpad` explicitly points
there.

The breadth gate is manifest-exact: non-manifest `analysis_*.md` files do not
satisfy missing manifest outputs, and later-phase files such as
`analysis_rescan_*.md`, inventory, depth, verify, or report artifacts are not
breadth completion artifacts.

The inventory gate is single-file and structure-aware:
`findings_inventory.md` must be substantial, contain `Source Summary`,
`Master Table`, and `Per-Finding Detail`, include the required finding field
labels, and account for every authoritative discovery source file. Legacy
sharded outputs such as `inventory_shard_plan.md`,
`inventory_chunk_*.manifest.md`, and `findings_inventory_chunk_*.md` do not
satisfy LangGraph inventory completion.

The invariants gate is single-file and structure-aware:
`semantic_invariants.md` must be substantial and contain `Main Table`,
`Mirror Variable Pairs`, `Time-Weighted Accumulators`, `Semantic Clusters`,
`Write Completeness vs Semantic Correctness`, `Read-Site Expectations`,
`Write/Read Meaning Drift`, `Branch-Conditioned Formula Inputs`,
`Lifecycle Semantics`, and `Refutation Hazards`, with the required table field
labels. It is Pass 1 only; Pass 2, fuzzing, depth, verification, scoring, and
report artifacts remain out of scope.

The depth gate is mode-aware. Light requires the four standard depth outputs:
`depth_token_flow_findings.md`, `depth_state_trace_findings.md`,
`depth_edge_case_findings.md`, and `depth_external_findings.md`. Core adds
`blind_spot_a_findings.md`, `blind_spot_b_findings.md`,
`blind_spot_c_findings.md`, `validation_sweep_findings.md` or
`scanner_validation_findings.md`, and `confidence_scores.md`. Thorough adds
`design_stress_findings.md` or `depth_design_stress_findings.md`,
`perturbation_findings.md` or `depth_perturbation_findings.md`, and
`skill_execution_gaps.md` or `skill_execution_checklist.md`. Every accepted
depth output must be substantial and include a heading, investigated
candidates or explicit no-finding rationale, evidence, verdict/disposition,
and limitations or unresolved evidence gaps.

The SC semantic dedup gate is SC-only and inventory-based. It requires
`dedup_decisions.md` and `findings_inventory_deduped.md`; the deduped inventory
must remain structurally valid. If live candidate pairs exist, an unchanged
`PASSTHROUGH` decision is rejected unless the node explicitly selected the
budget guard. LangGraph semantic dedup does not reuse legacy private mechanical
helpers and does not run the canceled `attention_repair` or `rag_sweep`
stages.
