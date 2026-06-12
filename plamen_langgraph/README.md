# Plamen LangGraph Audit Prefix

This package is an experimental LangGraph execution path for Plamen. Phase 1
supports the smart-contract `recon` phase. Phase 2 extends the same isolated
path to the supported prefix `recon -> instantiate`. Phase 3 extends it to
`recon -> instantiate -> breadth` with manifest-exact first-pass breadth
artifacts. The `rescan` node extends the prefix to the mandatory re-scan and
per-contract review phase. The `inventory` node extends the prefix to
`recon -> instantiate -> breadth -> rescan -> inventory` and writes one
canonical `findings_inventory.md`. The package intentionally lives outside the
legacy driver.

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
```

`instantiate` always runs `recon` first. `breadth` always runs `recon` and
`instantiate` first. `rescan` always runs `recon`, `instantiate`, and `breadth`
first. `inventory` always runs `recon`, `instantiate`, `breadth`, and `rescan`
first. If an upstream phase fails, downstream phases do not call Codex and do
not create phase rows.

For failed-tail recovery, single-node mode infers the latest successful direct
predecessor from the LangGraph state DB before running only the requested node:

```bash
python -m plamen_langgraph.cli breadth /path/to/project \
  --single-node

python -m plamen_langgraph.cli rescan /path/to/project \
  --single-node

python -m plamen_langgraph.cli inventory /path/to/project \
  --single-node \
  --base-run-id <run-id>
```

Pass `--base-run-id <run-id>` only when you need to override the inferred
predecessor run. Inventory single-node mode requires an explicit
`--base-run-id` because it depends on a completed four-phase discovery chain.

Before inventory invokes Codex, it revalidates breadth and rescan artifacts and
checks the discovery source set against the configured single-pass limits. If
the source file count or total source bytes are too large, the phase fails
closed with `inventory source set too large; needs sharded inventory support`
and does not call Codex.

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
- `spawn_manifest.md`
- manifest-derived first-pass `analysis_*.md` files
- `analysis_rescan_*.md` files
- `analysis_percontract_*.md` files
- `findings_inventory.md`

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
