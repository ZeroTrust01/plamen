# Plamen LangGraph Phase 1

This package is an experimental LangGraph execution path for Plamen. Phase 1
supports only the smart-contract `recon` phase and intentionally lives outside
the legacy driver.

Run:

```bash
python -m plamen_langgraph.cli recon /path/to/project
```

Useful options:

```bash
python -m plamen_langgraph.cli recon /path/to/project \
  --mode core \
  --pipeline sc \
  --language auto \
  --db /path/to/project/.scratchpad/plamen_lg.sqlite
```

The new path writes only LangGraph debug/state files under the target
project's `.scratchpad`:

- `plamen_lg.sqlite`
- `_lg_recon_prompt.md`
- `_lg_recon_stdout.log`
- `_lg_recon_stderr.log`
- `_lg_recon_events.jsonl`
- `_lg_recon_last_message.md`

It does not update legacy checkpoints such as `_v2_checkpoint.json`.

