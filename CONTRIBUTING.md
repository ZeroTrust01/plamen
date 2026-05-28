# Contributing to Plamen

Thanks for helping improve Plamen. The project is now Codex-native: runtime
instructions, generated adapter files, and docs should assume OpenAI Codex CLI
and the `~/.codex/plamen/` methodology root.

## How Plamen Works

Plamen is a deterministic multi-agent security auditing pipeline:

- `plamen.py` provides the terminal wrapper and installer
- `scripts/plamen_driver.py` owns phase sequencing and artifact gates
- `scripts/plamen_types.py` defines phases, modes, and model tier aliases
- `commands/` contains phase prompt surfaces used by the driver
- `prompts/` and `rules/` contain audit methodology
- `agents/` contains agent role definitions and skills
- `codex-adapter/` contains generated Codex config, roles, commands, and skills

The driver is the sole owner of phase sequencing. Do not move phase-order
policy into prompts or agent text.

## High-Impact Contributions

### Skills

Skills teach agents how to analyze a vulnerability class. Good skills:

- Explain methodology, not expected answers
- Define trigger conditions
- Include a step checklist
- Include false positives
- Stay under the local file-size cap
- Have been tested on a real codebase

Place standard skills under `agents/skills/{language}/{skill}/SKILL.md`,
injectable skills under `agents/skills/injectable/`, and focused niche skills
under `agents/skills/niche/`.

### Scanner Checks

Scanner templates live under `prompts/{language}/phase4b-scanner-templates.md`.
New checks should be broad, low-noise, and short.

### Driver and Wrapper Work

Changes to `scripts/plamen_driver.py`, parsers, validators, or `plamen.py`
should include focused regression coverage when possible. Keep runtime policy
in Python, not duplicated in prompt prose.

### L1 Methodology

L1 skills live under `agents/skills/injectable/l1/` and target Go/Rust node
clients. They should use L1 evidence tags and the L1 severity matrix.

## Local Setup

```bash
git clone --recurse-submodules https://github.com/PlamenTSV/plamen.git ~/.plamen
cd ~/.plamen
python3 plamen.py install
plamen doctor
```

After `git pull`, always run:

```bash
plamen install
```

Generated files such as `~/.codex/AGENTS.md` and `~/.codex/config.toml` are
copies, not symlinks.

## Testing

Useful checks:

```bash
python3 -m py_compile plamen.py scripts/plamen_types.py scripts/plamen_driver.py
python3 scripts/test_structural_integrity.py
python3 scripts/test_phase_containment_regression.py
```

For methodology changes, run an audit on a relevant target and inspect
`.scratchpad/` artifacts.

## Pull Requests

- Keep changes scoped to one concern
- Avoid secrets or real API keys
- Update generated Codex adapter files when generator inputs change
- Explain why the change improves audit quality or runtime reliability
- Include tests or a manual verification note

By contributing, you certify that you have the right to submit the work under
the project license.
