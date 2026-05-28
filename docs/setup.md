# Setup Guide

Manual setup instructions for Plamen's Codex-native runtime.

## Prerequisites

| Tool | Purpose |
|------|---------|
| OpenAI Codex CLI | AI runtime |
| Python 3.11-3.12 | Wrapper and Python tooling |
| Node.js 18+ | npm-based tools and MCP servers |
| Git | Clone and submodules |

Install Codex CLI:

```bash
npm install -g @openai/codex
```

On macOS/Homebrew Node, prefer a user-local npm prefix if global install fails.

## Windows Developer Mode

Enable Developer Mode before installing. Plamen creates symlinks, and Windows
requires Developer Mode for file symlinks.

## Clone

```bash
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git ~/.plamen
cd ~/.plamen
```

Windows PowerShell:

```powershell
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git $HOME\.plamen
cd $HOME\.plamen
```

## Install Plamen

```bash
python3 plamen.py install       # macOS/Linux
python plamen.py install        # Windows
```

This creates the Codex-native layout:

| Path | Purpose |
|------|---------|
| `~/.codex/plamen/` | Methodology root linked to `~/.plamen/` |
| `~/.codex/AGENTS.md` | Installed orchestrator instructions |
| `~/.codex/config.toml` | Codex config generated from `codex-adapter/` |
| `~/.codex/commands/` | Codex command wrappers |
| `~/.codex/agents/` | Codex role definitions |

Then add the wrapper to PATH:

```bash
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Toolchains

Run from a real terminal:

```bash
plamen setup
```

Select only the tools you need for your target chain.

## RAG Database

Optional:

```bash
export SOLODIT_API_KEY=your_key_here
plamen rag
```

For persistent subprocess access, put API keys in `~/.codex/config.toml`.

## Verify

```bash
plamen doctor
plamen help
```

## Update

```bash
cd ~/.plamen
git pull
plamen install
```
