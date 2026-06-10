# Plamen LangGraph Phase-1 Refactor Plan

## Objective

Build a new LangGraph-based execution path for Plamen without mixing it into the existing driver implementation.

Phase 1 intentionally supports only one phase: `recon`.

The goal is to prove the new architecture can:

- create a run
- execute one Codex CLI worker through LangGraph
- write artifacts into the target project's `.scratchpad`
- record run, phase, and artifact status in SQLite
- leave the existing `plamen` CLI and `scripts/plamen_driver.py` behavior unchanged

## High-Level Architecture

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
              -> codex exec -C <repo> <prompt>
          -> artifact checker
          -> SQLite state store
      -> end
```

Long-term target architecture:

```text
LangGraph = phase orchestrator
Codex CLI = code/audit worker
SQLite = durable state and artifact index
Scratchpad = markdown artifact storage
Web UI = state and artifact viewer
Worktree/container = execution isolation
```

Phase 1 only implements the first vertical slice for `recon`.

## Directory Strategy

All new code goes under a new top-level directory:

```text
plamen_langgraph/
  README.md
  requirements.txt

  plamen_lg/
    __init__.py
    config.py
    state.py
    graph.py
    runner.py
    store.py
    phases.py
    artifacts.py

  cli.py

  examples/
    run_recon.py
```

This prevents confusion with the existing implementation:

- Do not put LangGraph code in `scripts/`.
- Do not modify `scripts/plamen_driver.py` for Phase 1.
- Do not change the default behavior of `plamen.py`.
- Do not replace existing checkpoint logic in Phase 1.

## Existing Assets To Reuse

The new implementation should reuse existing Plamen assets as read-only dependencies where practical.

Useful existing files:

- `scripts/plamen_types.py`
  - Source of canonical phase definitions.
  - Phase 1 only needs the `recon` phase definition from `SC_PHASES`.

- `scripts/plamen_prompt.py`
  - Source of existing phase prompt construction logic.
  - Prefer reuse over creating a divergent recon prompt format.

- `scripts/plamen_validators.py`
  - Source of artifact gate and validation logic.
  - Phase 1 can start with a simple file-existence check and then wire in stricter validators.

- `scripts/plamen_parsers.py`
  - Later useful for extracting structured findings and report inputs.
  - Not required for the first `recon` slice unless needed by prompt or validation reuse.

- `scripts/plamen_mechanical.py`
  - Useful later for deterministic report assembly.
  - Out of scope for Phase 1.

## Phase 1 Scope

Implement only:

```text
recon
```

Phase 1 must not implement:

- full SC phase graph
- L1 phase graph
- breadth/depth/verification/report phases
- dynamic verification shards
- dynamic report shards
- parallel Codex workers
- web UI
- full audit resume
- replacement of the legacy driver
- automatic integration into the existing `plamen core ...` command

## New CLI

Add a new entry point independent of the legacy CLI:

```bash
python -m plamen_langgraph.cli recon /path/to/project
```

Fallback direct execution may also be supported:

```bash
python plamen_langgraph/cli.py recon /path/to/project
```

Initial options:

```bash
python -m plamen_langgraph.cli recon /path/to/project \
  --mode core \
  --pipeline sc \
  --language auto \
  --db /path/to/project/.scratchpad/plamen_lg.sqlite
```

Defaults:

- `mode`: `core`
- `pipeline`: `sc`
- `language`: auto-detected if possible
- `scratchpad`: `<project>/.scratchpad`
- `db`: `<project>/.scratchpad/plamen_lg.sqlite`

## Codex Runner

Create `plamen_langgraph/plamen_lg/runner.py`.

Responsibilities:

- build a safe Codex CLI command
- run Codex non-interactively
- capture stdout and stderr
- save JSONL event stream when `--json` is enabled
- save the final assistant message with `--output-last-message`
- enforce timeout
- return a structured result

Recommended command shape:

```bash
codex exec \
  -C /path/to/project \
  --json \
  --output-last-message /path/to/project/.scratchpad/recon_last_message.md \
  "<prompt>"
```

Runner result shape:

```python
{
    "stdout_path": "...",
    "stderr_path": "...",
    "events_path": "...",
    "last_message_path": "...",
    "returncode": 0,
    "started_at": "...",
    "finished_at": "...",
    "duration_s": 123.4,
}
```

Security rules:

- Do not use `--dangerously-bypass-approvals-and-sandbox` by default.
- If dangerous mode is later added, require an isolated container or disposable worktree.
- Do not run multiple Codex workers against the same writable repository in Phase 1.

## LangGraph State

Create `plamen_langgraph/plamen_lg/state.py`.

Initial state type:

```python
from typing import TypedDict, Optional

class AuditState(TypedDict):
    run_id: str
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str
    mode: str
    language: str
    current_phase: str
    status: str
    error: Optional[str]
```

Phase 1 does not need a complex routing state. It only needs to run:

```text
START -> recon -> END
```

## LangGraph Graph

Create `plamen_langgraph/plamen_lg/graph.py`.

Graph shape:

```text
START
  -> recon
  -> END
```

The `recon` node should:

1. Load or construct the `recon` phase definition.
2. Build the recon prompt.
3. Insert a `phase_runs` row with status `running`.
4. Call `CodexRunner`.
5. Check expected artifacts.
6. Update `phase_runs` status to `succeeded` or `failed`.
7. Update the parent `runs` row.
8. Return updated state.

## Prompt Strategy

Preferred approach:

1. Reuse existing `scripts/plamen_prompt.py` to build a recon phase prompt.
2. Use the existing `SC_PHASES` `recon` definition from `scripts/plamen_types.py`.
3. Write the prompt snapshot to `.scratchpad/_lg_recon_prompt.md` for debugging.

If existing prompt construction is too tightly coupled to the legacy driver, use a temporary minimal recon prompt for Phase 1, but keep the compatibility target explicit:

```text
Phase 1 temporary prompt is acceptable only as a bridge.
Phase 2 should reuse the production prompt builder.
```

## Artifact Contract

For Phase 1, expect the same basic recon artifacts as the legacy `recon` phase:

```text
recon_summary.md
design_context.md
attack_surface.md
state_variables.md
function_list.md
contract_inventory.md
template_recommendations.md
detected_patterns.md
setter_list.md
emit_list.md
build_status.md
```

Artifact checker behavior:

- Check each expected artifact under `.scratchpad`.
- Record each artifact in SQLite with existence and size.
- Mark the phase failed if required artifacts are missing.
- Do not write or mutate legacy `_v2_checkpoint.json` in Phase 1.

Create `plamen_langgraph/plamen_lg/artifacts.py`.

Initial result shape:

```python
{
    "ok": True,
    "missing": [],
    "present": [
        {
            "path": "...",
            "size_bytes": 1234,
            "sha256": "...",
        }
    ],
}
```

## SQLite Store

Create `plamen_langgraph/plamen_lg/store.py`.

Phase 1 schema:

```sql
create table if not exists runs (
  id text primary key,
  project_root text not null,
  scratchpad text not null,
  phase text not null,
  status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists phase_runs (
  id text primary key,
  run_id text not null,
  phase_name text not null,
  status text not null,
  returncode integer,
  stdout_path text,
  stderr_path text,
  events_path text,
  output_path text,
  started_at text,
  finished_at text,
  error text,
  foreign key(run_id) references runs(id)
);

create table if not exists artifacts (
  id text primary key,
  run_id text not null,
  phase_name text not null,
  path text not null,
  exists integer not null,
  size_bytes integer,
  sha256 text,
  created_at text not null,
  foreign key(run_id) references runs(id)
);
```

State transitions:

```text
runs.status:
  pending -> running -> succeeded
                     -> failed

phase_runs.status:
  pending -> running -> succeeded
                         failed
                         timeout
```

## Configuration

Create `plamen_langgraph/plamen_lg/config.py`.

Initial config fields:

```python
{
    "project_root": "...",
    "scratchpad": "...",
    "db_path": "...",
    "pipeline": "sc",
    "mode": "core",
    "language": "evm|solana|aptos|sui|soroban|auto",
    "codex_bin": "codex",
    "timeout_s": 3000,
}
```

For Phase 1, config can be built directly from CLI args. It does not need to be compatible with every legacy `config.json` field.

## Isolation Rules

Phase 1 uses the target repository directly, but documents the future isolation model.

Rules for Phase 1:

- One run at a time per project.
- No parallel Codex subprocesses.
- Do not pass dangerous Codex sandbox bypass flags.
- Write only to `.scratchpad` unless Codex itself creates analysis files as part of the prompt.

Future isolation:

- one git worktree per worker
- or one container per worker
- SQLite records the worktree/container ID
- artifacts are copied back to the canonical scratchpad

## Logging And Debug Files

For a run with ID `<run_id>`, write:

```text
.scratchpad/
  plamen_lg.sqlite
  _lg_recon_prompt.md
  _lg_recon_stdout.log
  _lg_recon_stderr.log
  _lg_recon_events.jsonl
  _lg_recon_last_message.md
```

These files are separate from legacy driver files and should not collide with `_v2_checkpoint.json` or `_plamen.log`.

## Tests

Add tests under:

```text
plamen_langgraph/tests/
```

Phase 1 test targets:

- SQLite schema initializes.
- A run row can be created and updated.
- A phase row can be created and updated.
- Artifact checker detects present and missing files.
- Graph can run with a mocked `CodexRunner`.
- Mocked successful recon marks run as `succeeded`.
- Mocked missing artifacts marks run as `failed`.
- Legacy files such as `_v2_checkpoint.json` are not created or modified.

Do not require a real Codex CLI call in unit tests. Real Codex invocation can be covered by a manual smoke test.

## Manual Smoke Test

Use a small local repository as target:

```bash
python -m plamen_langgraph.cli recon /path/to/small/project
```

Then verify:

```bash
ls -la /path/to/small/project/.scratchpad
sqlite3 /path/to/small/project/.scratchpad/plamen_lg.sqlite ".tables"
sqlite3 /path/to/small/project/.scratchpad/plamen_lg.sqlite "select phase, status from runs;"
sqlite3 /path/to/small/project/.scratchpad/plamen_lg.sqlite "select phase_name, status, returncode from phase_runs;"
```

Expected result:

- `runs.status = succeeded` if all required recon artifacts exist.
- `phase_runs.status = succeeded`.
- required recon artifacts exist under `.scratchpad`.
- no legacy full-pipeline checkpoint is written by the new implementation.

## Acceptance Criteria

Phase 1 is complete when:

1. All new implementation files live under `plamen_langgraph/`.
2. Existing `plamen.py` and `scripts/plamen_driver.py` behavior is unchanged.
3. `python -m plamen_langgraph.cli recon /path/to/project` runs a LangGraph graph.
4. The graph executes exactly one phase: `recon`.
5. Codex CLI is invoked through a dedicated runner wrapper.
6. stdout, stderr, JSONL events, prompt snapshot, and final message are saved under `.scratchpad`.
7. SQLite records run, phase, and artifact status.
8. Recon artifacts are checked and recorded.
9. Unit tests pass with a mocked Codex runner.
10. A manual smoke test can run against a small repo.

## Phase 2 Preview

After Phase 1 works, the next step should not jump straight to the full pipeline.

Recommended Phase 2:

```text
recon -> inventory_prepare
```

Rationale:

- `inventory_prepare` is mostly mechanical.
- It validates multi-node graph routing without introducing heavy Codex workload.
- It keeps the blast radius small.

Recommended Phase 3:

```text
recon -> breadth
```

At that point, start addressing:

- worktree isolation
- parallel worker policy
- richer resume semantics
- compatibility with legacy artifact gates

## Migration Strategy

Keep both engines side by side until the LangGraph path is proven.

Future CLI shape:

```bash
plamen core /path/to/project --engine legacy
plamen core /path/to/project --engine langgraph
```

or:

```bash
PLAMEN_ENGINE=langgraph plamen core /path/to/project
```

Do not change the default engine until:

- SC light mode passes end to end
- resume behavior is equivalent or better
- artifact gates are equivalent
- failure handling is tested
- there is a migration path for existing `.scratchpad` runs

