# Updating Plamen

## Quick Update

```bash
cd ~/.plamen
git pull
plamen install
```

`plamen install` is idempotent. It refreshes Codex-visible methodology links,
regenerates adapter files, and updates generated config. It does not delete
your RAG database, reinstall chain toolchains, or overwrite API keys.

## Why Install After Pull?

Most methodology files are visible through symlinks:

| Source | Codex-visible path |
|--------|--------------------|
| `agents/` | `~/.codex/plamen/agents/` |
| `prompts/` | `~/.codex/plamen/prompts/` |
| `rules/` | `~/.codex/plamen/rules/` |
| `commands/` | `~/.codex/plamen/commands/` |

Generated files are copies:

| File | Why refresh matters |
|------|---------------------|
| `~/.codex/AGENTS.md` | Contains top-level orchestrator rules and version |
| `~/.codex/config.toml` | Contains model, sandbox, env, and MCP config |
| `~/.codex/agents/*.toml` | Defines Codex sub-agent roles |
| `~/.codex/skills/plamen*/` | Exposes Plamen launch skills |

If `AGENTS.md` is stale, the orchestrator can follow old mode tables or phase
rules while the Python driver and prompts are newer.

## Version Warning

If Plamen detects a mismatch, it prints a warning like:

```text
Version mismatch: repo is v2.0.2 but ~/.codex/AGENTS.md has v2.0.1
Run 'plamen install' to update.
```

Run the quick update commands above.

## What Is Never Touched

| Component | Location |
|-----------|----------|
| RAG database | `~/.plamen/custom-mcp/unified-vuln-db/data/` |
| Chain toolchains | System-level installs |
| API keys | User-managed values in `~/.codex/config.toml` |
| Project scratchpads | `{PROJECT}/.scratchpad/` |

## Submodules

If analyzer directories look empty after update:

```bash
cd ~/.plamen
git submodule update --init --recursive
plamen install
```
