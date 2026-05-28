# Changelog

## v2.0.2 - Codex-native

- Plamen now documents OpenAI Codex CLI as the supported runtime path.
- Top-level instructions are installed through `AGENTS.md`.
- Methodology files resolve through `~/.codex/plamen/`.
- The Python driver remains the sole owner of phase sequencing, retries,
  artifact gates, and resume.
- `codex-adapter/` generates Codex config, role definitions, command wrappers,
  and Plamen launch skills.
- Public setup, usage, update, and dependency docs have been rewritten around
  the Codex-native layout.

Historical pre-Codex-native release notes are intentionally omitted on this
branch to avoid stale runtime instructions.
