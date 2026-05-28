# MCP Servers

Plamen's Codex config is generated into `~/.codex/config.toml`. MCP servers
are optional; the pipeline falls back to code analysis, grep, and web search
when a server is unavailable.

## Bundled and Submodule Servers

| Server | Purpose |
|--------|---------|
| `unified-vuln-db` | Local RAG vulnerability database |
| `solana-fender` | Solana static security analysis |
| `slither-mcp` | Slither static analysis bridge |
| `farofino-mcp` | Aderyn and EVM pattern analysis fallback |

## npm MCP Packages

| Server | Purpose |
|--------|---------|
| `foundry-suite` | Anvil fork testing, Forge scripts, bytecode helpers |
| `evm-chain-data` | On-chain ABI/state lookups |
| `tavily-search` | Web search fallback |
| `helius` | Solana on-chain data |
| `memory` | Session memory |

## API Keys

All keys are optional, but they improve coverage:

| Key | Used for |
|-----|----------|
| `SOLODIT_API_KEY` | RAG indexing and search |
| `ETHERSCAN_API_KEY` | Verified EVM source and ABI lookups |
| `TAVILY_API_KEY` | Web search fallback |
| `HELIUS_API_KEY` | Solana account and transaction data |
| `RPC_URL` | EVM fork testing |

Put persistent values in `~/.codex/config.toml`.

## Failure Policy

If an MCP call times out or a tool is unavailable, agents must record
`[MCP: TIMEOUT]` or the relevant failure note and switch to fallback analysis.
They must not retry the same timed-out provider in a loop.
