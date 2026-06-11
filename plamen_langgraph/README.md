# Plamen LangGraph Phase 1-2

This package is an experimental LangGraph execution path for Plamen. Phase 1
supports the smart-contract `recon` phase. Phase 2 extends the same isolated
path to the supported prefix `recon -> instantiate`. The package intentionally
lives outside the legacy driver.

Run:

```bash
python -m plamen_langgraph.cli recon /path/to/project
python -m plamen_langgraph.cli instantiate /path/to/project
```

`instantiate` always runs `recon` first in Phase 2. If recon fails, instantiate
does not call Codex and no instantiate phase row is created.

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
- `spawn_manifest.md`

It does not update legacy checkpoints such as `_v2_checkpoint.json` or write
to the legacy `.scratchpad` directory unless `--scratchpad` explicitly points
there.
