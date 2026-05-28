# Platform Dependencies

Install only the toolchains you need for the code you audit. `plamen setup`
detects installed tools and offers to install missing ones interactively.

## Required Everywhere

| Tool | Version | Purpose |
|------|---------|---------|
| OpenAI Codex CLI | latest | AI runtime |
| Python | 3.11-3.12 | Wrapper and Python tooling |
| Node.js | 18+ | npm tooling |
| Git | any | Clone and submodules |
| Rust | stable | Solana, Soroban, and L1 Rust tooling |

Install Codex CLI:

```bash
npm install -g @openai/codex
```

## Windows

Enable Developer Mode. Plamen and some chain toolchains create symlinks.

For Solana/Trident builds, install OpenSSL:

```powershell
winget install ShiningLight.OpenSSL.Dev
```

## EVM/Solidity

| Tool | Purpose |
|------|---------|
| Foundry | Build, test, invariant fuzz, fork testing |
| Slither | Static analysis |
| Medusa | Stateful fuzzing for Thorough mode |

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
pip install slither-analyzer
```

## Solana

| Tool | Purpose |
|------|---------|
| Solana CLI | Build and account data |
| Anchor | Anchor program builds |
| Trident | Stateful fuzzing |

Use the official Solana/Anchor installers or run `plamen setup`.

## Move

| Tool | Purpose |
|------|---------|
| Aptos CLI | Aptos Move build/test/prove |
| Sui CLI | Sui Move build/test |

## Soroban/Stellar

| Tool | Purpose |
|------|---------|
| Rust | Contract compilation |
| Stellar CLI | Build and test Soroban contracts |

## L1 Infrastructure

| Tool | Purpose |
|------|---------|
| Go | Go node-client builds |
| Rust | Rust node-client builds |
| scip-go | Go cross-reference index |
| rust-analyzer | Rust cross-reference index |
| Opengrep | Static analysis |
| ast-grep | Structural search |

These tools power Phase 0.5 Bake before L1 depth analysis.

## RAG and API Keys

The RAG database is optional but recommended:

```bash
export SOLODIT_API_KEY=your_key_here
plamen rag
```

Persistent API keys and MCP server settings belong in `~/.codex/config.toml`.
Relevant keys include `SOLODIT_API_KEY`, `TAVILY_API_KEY`,
`ETHERSCAN_API_KEY`, `HELIUS_API_KEY`, and RPC URLs.
