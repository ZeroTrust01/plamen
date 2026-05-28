# Automated Setup - Paste This Into Codex CLI

> For users who want Codex to run the install.
> Copy everything below the line into a Codex CLI session.
> The optional RAG build is intentionally not run here because it is CPU and
> memory heavy. Run `plamen rag` later from a real terminal if you want it.

---

Please install Plamen (Web3 Security Auditor) on my machine. Follow these
steps in order. After each step, report any error and stop unless I tell you
to continue.

## Step 0: Detect platform and prerequisites

Run:

```bash
uname -s 2>/dev/null || ver
python3 --version 2>/dev/null || python --version
pip3 --version 2>/dev/null || pip --version
node --version
npx --version
npm --version
git --version
codex --version 2>/dev/null && echo "codex OK"
```

If any required tool is missing, stop and tell me which one. Do not install
system-level prerequisites without asking.

Quick hints:

- Codex CLI: `npm install -g @openai/codex`
- Python: 3.11 or 3.12 is recommended
- Node: 18+
- macOS: `xcode-select --install` may be needed for native dependencies

## Step 0b: Windows Developer Mode

Skip on macOS and Linux.

Plamen creates symlinks. On Windows, file symlinks require Developer Mode.
Ask the user to enable Settings > System > For Developers > Developer Mode.

## Step 1: Clone

Use submodules:

```bash
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git ~/.plamen
cd ~/.plamen
```

Windows PowerShell:

```powershell
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git $HOME\.plamen
cd $HOME\.plamen
```

If the repo already exists but submodules are empty, run:

```bash
git submodule update --init --recursive
```

## Step 2: Install

```bash
python3 plamen.py install        # macOS/Linux
python plamen.py install         # Windows
```

This is safe inside an AI assistant. It does not open the interactive
toolchain wizard.

Expected result:

- `~/.codex/plamen/` points at the Plamen methodology files
- `~/.codex/AGENTS.md` contains the Plamen marker block
- `~/.codex/config.toml` is generated or refreshed
- Python wrapper dependencies are installed

If install reports any non-critical dependency failure, stop and show the
failed dependency. The most common cause is cloning without submodules.

## Step 3: Add `plamen` to PATH

Linux:

```bash
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

macOS:

```bash
echo 'export PATH="$HOME/.plamen:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Windows PowerShell:

```powershell
[System.Environment]::SetEnvironmentVariable("Path", "$env:USERPROFILE\.plamen;" + [System.Environment]::GetEnvironmentVariable("Path", "User"), "User")
```

## Step 4: Verify

```bash
plamen help
plamen doctor
```

Do not run `plamen setup` or `plamen` with no args from this assistant
session. Those commands open an interactive terminal wizard. Tell the user to
run `plamen setup` from a real terminal when they want chain toolchains.

## Step 5: Optional RAG database

Do not run this from the AI session. Tell the user:

```bash
export SOLODIT_API_KEY=your_key_here
plamen rag
```

## Done

Report:

`Plamen installed at ~/.plamen and linked into ~/.codex/plamen/. Run plamen setup from a real terminal for chain toolchains, and plamen rag if you want the optional vulnerability database.`
