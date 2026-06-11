# Plamen LangGraph Phase 1-3

This package is an experimental LangGraph execution path for Plamen. Phase 1
supports the smart-contract `recon` phase. Phase 2 extends the same isolated
path to the supported prefix `recon -> instantiate`. Phase 3 extends it to
`recon -> instantiate -> breadth` with manifest-exact first-pass breadth
artifacts. The package intentionally lives outside the legacy driver.

Run:

```bash
python -m plamen_langgraph.cli recon /path/to/project
python -m plamen_langgraph.cli instantiate /path/to/project
python -m plamen_langgraph.cli breadth /path/to/project
```

`instantiate` always runs `recon` first. `breadth` always runs `recon` and
`instantiate` first. If an upstream phase fails, downstream phases do not call
Codex and do not create phase rows.

For explicit failed-tail recovery, single-node mode validates a referenced
base run before running only the requested node:

```bash
python -m plamen_langgraph.cli breadth /path/to/project \
  --single-node \
  --base-run-id <successful-instantiate-run-id>
```

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
- `spawn_manifest.md`
- manifest-derived first-pass `analysis_*.md` files

It does not update legacy checkpoints such as `_v2_checkpoint.json` or write
to the legacy `.scratchpad` directory unless `--scratchpad` explicitly points
there.

The breadth gate is manifest-exact: non-manifest `analysis_*.md` files do not
satisfy missing manifest outputs, and later-phase files such as
`analysis_rescan_*.md`, inventory, depth, verify, or report artifacts are not
breadth completion artifacts.
