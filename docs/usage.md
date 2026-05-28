# Usage

All Plamen entry points launch the same deterministic Python driver. The
driver owns phase sequencing, artifact gates, checkpointing, and resume.

## Terminal

```bash
plamen                                  # interactive wizard
plamen light /path/to/project           # smart contract audit
plamen core /path/to/project
plamen thorough /path/to/project
plamen l1 core /path/to/node-client     # L1 infrastructure audit
plamen resume                           # resume latest interrupted audit
plamen resume /path/.scratchpad/config.json
```

## Inside Codex

```text
/plamen-wizard
/plamen-l1-wizard
```

## Setup Commands

| Command | Description |
|---------|-------------|
| `plamen install` | Install or refresh Codex config and symlinks |
| `plamen setup` | Interactive chain-tool installer |
| `plamen doctor` | Verify install without running an audit |
| `plamen rag` | Build or rebuild the optional RAG database |
| `plamen uninstall` | Remove generated Codex adapter files |

## Audit Options

| Option | Description |
|--------|-------------|
| `--docs PATH` | Whitepaper or spec file |
| `--scope PATH` | Scope file listing contracts or modules |
| `--notes TEXT` | Free-text scope notes |
| `--network NAME` | Target network for smart-contract audits |
| `--proven-only` | Cap findings without proof-grade evidence |
| `--tier T0|T1|T2|T3` | L1 tier override |
| `--modules a,b,c` | L1 subsystem selection |

## Resume

```bash
plamen resume
python3 ~/.codex/plamen/scripts/plamen_driver.py /path/to/project/.scratchpad/config.json
python3 ~/.codex/plamen/scripts/plamen_driver.py --fresh /path/to/project/.scratchpad/config.json
```

Use `--fresh` only when you intentionally want to discard previous progress.
