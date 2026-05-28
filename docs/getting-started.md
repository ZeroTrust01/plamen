# Getting Started

Start here after `plamen install`.

## Verify Install

```bash
plamen doctor
```

This checks the Plamen checkout, Codex CLI, Python dependencies, submodules,
symlinks, `~/.codex/AGENTS.md`, and generated Codex config.

## What Install Created

| Component | Location |
|-----------|----------|
| Source checkout | `~/.plamen/` |
| Codex methodology root | `~/.codex/plamen/` |
| Codex orchestrator rules | `~/.codex/AGENTS.md` |
| Codex config | `~/.codex/config.toml` |
| Project scratchpad | `{PROJECT}/.scratchpad/` |

`~/.codex/plamen/` points back to the source checkout. `AGENTS.md` and
`config.toml` are generated copies, so re-run `plamen install` after updates.

## Required Tools

- Codex CLI (`codex`)
- Python 3.11 or 3.12
- Node.js 18+ with `npm` and `npx`
- Git

Install target-chain tools only for the projects you audit:

| Target | Install with |
|--------|--------------|
| EVM/Solidity | `plamen setup` -> EVM |
| Solana/Anchor | `plamen setup` -> Solana |
| Aptos/Sui Move | `plamen setup` -> Move |
| Soroban/Stellar | `plamen setup` -> Soroban |
| L1 Go/Rust | `plamen setup` -> L1 |

## Optional RAG Database

RAG improves historical vulnerability matching but requires several GB of RAM.

```bash
export SOLODIT_API_KEY=your_key_here
plamen rag
```

Persistent API keys for Codex subprocesses belong in `~/.codex/config.toml`.

## First Audit

Interactive wizard:

```bash
plamen
```

One-liner:

```bash
plamen core /path/to/project
```

Inside Codex:

```text
/plamen-wizard
/plamen-l1-wizard
```

The driver writes checkpoints and artifacts under `{PROJECT}/.scratchpad/`.
If an audit is interrupted, run:

```bash
plamen resume
```

## Modes

| Mode | Use for |
|------|---------|
| Light | Fast first pass |
| Core | Standard audit |
| Thorough | Deep audit with extra verification and fuzzing |

Use `plamen l1 [light|core|thorough] /path` for Go/Rust node-client audits.

## Updating

```bash
cd ~/.plamen
git pull
plamen install
```

See [updating.md](updating.md) for details.
