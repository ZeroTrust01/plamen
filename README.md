# Plamen (v2.0.2)

Autonomous Web3 security auditor for [OpenAI Codex CLI](https://github.com/openai/codex).

Plamen orchestrates a deterministic multi-agent audit pipeline for smart
contracts and L1 infrastructure. It supports EVM/Solidity, Solana/Anchor,
Aptos Move, Sui Move, Soroban/Stellar, and Go/Rust node clients.

## Requirements

- [OpenAI Codex CLI](https://github.com/openai/codex), available as `codex`
- Python 3.11 or 3.12
- Node.js 18+ with `npm` and `npx`
- Git with submodule support

Install Codex CLI with a user-local npm prefix if your Node install rejects
global packages:

```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.zshrc
npm install -g @openai/codex
```

## Install

```bash
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git ~/.plamen
cd ~/.plamen
python3 plamen.py install
```

On Windows PowerShell:

```powershell
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git $HOME\.plamen
cd $HOME\.plamen
python plamen.py install
```

Use `--recurse-submodules`; the RAG and analyzer integrations depend on
submodules under `custom-mcp/`.

The installer:

- Links methodology files into `~/.codex/plamen/`
- Generates Codex config from `codex-adapter/`
- Installs `~/.codex/AGENTS.md` with Plamen's orchestrator rules
- Installs or refreshes `~/.codex/config.toml`
- Installs Python wrapper dependencies

Add the wrapper to PATH:

```bash
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then verify:

```bash
plamen doctor
```

## Setup Optional Toolchains

Run the interactive setup wizard from a real terminal:

```bash
plamen setup
```

Install only the chain tools you need:

| Target | Typical tools |
|--------|---------------|
| EVM/Solidity | Foundry, Slither, Medusa |
| Solana/Anchor | Solana CLI, Anchor, Trident |
| Aptos/Sui Move | Aptos CLI, Sui CLI |
| Soroban/Stellar | Rust, Stellar CLI |
| L1 Go/Rust | Go, Rust, scip-go, rust-analyzer, Opengrep |

The optional RAG database uses historical findings from Solodit,
DeFiHackLabs, and Immunefi. It requires several GB of RAM:

```bash
export SOLODIT_API_KEY=your_key_here
plamen rag
```

For Codex subprocesses, persistent API keys belong in `~/.codex/config.toml`.

## Run

```bash
plamen                              # interactive wizard
plamen core /path/to/project        # smart contract audit
plamen thorough /path/to/project    # deeper smart contract audit
plamen l1 core /path/to/node-client # L1 infrastructure audit
plamen resume                       # resume interrupted audit
```

Inside Codex CLI, use the installed commands:

```text
/plamen-wizard
/plamen-l1-wizard
```

The Python driver is the sole owner of phase sequencing. It runs isolated
`codex exec` subprocesses, checks phase artifacts, and resumes from checkpoints
after crashes or rate limits.

## Audit Modes

| Mode | Typical agents | Use for |
|------|----------------|---------|
| Light | ~18-22 | Fast first pass, smaller projects |
| Core | ~30-50 | Standard audit depth |
| Thorough | ~40-100 | High-value targets, fuzzing, extra verification |

Severity is based on Impact x Likelihood. Reports are produced only after
verification gates complete.

## Layout

| Path | Purpose |
|------|---------|
| `~/.plamen/` | Source checkout |
| `~/.codex/plamen/` | Codex-visible methodology root |
| `~/.codex/AGENTS.md` | Installed orchestrator rules |
| `~/.codex/config.toml` | Codex model, sandbox, env, and MCP config |
| `{PROJECT}/.scratchpad/` | Per-audit artifacts and checkpoints |

## Updating

```bash
cd ~/.plamen
git pull
plamen install
```

Run `plamen install` after every pull. Many files update through symlinks, but
`~/.codex/AGENTS.md` and `~/.codex/config.toml` are generated copies.

## Documentation

| Topic | Link |
|-------|------|
| Automated setup prompt | [SETUP.md](SETUP.md) |
| Manual setup | [docs/setup.md](docs/setup.md) |
| First audit | [docs/getting-started.md](docs/getting-started.md) |
| Usage | [docs/usage.md](docs/usage.md) |
| Updating | [docs/updating.md](docs/updating.md) |
| Dependencies | [docs/dependencies.md](docs/dependencies.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| L1 design | [docs/l1-mode/design.md](docs/l1-mode/design.md) |

## License

[MIT](LICENSE)
