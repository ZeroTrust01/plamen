# Plamen LangGraph Phase 1-5 Refactor Plan

## Objective

Build a new LangGraph-based execution path for Plamen without mixing it into the existing driver implementation.

Phase 1 intentionally supports only one phase: `recon`.
Phase 2 extends the same execution path to the second canonical smart-contract phase: `instantiate`.
Phase 3 extends the same prefix to the third canonical smart-contract phase:
`breadth`.
Phase 4 extends the same prefix to the mandatory additional breadth pass:
`rescan`.
Phase 5 extends the same prefix to a single canonical `inventory` phase that
consolidates all discovery outputs.

The Phase 1 goal is to prove the new architecture can:

- create a run
- execute one Codex CLI worker through LangGraph
- write artifacts into the target project's LangGraph scratchpad
- record run, phase, and artifact status in SQLite
- leave the existing `plamen` CLI and `scripts/plamen_driver.py` behavior unchanged

The Phase 2 goal is to prove that the architecture can:

- execute a two-node phase graph: `recon -> instantiate`
- preserve phase ordering and stop after a failed upstream phase
- write and validate `spawn_manifest.md`
- record multiple `phase_runs` rows for one run
- keep the legacy driver and legacy checkpoint behavior untouched

The Phase 3 goal is to prove that the architecture can:

- execute a three-node phase graph: `recon -> instantiate -> breadth`
- consume `spawn_manifest.md` as the authoritative breadth contract
- produce every manifest-derived first-pass `analysis_*.md` output
- fail the breadth phase when any manifest-derived output is missing or stub
- execute one explicitly requested phase node when its predecessor phases have
  already succeeded in a referenced LangGraph run
- record breadth artifacts and phase status in SQLite
- still avoid legacy driver/checkpoint mutation

The Phase 4 goal is to prove that the architecture can:

- execute a four-node all-mode graph:
  `recon -> instantiate -> breadth -> rescan`
- consume first-pass breadth outputs as an exclusion set
- produce bounded additional discovery artifacts:
  `analysis_rescan_*.md` and `analysis_percontract_*.md`
- fail the rescan phase when first-pass breadth prerequisites are incomplete
  or when rescan outputs are missing, stub, duplicated from first pass, or
  outside the rescan-owned output families
- execute `rescan` as an explicitly requested single node when
  `recon`, `instantiate`, and `breadth` already succeeded in a referenced
  LangGraph run
- record rescan artifacts and phase status in SQLite
- still avoid legacy driver/checkpoint mutation

The Phase 5 goal is to prove that the architecture can:

- execute a five-node graph:
  `recon -> instantiate -> breadth -> rescan -> inventory`
- treat `rescan` as a required discovery producer in every mode
- consolidate first-pass breadth, rescan, and per-contract discovery artifacts
  into one canonical `findings_inventory.md`
- fail closed before invoking Codex when the discovery source set is too large
  for a single inventory phase
- fail the inventory phase when `findings_inventory.md` is missing, stub, or
  structurally incomplete
- record inventory artifacts and phase status in SQLite
- still avoid legacy driver/checkpoint mutation

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

Phase 2 target shape:

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
          -> recon artifact checker
          -> SQLite state store
      -> instantiate phase node
          -> CodexRunner
          -> spawn_manifest schema gate
          -> SQLite state store
      -> end
```

Phase 3 target shape:

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
          -> recon artifact checker
          -> SQLite state store
      -> instantiate phase node
          -> CodexRunner
          -> spawn_manifest schema gate
          -> SQLite state store
      -> breadth phase node
          -> spawn_manifest parser
          -> CodexRunner
          -> manifest-exact analysis output gate
          -> SQLite state store
      -> end
```

Phase 4 target shape:

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
          -> CodexRunner
          -> recon artifact checker
          -> SQLite state store
      -> instantiate phase node
          -> CodexRunner
          -> spawn_manifest schema gate
          -> SQLite state store
      -> breadth phase node
          -> spawn_manifest parser
          -> CodexRunner
          -> manifest-exact analysis output gate
          -> SQLite state store
      -> rescan phase node
          -> first-pass breadth output collector
          -> duplicate/exclusion prompt builder
          -> CodexRunner
          -> rescan/per-contract output gate
          -> SQLite state store
      -> end
```

Phase 5 target shape:

```text
new CLI entry
  -> LangGraph graph
      -> recon phase node
      -> instantiate phase node
      -> breadth phase node
      -> rescan phase node
      -> inventory phase node
          -> discovery source collector
          -> fail-closed source-size gate
          -> CodexRunner
          -> findings_inventory.md structural gate
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
Phase 2 implements the next canonical SC phase without adding breadth workers yet.
Phase 3 implements the first breadth slice without replacing the legacy
parallel worker scheduler. The initial LangGraph breadth node should run as a
single phase node and may use one Codex subprocess to complete all open
manifest outputs. Python-level fan-out, per-agent worktrees, and container
isolation are follow-on work after manifest-exact completion is proven.
Phase 4 implements the mandatory rescan slice without replacing the legacy
parallel worker scheduler. The initial LangGraph rescan node should run
as a single phase node and may use one Codex subprocess to complete the bounded
rescan/per-contract output set.
Phase 5 deliberately does not port the legacy `inventory_prepare` and
`inventory_chunk_a/b/c` split. The initial LangGraph inventory node should run
as one direct phase node and fail closed when the discovery source set is too
large for a safe single-pass inventory.

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
- Do not modify `scripts/plamen_driver.py` for Phase 1, Phase 2, Phase 3, or
  Phase 4.
- Do not change the default behavior of `plamen.py`.
- Do not replace existing checkpoint logic in Phase 1, Phase 2, Phase 3, or
  Phase 4.

## Existing Assets To Reuse

The new implementation should reuse existing Plamen assets as read-only dependencies where practical.

Useful existing files:

- `scripts/plamen_types.py`
  - Source of canonical phase definitions.
  - Phase 1 needs the `recon` phase definition from `SC_PHASES`.
  - Phase 2 needs the `instantiate` phase definition from `SC_PHASES`.
  - Phase 3 needs the `breadth` phase definition from `SC_PHASES`.
  - Phase 4 needs the `rescan` phase definition from `SC_PHASES`.

- `scripts/plamen_prompt.py`
  - Source of existing phase prompt construction logic.
  - Prefer reuse over creating divergent prompt formats.
  - Phase 2 should reuse `prompts/shared/v2/phase2-instantiate.md` as the methodology body with a LangGraph direct-execution wrapper.

- `scripts/plamen_validators.py`
  - Source of artifact gate and validation logic.
  - Phase 1 can start with a simple file-existence check and then wire in stricter validators.
  - Phase 2 should reuse `_validate_spawn_manifest_schema()` or an equivalent local wrapper that uses the same parser contract.
  - Phase 3 should reuse the breadth manifest-exact output contract already
    enforced for `analysis_*.md`, or a local wrapper with matching accepted and
    rejected examples.
  - Phase 4 should start with a LangGraph-local validator for rescan-owned
    artifact families, then align with any legacy rescan gate if one is later
    factored into a reusable function.

- `scripts/plamen_parsers.py`
  - Source of `parse_breadth_manifest_outputs()` and
    `parse_breadth_manifest_count()`.
  - Phase 3 should reuse these parser semantics or keep local compatibility
    tests aligned with them.
  - Phase 4 should reuse Phase 3's parsed breadth outputs as the first-pass
    exclusion set; do not re-parse arbitrary `analysis_*.md` files as
    successful breadth outputs.

- `prompts/shared/v2/phase4-rescan.md`
  - Target location for the rescan methodology body.
  - If the repository still stores the rescan prompt under an older numbered
    filename, rename or copy it to this Phase 4 path as part of the Phase 4
    implementation.
  - Phase 4 should wrap this prompt for direct LangGraph execution and strip
    or override legacy-driver-only assumptions.

- `scripts/plamen_mechanical.py`
  - Useful later for deterministic report assembly.
  - Out of scope for Phase 1, Phase 2, Phase 3, and Phase 4.

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

Phase 2 should add a second command that runs the supported SC prefix through
`instantiate`:

```bash
python -m plamen_langgraph.cli instantiate /path/to/project
```

The `instantiate` command must execute both supported nodes:

```text
recon -> instantiate
```

It must not skip `recon` implicitly. A later automatic resume design can reuse
existing recon artifacts, but Phase 2 keeps execution simple and deterministic.

Phase 3 should add a third command that runs the supported SC prefix through
`breadth`:

```bash
python -m plamen_langgraph.cli breadth /path/to/project
```

The `breadth` command must execute all supported nodes in order:

```text
recon -> instantiate -> breadth
```

It must not skip `recon` or `instantiate` implicitly. A later automatic resume
design can reuse prior artifacts, but Phase 3 keeps execution deterministic:
if an upstream node fails, downstream nodes are not created or run.

Phase 3 should also add an explicit single-node execution mode for developer
iteration and failed-tail recovery:

```bash
python -m plamen_langgraph.cli instantiate /path/to/project \
  --single-node \
  --base-run-id <successful-recon-run-id>

python -m plamen_langgraph.cli breadth /path/to/project \
  --single-node \
  --base-run-id <successful-instantiate-run-id>
```

Single-node mode is not automatic resume. It must be opt-in, must require an
explicit `--base-run-id` for phases with predecessors, and must validate that
all predecessor phases succeeded in that base run before the target node runs.
The default `instantiate` and `breadth` commands still execute the full
supported prefix.

Phase 4 should add a fourth command that runs the supported SC prefix through
`rescan` in every mode:

```bash
python -m plamen_langgraph.cli rescan /path/to/project --mode core
```

The `rescan` command must execute all supported nodes in order:

```text
recon -> instantiate -> breadth -> rescan
```

`rescan` is mandatory for Light, Core, and Thorough. Do not silently skip it
based on mode in the experimental LangGraph CLI.

Phase 4 should also extend explicit single-node execution:

```bash
python -m plamen_langgraph.cli rescan /path/to/project \
  --mode core \
  --single-node \
  --base-run-id <successful-breadth-run-id>
```

Single-node `rescan` must require an explicit `--base-run-id` and must validate
that `recon`, `instantiate`, and `breadth` succeeded in that base run before
the target node runs. It is still not automatic resume.

Fallback direct execution may also be supported:

```bash
python plamen_langgraph/cli.py recon /path/to/project
python plamen_langgraph/cli.py instantiate /path/to/project
python plamen_langgraph/cli.py breadth /path/to/project
python plamen_langgraph/cli.py rescan /path/to/project --mode core
```

Initial options:

```bash
python -m plamen_langgraph.cli recon /path/to/project \
  --mode core \
  --pipeline sc \
  --language auto \
  --db /path/to/project/.lg_scratchpad/plamen_lg.sqlite
```

Defaults:

- `mode`: `core`
- `pipeline`: `sc`
- `language`: auto-detected if possible
- `scratchpad`: `<project>/.lg_scratchpad`
- `db`: `<project>/.lg_scratchpad/plamen_lg.sqlite`

Phase 2 CLI implementation tasks:

1. Keep the existing `recon` command behavior unchanged.
2. Add `instantiate` with the same options as `recon`.
3. Route `recon` to a graph with `target_phase = "recon"`.
4. Route `instantiate` to a graph with `target_phase = "instantiate"`.
5. Print the same run summary fields: `run_id`, `status`, `scratchpad`, and `db`.
6. Return exit code `0` only when the requested target phase succeeds.

Phase 3 CLI implementation tasks:

1. Keep the existing `recon` and `instantiate` command behavior unchanged.
2. Add `breadth` with the same options as `recon` and `instantiate`.
3. Route `breadth` to a graph with `target_phase = "breadth"`.
4. Add `--single-node` and `--base-run-id` to phase commands.
5. In prefix mode, print the same run summary fields: `run_id`, `status`,
   `scratchpad`, and `db`.
6. In single-node mode, also print `execution_mode: single_node` and
   `base_run_id: <id>`.
7. Return exit code `0` only when the requested target phase succeeds.
8. Return a non-zero exit code if prerequisite validation fails or the target
   node fails.

Phase 4 CLI implementation tasks:

1. Keep the existing `recon`, `instantiate`, and `breadth` command behavior
   unchanged.
2. Add `rescan` with the same options as `breadth`.
3. Route prefix-mode `rescan` to a graph with `target_phase = "rescan"`.
4. Run `rescan` for every supported mode: `light`, `core`, and `thorough`.
5. Preserve `--single-node` and `--base-run-id` semantics.
6. In prefix mode, print the same run summary fields: `run_id`, `status`,
   `scratchpad`, and `db`.
7. In single-node mode, also print `execution_mode: single_node` and
   `base_run_id: <id>`.
8. Return exit code `0` only when the requested target phase succeeds.
9. Return a non-zero exit code if prerequisite validation or the target node
   fails.

Phase 5 CLI implementation tasks:

1. Keep the existing `recon`, `instantiate`, `breadth`, and `rescan` command
   behavior unchanged.
2. Add `inventory` with the same options as `rescan`.
3. Route prefix-mode `inventory` to a graph with `target_phase = "inventory"`.
4. Preserve `--single-node` and `--base-run-id` semantics.
5. In prefix mode, print the same run summary fields: `run_id`, `status`,
   `scratchpad`, and `db`.
6. In single-node mode, also print `execution_mode: single_node` and
   `base_run_id: <id>`.
7. Return exit code `0` only when the requested target phase succeeds.
8. Return a non-zero exit code if prerequisite validation, discovery-size
   gating, or the inventory node fails.

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
  --output-last-message /path/to/project/.lg_scratchpad/recon_last_message.md \
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
- Do not run multiple Codex workers against the same writable repository in Phase 1 or Phase 2.
- Phase 2 still runs workers sequentially.
- Phase 3 initial implementation should still avoid Python-level parallel
  Codex workers against the same writable repository. The breadth phase may be
  implemented as one manifest-aware Codex subprocess that completes all open
  first-pass outputs, or as sequential per-output subprocesses if that is
  simpler to test. Do not add concurrent worker fan-out until isolation exists.
- Phase 4 keeps the same constraint: the rescan phase should be one direct
  Codex subprocess that writes all required additional outputs. Python-level
  parallel rescan/per-contract workers are deferred until isolation exists.

## LangGraph State

Create `plamen_langgraph/plamen_lg/state.py`.

Initial state type:

```python
from typing import TypedDict, Optional

class AuditState(TypedDict):
    run_id: str
    base_run_id: Optional[str]
    project_root: str
    scratchpad: str
    db_path: str
    pipeline: str
    mode: str
    language: str
    execution_mode: str  # "prefix" or "single_node"
    current_phase: str
    target_phase: str
    completed_phases: list[str]
    failed_phase: Optional[str]
    status: str
    error: Optional[str]
```

Phase 1 does not need a complex routing state. It only needs to run:

```text
START -> recon -> END
```

Routing can keep deterministic:

```text
target_phase = "recon":       START -> recon -> END
target_phase = "instantiate": START -> recon -> instantiate -> END
target_phase = "breadth":     START -> recon -> instantiate -> breadth -> END
target_phase = "rescan":      START -> recon -> instantiate -> breadth -> rescan -> END
target_phase = "inventory":   START -> recon -> instantiate -> breadth -> rescan -> inventory -> END
```

Single-node mode keeps routing deterministic but starts at exactly the requested
node after prerequisite validation:

```text
single_node phase = "recon":       START -> recon -> END
single_node phase = "instantiate": START -> instantiate -> END
single_node phase = "breadth":     START -> breadth -> END
single_node phase = "rescan":      START -> rescan -> END
single_node phase = "inventory":   START -> inventory -> END
```

Do not add dynamic branching for later phases in Phase 2, Phase 3, Phase 4,
or Phase 5. The only conditional behavior should be:

- `instantiate` returns immediately with failed state if `recon` did not succeed.
- `breadth` returns immediately with failed state if `instantiate` did not succeed.
- `rescan` returns immediately with failed state if `breadth` did not succeed.
- `inventory` returns immediately with failed state if `rescan` did not succeed
  or if the discovery source set exceeds the single-phase inventory threshold.
- single-node `instantiate` is allowed only when the base run has successful
  `recon` state and valid recon artifacts.
- single-node `breadth` is allowed only when the base run has successful
  `recon` and `instantiate` state plus valid `spawn_manifest.md`.
- single-node `rescan` is allowed only when the base run has successful
  `recon`, `instantiate`, and `breadth` state plus valid breadth outputs.
- single-node `inventory` is allowed only when the base run has successful
  `recon`, `instantiate`, `breadth`, and `rescan` state plus valid discovery
  outputs.

## LangGraph Graph

Create `plamen_langgraph/plamen_lg/graph.py`.

Graph shape:

```text
START
  -> recon
  -> END
```

Phase 2 graph shape:

```text
START
  -> recon
  -> instantiate
  -> END
```

Phase 3 graph shape:

```text
START
  -> recon
  -> instantiate
  -> breadth
  -> END
```

Phase 4 graph shape:

```text
START
  -> recon
  -> instantiate
  -> breadth
  -> rescan
  -> END
```

Phase 5 graph shape:

```text
START
  -> recon
  -> instantiate
  -> breadth
  -> rescan
  -> inventory
  -> END
```

The implementation can use one graph builder with a `target_phase` argument and
small wrappers:

```python
run_recon_graph(config, runner=None)
run_instantiate_graph(config, runner=None)
run_breadth_graph(config, runner=None)
run_rescan_graph(config, runner=None)
run_inventory_graph(config, runner=None)
run_phase_node(config, phase_name, base_run_id, runner=None)
```

Preferred internal API:

```python
run_graph(config, target_phase="recon", runner=None)
```

Then keep `run_recon_graph()` as a compatibility wrapper for existing tests.
Add `run_instantiate_graph()` and `run_breadth_graph()` as thin wrappers so
tests and examples do not need to duplicate target strings.
Add `run_rescan_graph()` as the same style of thin wrapper for Phase 4.
Add `run_inventory_graph()` as the same style of thin wrapper for Phase 5.
Add `run_phase_node()` for explicit single-node execution. It should create a
new LangGraph run row linked to `base_run_id`, seed `completed_phases` from the
validated predecessor set, and invoke only the requested phase node.

The `recon` node should:

1. Load or construct the `recon` phase definition.
2. Build the recon prompt.
3. Insert a `phase_runs` row with status `running`.
4. Call `CodexRunner`.
5. Check expected artifacts.
6. Update `phase_runs` status to `succeeded` or `failed`.
7. Update the parent `runs` row.
8. Return updated state.

The `instantiate` node should:

1. Check that `state["status"] == "succeeded"` and `recon` is in `completed_phases`.
2. Load or construct the `instantiate` phase definition.
3. Build a Phase 2 direct-execution prompt.
4. Write the prompt snapshot to `_lg_instantiate_prompt.md`.
5. Insert a `phase_runs` row with status `running`.
6. Call `CodexRunner`.
7. Check that `spawn_manifest.md` exists and is substantial.
8. Validate `spawn_manifest.md` with the legacy-compatible schema gate.
9. Record the artifact row for `spawn_manifest.md`.
10. Update `phase_runs` and parent `runs` to `succeeded`, `failed`, or `timeout`.
11. Append `instantiate` to `completed_phases` only on success.
12. Return updated state.

The `breadth` node should:

1. Check that `state["status"] == "succeeded"` and `instantiate` is in
   `completed_phases`.
2. Re-validate `spawn_manifest.md` before starting breadth work. Producer-side
   validation in `instantiate` is not enough because users may edit scratchpad
   files between runs.
3. Parse manifest-derived first-pass breadth outputs from `spawn_manifest.md`.
   Use `scripts/plamen_parsers.py::parse_breadth_manifest_outputs()` semantics
   or a local compatibility parser.
4. Build the open-output list from manifest-derived outputs whose files are
   missing or smaller than the breadth minimum byte threshold.
5. If every manifest-derived output is already substantial, create and mark the
   `breadth` `phase_runs` row as `succeeded` without invoking Codex.
6. Otherwise build a Phase 3 direct-execution prompt and write it to
   `_lg_breadth_prompt.md`.
7. Insert a `phase_runs` row with status `running`.
8. Call `CodexRunner`.
9. Re-parse `spawn_manifest.md` and re-check every expected `analysis_*.md`
   output. Ignore non-manifest `analysis_*.md` files for completion.
10. Record one artifact row per manifest-derived output with
    `phase_name = "breadth"`.
11. Mark the phase failed if any expected output is missing, stub, or has a
    forbidden later-phase filename family such as `analysis_rescan_*.md`,
    `analysis_percontract_*.md`, inventory, depth, chain, verification, or
    report artifacts.
12. Update `phase_runs` and parent `runs` to `succeeded`, `failed`, or `timeout`.
13. Append `breadth` to `completed_phases` only on success.
14. Return updated state.

The `rescan` node should:

1. Check that `state["status"] == "succeeded"` and `breadth` is in
   `completed_phases`.
2. Re-validate `spawn_manifest.md` and every manifest-derived first-pass
   breadth output before starting rescan work.
3. Build the first-pass exclusion set from manifest-derived breadth outputs
   only. Do not include prior `analysis_rescan_*.md` or
   `analysis_percontract_*.md` files in the first-pass exclusion set.
4. Build a deterministic open-output list for the initial LangGraph rescan
   contract:
   - `analysis_rescan_gap_sweep.md`
   - `analysis_rescan_cross_check.md`
   - `analysis_percontract_scope_review.md`
5. If every required rescan output is already substantial, create and mark the
   `rescan` `phase_runs` row as `succeeded` without invoking Codex.
6. Otherwise build a Phase 4 direct-execution prompt and write it to
   `_lg_rescan_prompt.md`.
7. Insert a `phase_runs` row with status `running`.
8. Call `CodexRunner`.
9. Re-check every required rescan/per-contract output.
10. Record one artifact row per required rescan output with
    `phase_name = "rescan"`.
11. Mark the phase failed if any required output is missing, stub, empty of
    substantive findings/coverage notes, or if the worker wrote forbidden
    later-phase artifacts such as inventory, depth, chain, verification, or
    report artifacts.
12. Update `phase_runs` and parent `runs` to `succeeded`, `failed`, or
    `timeout`.
13. Append `rescan` to `completed_phases` only on success.
14. Return updated state.

The `inventory` node should:

1. Check that `state["status"] == "succeeded"` and `rescan` is in
   `completed_phases`.
2. Re-run the breadth and rescan artifact gates before starting inventory work.
3. Collect discovery source files from the configured LangGraph scratchpad:
   - manifest-derived first-pass `analysis_*.md`
   - required and extra `analysis_rescan_*.md`
   - required and extra `analysis_percontract_*.md`
4. Fail before invoking Codex if the discovery source set exceeds either
   single-phase inventory threshold:
   - file count greater than `INVENTORY_MAX_SOURCE_FILES`
   - total source bytes greater than `INVENTORY_MAX_SOURCE_BYTES`
5. Build a Phase 5 direct-execution prompt and write it to
   `_lg_inventory_prompt.md`.
6. Insert a `phase_runs` row with status `running`.
7. Call `CodexRunner`.
8. Re-check `findings_inventory.md`.
9. Record one artifact row for `findings_inventory.md` with
   `phase_name = "inventory"`.
10. Mark the phase failed if `findings_inventory.md` is missing, stub,
    structurally incomplete, or if the worker wrote forbidden later-phase
    artifacts such as depth, chain, verification, or report artifacts.
11. Update `phase_runs` and parent `runs` to `succeeded`, `failed`, or
    `timeout`.
12. Append `inventory` to `completed_phases` only on success.
13. Return updated state.

Single-node prerequisite validation should run before constructing the graph:

1. Load the base run by `--base-run-id` from the configured SQLite DB.
2. Check that the base run belongs to the same `project_root` and `scratchpad`.
3. Check that each predecessor phase has a `phase_runs.status = succeeded` row
   in the base run:
   - `instantiate` requires `recon`
   - `breadth` requires `recon` and `instantiate`
   - `rescan` requires `recon`, `instantiate`, and `breadth`
   - `inventory` requires `recon`, `instantiate`, `breadth`, and `rescan`
4. Re-run artifact gates for predecessor outputs instead of trusting only DB
   status:
   - `recon`: required recon artifacts exist and pass recon validation
   - `instantiate`: `spawn_manifest.md` exists and passes the schema gate
   - `breadth`: `spawn_manifest.md` is valid and manifest-derived
     `analysis_*.md` outputs exist and pass the breadth gate
   - `rescan`: required `analysis_rescan_*.md` and
     `analysis_percontract_*.md` outputs exist and pass the rescan gate
5. Fail before invoking Codex if any prerequisite check fails.
6. Create a new run row with `execution_mode = "single_node"` and
   `base_run_id = <base-run-id>`.
7. Do not create new `phase_runs` rows for predecessor phases in the new run.
   The new run records only the target node execution.

## Prompt Strategy

Phase 1 preferred approach:

1. Reuse existing `scripts/plamen_prompt.py` to build a recon phase prompt.
2. Use the existing `SC_PHASES` `recon` definition from `scripts/plamen_types.py`.
3. Write the prompt snapshot to `.lg_scratchpad/_lg_recon_prompt.md` for debugging.

If existing prompt construction is too tightly coupled to the legacy driver, use a temporary minimal recon prompt for Phase 1, but keep the compatibility target explicit:

```text
Phase 1 temporary prompt is acceptable only as a bridge.
Phase 2 should reuse production Phase 2 methodology content.
```

Phase 2 prompt requirements:

1. Add `build_instantiate_prompt(config)` in `plamen_langgraph/plamen_lg/phases.py`.
2. Load `prompts/shared/v2/phase2-instantiate.md` from the Plamen installation root.
3. Wrap that methodology in a LangGraph direct-execution prompt that provides:
   - project root
   - scratchpad
   - pipeline
   - mode
   - language
   - required recon input artifacts
   - required output artifact: `spawn_manifest.md`
4. Explicitly scope the worker to Phase 2 only:
   - read recon artifacts
   - write only `spawn_manifest.md` and optional debug notes with `_lg_` prefix
   - do not run breadth, inventory, depth, verification, scoring, or report work
   - do not spawn subagents from inside the Phase 2 worker
5. Include the machine-readable table contract from `phase2-instantiate.md`.
6. Write `_lg_instantiate_prompt.md` before calling Codex.

The Phase 2 direct-execution wrapper should not invoke the legacy orchestrator
prompt wholesale if doing so leaks future phase control flow or `Task(...)`
subagent directives. Reusing the standalone shared V2 prompt body is the
compatibility target.

Phase 3 prompt requirements:

1. Add `build_breadth_prompt(config, open_outputs=None)` in
   `plamen_langgraph/plamen_lg/phases.py`.
2. Load `prompts/shared/v2/phase3-breadth.md` from the Plamen installation root
   as the methodology body.
3. Wrap that methodology in a LangGraph direct-execution prompt that provides:
   - project root
   - scratchpad
   - pipeline
   - mode
   - language
   - required input artifact: `spawn_manifest.md`
   - manifest-derived expected output list
   - current open-output list, if any
   - required output family: first-pass `analysis_*.md` files named by the
     manifest
4. Explicitly scope the worker to Phase 3 only:
   - read `spawn_manifest.md`, recon artifacts, and target source files as
     needed for breadth analysis
   - write only manifest-derived first-pass `analysis_*.md` outputs,
     `violations.md`, and optional debug notes with `_lg_` prefix
   - do not write `analysis_rescan_*.md`, `analysis_percontract_*.md`,
     inventory, depth, chain, verification, scoring, or report artifacts
   - do not proceed to inventory synthesis
5. Tell the worker that `spawn_manifest.md` is authoritative. It must not invent
   additional output filenames, count non-manifest analysis files as complete,
   or treat the manifest `Status` column as authoritative over filesystem
   existence and size.
6. Include a direct-execution fallback rule: if this Codex execution environment
   does not expose subagent/task tools, the breadth worker should perform the
   missing breadth analyses itself sequentially and still write exactly the
   manifest-derived outputs. This keeps Phase 3 implementable before
   LangGraph-level parallel worker fan-out exists.
7. Write `_lg_breadth_prompt.md` before calling Codex.

The Phase 3 direct-execution wrapper may reuse the shared V2 breadth body, but
it must override any legacy-driver-only assumptions. The LangGraph contract is
manifest-exact artifact completion under `.lg_scratchpad`, not legacy
checkpoint progression.

Phase 4 prompt requirements:

1. Add `build_rescan_prompt(config, open_outputs=None)` in
   `plamen_langgraph/plamen_lg/phases.py`.
2. Load `prompts/shared/v2/phase4-rescan.md` from the Plamen installation
   root as the methodology body.
3. Wrap that methodology in a LangGraph direct-execution prompt that provides:
   - project root
   - scratchpad
   - pipeline
   - mode
   - language
   - required input artifact: `spawn_manifest.md`
   - manifest-derived first-pass breadth output list
   - first-pass exclusion summary generated from the breadth outputs
   - current open-output list, if any
   - required output files for the initial LangGraph contract:
     `analysis_rescan_gap_sweep.md`,
     `analysis_rescan_cross_check.md`, and
     `analysis_percontract_scope_review.md`
4. Explicitly scope the worker to Phase 4 only:
   - read `spawn_manifest.md`, recon artifacts, first-pass breadth outputs,
     and target source files as needed for additional breadth analysis
   - write only `analysis_rescan_*.md`, `analysis_percontract_*.md`,
     `violations.md`, and optional debug notes with `_lg_` prefix
   - do not write first-pass `analysis_*.md` outputs unless they are missing
     prerequisites and the phase should fail before invoking Codex
   - do not write inventory, semantic invariants, depth, RAG, chain,
     verification, scoring, or report artifacts
5. Tell the worker that first-pass breadth outputs are an exclusion set. It
   must not re-report the same root cause or same location with a renamed
   title.
6. Include a direct-execution fallback rule: if this Codex execution
   environment does not expose subagent/task tools, the rescan worker should
   perform the additional sweeps sequentially and still write exactly the
   required rescan outputs.
7. Write `_lg_rescan_prompt.md` before calling Codex.

The Phase 4 direct-execution wrapper may reuse the shared V2 rescan body, but
it must override legacy-driver-only assumptions. The LangGraph contract is
bounded additional artifact completion under `.lg_scratchpad`, not legacy
checkpoint progression.

Phase 5 prompt requirements:

1. Add `build_inventory_prompt(config, source_files=None)` in
   `plamen_langgraph/plamen_lg/phases.py`.
2. Load `prompts/shared/v2/phase4a-inventory-base.md` from the Plamen
   installation root as the methodology body.
3. Wrap that methodology in a LangGraph direct-execution prompt that provides:
   - project root
   - scratchpad
   - pipeline
   - mode
   - language
   - exact discovery source file list
   - required output artifact: `findings_inventory.md`
   - source file count and total source byte summary
4. Explicitly scope the worker to the single LangGraph inventory phase only:
   - read recon artifacts and the provided discovery source files
   - write only `findings_inventory.md`, `violations.md`, and optional debug
     notes with `_lg_` prefix
   - do not write `findings_inventory_chunk_*.md`,
     `inventory_shard_plan.md`, or `inventory_chunk_*.manifest.md`
   - do not write semantic invariants, depth, RAG, chain, verification,
     scoring, or report artifacts
5. Tell the worker that the discovery source file list is authoritative. It
   must not invent additional source files, skip listed files, or treat stale
   legacy `.scratchpad` files as inputs.
6. Write `_lg_inventory_prompt.md` before calling Codex.

The Phase 5 direct-execution wrapper may reuse the shared V2 inventory base
methodology, but it must override the legacy sharded inventory architecture.
The LangGraph contract is one canonical `findings_inventory.md` under
`.lg_scratchpad`, not `inventory_prepare` plus chunk/merge phases.

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

- Check each expected artifact under the configured LangGraph scratchpad.
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

Phase 2 artifact contract:

```text
spawn_manifest.md
```

`spawn_manifest.md` must follow the producer-side schema already enforced by
`scripts/plamen_validators.py::_validate_spawn_manifest_schema()`:

- file exists under the configured LangGraph scratchpad
- file size is at least 50 bytes
- first parseable breadth-agent table includes `Template` and `Required?` columns
- every spawned `AGENT` row has a unique agent identifier
- every spawned `AGENT` row maps to a distinct first-pass `analysis_*.md` output
- no spawned row points at `verify_*.md`, `analysis_rescan_*.md`,
  `analysis_percontract_*.md`, `analysis_merged_into_*.md`, inventory, depth,
  chain, verification, or report artifacts

Implementation tasks:

1. Keep `check_artifacts()` for generic existence/size/hash recording.
2. Add a phase-specific validator hook:

   ```python
   validate_phase_artifacts(phase_name, scratchpad, records) -> list[str]
   ```

3. For `recon`, the validator can return `[]` after the existing file checks.
4. For `instantiate`, call the spawn manifest schema gate after the generic file check.
5. If importing `_validate_spawn_manifest_schema()` pulls in too much legacy state,
   add a local compatibility validator and tests that assert the same accepted and
   rejected examples.

Phase 3 artifact contract:

```text
analysis_*.md
```

For Phase 3, the static glob is only the broad artifact family. Completion is
manifest-exact:

- `spawn_manifest.md` must exist and remain schema-valid.
- Parse the exact first-pass breadth output filenames declared by spawned
  breadth-agent rows in `spawn_manifest.md`.
- Every parsed output must exist under the configured LangGraph scratchpad.
- Every parsed output must be substantial. Use the legacy breadth threshold
  where practical; the shared V2 prompt currently uses 200 bytes for the
  completion loop, while the legacy `Phase` default minimum is 100 bytes. Pick
  one threshold in code and tests, document it, and keep the prompt and gate in
  sync. Prefer 200 bytes for Phase 3 to match the current prompt.
- Non-manifest `analysis_*.md` files do not satisfy missing manifest outputs.
- `analysis_rescan_*.md`, `analysis_percontract_*.md`,
  `analysis_merged_into_*.md`, `analysis_report_*.md`, inventory, depth, chain,
  verification, scoring, and report files are not breadth outputs.

Phase 3 implementation tasks:

1. Add `parse_breadth_outputs(scratchpad)` or import
   `parse_breadth_manifest_outputs()` behind a small local wrapper.
2. Add `expected_breadth_artifacts(scratchpad) -> list[str]` that returns the
   manifest-derived output filenames.
3. Teach the breadth node to call `check_artifacts()` with explicit
   manifest-derived filenames, not just `["analysis_*.md"]`.
4. Add `validate_phase_artifacts("breadth", scratchpad, records)` with
   manifest-exact checks:
   - invalid/missing `spawn_manifest.md`
   - zero parseable breadth outputs
   - missing expected output
   - stub expected output
   - forbidden later-phase output family
5. Record only manifest-derived expected outputs as required breadth artifacts.
   Extra non-manifest analysis files can be ignored or recorded as debug
   extras later, but they must not make the phase pass.

Phase 4 artifact contract:

```text
analysis_rescan_*.md
analysis_percontract_*.md
```

For the initial LangGraph rescan implementation, use a deterministic minimum
output set instead of a dynamic rescan manifest:

```text
analysis_rescan_gap_sweep.md
analysis_rescan_cross_check.md
analysis_percontract_scope_review.md
```

Completion rules:

- `spawn_manifest.md` must exist and remain schema-valid.
- Manifest-derived first-pass breadth outputs must still pass the Phase 3
  breadth gate before rescan starts.
- Every required rescan output must exist under the configured LangGraph
  scratchpad.
- Every required rescan output must be substantial. Use a single
  `RESCAN_MIN_BYTES` constant and keep prompt/tests in sync. Prefer 200 bytes
  to match the breadth gate.
- `analysis_rescan_*.md` files must describe additional findings or explicit
  negative coverage against under-explored surfaces, not copies of first-pass
  breadth text.
- `analysis_percontract_scope_review.md` must either contain per-contract or
  inheritance-cluster review notes, or a substantive explanation of why no
  meaningful cluster exists and what files were checked.
- First-pass `analysis_*.md` files do not satisfy rescan output requirements.
- Inventory, semantic invariant, depth, RAG, chain, verification, scoring, and
  report files are not rescan outputs.

Phase 4 implementation tasks:

1. Add `RESCAN_MIN_BYTES = 200` and a deterministic
   `RESCAN_REQUIRED_ARTIFACTS` list in
   `plamen_langgraph/plamen_lg/artifacts.py`.
2. Add `expected_rescan_artifacts(scratchpad) -> list[str]` that returns the
   deterministic required rescan outputs for now.
3. Add `rescan_open_outputs(scratchpad) -> list[str]` mirroring
   `breadth_open_outputs()`.
4. Add `forbidden_rescan_artifacts(scratchpad) -> list[str]` for later-phase
   output families.
5. Extend `validate_phase_artifacts("rescan", scratchpad, records)` with:
   - invalid/missing `spawn_manifest.md`
   - missing or stub first-pass breadth prerequisites
   - missing required rescan output
   - stub required rescan output
   - forbidden later-phase output family
6. Add a lightweight duplicate guard that fails when a required rescan output
   is byte-identical to any first-pass breadth output. Semantic duplicate
   detection is deferred to later phases; this guard only catches copy/paste
   or wrong-output mistakes.
7. Record only required rescan outputs as required `rescan` artifacts. Extra
   `analysis_rescan_*.md` files can be recorded as debug extras later, but they
   must not compensate for a missing required output.

Phase 5 artifact contract:

```text
findings_inventory.md
```

For the initial LangGraph inventory implementation, use one direct inventory
phase instead of the legacy `inventory_prepare` plus
`inventory_chunk_a/b/c` plus merge flow.

Discovery source rules:

- `spawn_manifest.md` must exist and remain schema-valid.
- Manifest-derived first-pass breadth outputs must still pass the Phase 3
  breadth gate before inventory starts.
- Required rescan/per-contract outputs must still pass the Phase 4 rescan gate
  before inventory starts.
- Inventory sources are only files under the configured LangGraph scratchpad:
  manifest-derived `analysis_*.md`, `analysis_rescan_*.md`, and
  `analysis_percontract_*.md`.
- Legacy `.scratchpad` discovery outputs do not count.

Fail-closed source-size gate:

- Define `INVENTORY_MAX_SOURCE_FILES` and `INVENTORY_MAX_SOURCE_BYTES` in
  `plamen_langgraph/plamen_lg/artifacts.py`.
- Before invoking Codex, count inventory source files and sum their byte sizes.
- If either threshold is exceeded, fail the `inventory` phase with:
  `inventory source set too large; needs sharded inventory support`.
- Do not invoke Codex and do not write partial inventory output on this path.

Completion rules:

- `findings_inventory.md` must exist under the configured LangGraph scratchpad.
- `findings_inventory.md` must be substantial. Use a single
  `INVENTORY_MIN_BYTES` constant and keep prompt/tests in sync.
- `findings_inventory.md` must contain at least:
  - `Source Summary`
  - `Master Table`
  - `Per-Finding Detail`
  - required field labels for finding ID, title, severity, verdict, location,
    source IDs, root cause, and preferred tag
- `findings_inventory.md` must account for every discovery source file in the
  Source Summary.
- `findings_inventory_chunk_*.md`, `inventory_shard_plan.md`, and
  `inventory_chunk_*.manifest.md` do not satisfy inventory completion in the
  LangGraph path.
- Semantic invariant, depth, RAG, chain, verification, scoring, and report
  files are not inventory outputs.

Phase 5 implementation tasks:

1. Add `INVENTORY_MIN_BYTES`, `INVENTORY_MAX_SOURCE_FILES`, and
   `INVENTORY_MAX_SOURCE_BYTES` constants in
   `plamen_langgraph/plamen_lg/artifacts.py`.
2. Add `inventory_source_files(scratchpad) -> list[str]` that returns the
   authoritative discovery source list described above.
3. Add `inventory_source_size_issues(scratchpad) -> list[str]` that implements
   the fail-closed file-count and byte-size threshold.
4. Add `expected_inventory_artifacts(scratchpad) -> list[str]` returning
   `["findings_inventory.md"]`.
5. Add `forbidden_inventory_artifacts(scratchpad) -> list[str]` for later-phase
   output families and legacy sharded inventory files.
6. Extend `validate_phase_artifacts("inventory", scratchpad, records)` with:
   - invalid/missing `spawn_manifest.md`
   - missing or stub first-pass breadth prerequisites
   - missing or stub rescan prerequisites
   - oversized discovery source set
   - missing or stub `findings_inventory.md`
   - missing required inventory sections/field labels
   - missing Source Summary accounting for a discovery source file
   - forbidden later-phase or legacy sharded inventory output family
7. Record only `findings_inventory.md` as the required `inventory` artifact.

## SQLite Store

Create `plamen_langgraph/plamen_lg/store.py`.

Phase 1 schema:

```sql
create table if not exists runs (
  id text primary key,
  base_run_id text,
  project_root text not null,
  scratchpad text not null,
  phase text not null,
  execution_mode text not null default 'prefix',
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

Phase 2 does not need a schema migration. It should reuse the existing tables:

- one row in `runs`
- one `phase_runs` row for `recon`
- one `phase_runs` row for `instantiate`
- artifact rows with `phase_name = "recon"` for recon outputs
- artifact row with `phase_name = "instantiate"` for `spawn_manifest.md`

Prefix-mode Phase 3 does not need additional tables. It should reuse the
existing tables:

- one row in `runs`
- one `phase_runs` row each for `recon`, `instantiate`, and `breadth`
- artifact rows with `phase_name = "recon"` for recon outputs
- artifact row with `phase_name = "instantiate"` for `spawn_manifest.md`
- artifact rows with `phase_name = "breadth"` for every manifest-derived
  `analysis_*.md` output

Prefix-mode Phase 4 does not need additional tables. It should reuse the
existing tables:

- one row in `runs`
- one `phase_runs` row each for `recon`, `instantiate`, `breadth`, and `rescan`
- artifact rows with `phase_name = "recon"` for recon outputs
- artifact row with `phase_name = "instantiate"` for `spawn_manifest.md`
- artifact rows with `phase_name = "breadth"` for every manifest-derived
  first-pass `analysis_*.md` output
- artifact rows with `phase_name = "rescan"` for every required
  `analysis_rescan_*.md` and `analysis_percontract_*.md` output

Prefix-mode Phase 5 does not need additional tables. It should reuse the
existing tables:

- one row in `runs`
- one `phase_runs` row each for `recon`, `instantiate`, `breadth`, `rescan`,
  and `inventory`
- artifact rows with `phase_name = "recon"` for recon outputs
- artifact row with `phase_name = "instantiate"` for `spawn_manifest.md`
- artifact rows with `phase_name = "breadth"` for every manifest-derived
  first-pass `analysis_*.md` output
- artifact rows with `phase_name = "rescan"` for every required
  `analysis_rescan_*.md` and `analysis_percontract_*.md` output
- artifact row with `phase_name = "inventory"` for `findings_inventory.md`

Single-node mode needs a small backward-compatible schema migration:

```sql
alter table runs add column base_run_id text;
alter table runs add column execution_mode text not null default 'prefix';
```

For fresh DBs, include those columns in `create table if not exists runs`.
For existing DBs, add an idempotent migration helper that checks
`pragma table_info(runs)` before issuing each `alter table`.

Single-node run records:

- create a new row in `runs`
- set `runs.phase` to the requested target phase
- set `runs.execution_mode = "single_node"`
- set `runs.base_run_id` to the referenced successful predecessor run
- create exactly one `phase_runs` row for the target phase
- record only the target phase artifacts under the new run id

Do not mutate the base run's `runs.status`, `runs.phase`, or existing
`phase_runs` rows when running a single node. The base run is evidence for
prerequisites, not the mutable owner of the new node attempt.

For Phase 2, Phase 3, and Phase 4, the `runs.phase` column should store the
requested target phase:

```text
recon        # `python -m plamen_langgraph.cli recon ...`
instantiate  # `python -m plamen_langgraph.cli instantiate ...`
breadth      # `python -m plamen_langgraph.cli breadth ...`
rescan       # `python -m plamen_langgraph.cli rescan ...`
inventory    # `python -m plamen_langgraph.cli inventory ...`
```

In single-node mode, `runs.phase` still stores the requested target phase; use
`runs.execution_mode` to distinguish prefix runs from single-node runs.

Do not add checkpoint tables, worker tables, or worktree tables in Phase 2,
the initial Phase 3, or the initial Phase 4. If sequential per-output breadth
subprocesses are used,
aggregate them into one `breadth` `phase_runs` row for now and store their
detailed stdout/stderr in deterministic `_lg_breadth_*` debug files or a
documented `_lg_breadth_agents/` subdirectory.
Do the same for Phase 4: aggregate rescan work into one `rescan`
`phase_runs` row and deterministic `_lg_rescan_*` debug files. Do not add a
rescan worker table until parallel isolation exists.
For Phase 5, aggregate inventory work into one `inventory` `phase_runs` row
and deterministic `_lg_inventory_*` debug files. Do not add inventory shard or
worker tables until single-phase inventory size limits prove insufficient.

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

For Phase 2, keep the same config fields. Do not add broad legacy config
compatibility yet.

For Phase 3, keep the same config fields. Add a local constant for the breadth
minimum byte threshold if needed; do not add broad legacy config compatibility
yet. `--single-node` and `--base-run-id` are explicit node execution controls,
not broad automatic resume. Do not add "latest run" discovery, partial graph
auto-resume, or checkpoint replay flags yet.

For Phase 4, keep the same config fields. `rescan` is mandatory in every
supported mode. Add local constants for the rescan minimum byte threshold and
required output filenames. Do not add broad legacy config compatibility,
automatic skip semantics, or checkpoint replay flags yet.

For Phase 5, keep the same config fields. Add local constants for the inventory
minimum byte threshold, maximum discovery source file count, and maximum
discovery source bytes. Do not add dynamic inventory sharding, broad legacy
config compatibility, or checkpoint replay flags yet.

## Isolation Rules

Phase 1 uses the target repository directly, but documents the future isolation model.

Rules for Phase 1 and Phase 2:

- One run at a time per project.
- No parallel Codex subprocesses.
- Do not pass dangerous Codex sandbox bypass flags.
- Write only to the configured LangGraph scratchpad unless Codex itself creates normal build cache files as part of bounded inspection.
- Do not write or mutate legacy `.scratchpad/_v2_checkpoint.json`.

Rules for Phase 3:

- Keep one LangGraph run lock per project.
- Do not run Python-level parallel Codex subprocesses against the same writable
  project until worktree/container isolation is implemented.
- Write breadth outputs only under the configured LangGraph scratchpad.
- Do not write or mutate legacy `.scratchpad/_v2_checkpoint.json`.
- Do not let breadth workers edit target source files or dependency manifests.
- Single-node mode must hold the same run lock as prefix mode.
- Single-node mode must not mutate the base run it depends on.

Rules for Phase 4:

- Keep one LangGraph run lock per project.
- Do not run Python-level parallel Codex subprocesses against the same writable
  project until worktree/container isolation is implemented.
- Write rescan outputs only under the configured LangGraph scratchpad.
- Do not write or mutate legacy `.scratchpad/_v2_checkpoint.json`.
- Do not let rescan workers edit target source files or dependency manifests.
- Single-node mode must hold the same run lock as prefix mode.
- Single-node mode must not mutate the base run it depends on.

Rules for Phase 5:

- Keep one LangGraph run lock per project.
- Do not run Python-level parallel Codex subprocesses against the same writable
  project until worktree/container isolation is implemented.
- Fail closed before invoking Codex if the discovery source set exceeds the
  configured single-inventory thresholds.
- Write inventory outputs only under the configured LangGraph scratchpad.
- Do not write or mutate legacy `.scratchpad/_v2_checkpoint.json`.
- Do not let inventory workers edit target source files or dependency manifests.
- Single-node mode must hold the same run lock as prefix mode.
- Single-node mode must not mutate the base run it depends on.

Future isolation:

- one git worktree per worker
- or one container per worker
- SQLite records the worktree/container ID
- artifacts are copied back to the canonical scratchpad

## Logging And Debug Files

For a run with ID `<run_id>`, write:

```text
.lg_scratchpad/
  plamen_lg.sqlite
  _lg_recon_prompt.md
  _lg_recon_stdout.log
  _lg_recon_stderr.log
  _lg_recon_events.jsonl
  _lg_recon_last_message.md
  _lg_instantiate_prompt.md
  _lg_instantiate_stdout.log
  _lg_instantiate_stderr.log
  _lg_instantiate_events.jsonl
  _lg_instantiate_last_message.md
  _lg_breadth_prompt.md
  _lg_breadth_stdout.log
  _lg_breadth_stderr.log
  _lg_breadth_events.jsonl
  _lg_breadth_last_message.md
  _lg_rescan_prompt.md
  _lg_rescan_stdout.log
  _lg_rescan_stderr.log
  _lg_rescan_events.jsonl
  _lg_rescan_last_message.md
  _lg_inventory_prompt.md
  _lg_inventory_stdout.log
  _lg_inventory_stderr.log
  _lg_inventory_events.jsonl
  _lg_inventory_last_message.md
  spawn_manifest.md
  analysis_<focus_area>.md
  analysis_rescan_gap_sweep.md
  analysis_rescan_cross_check.md
  analysis_percontract_scope_review.md
  findings_inventory.md
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

Phase 2 test targets:

- `get_phase("instantiate")` returns the canonical SC second phase metadata.
- `build_instantiate_prompt()` includes the Phase 2 methodology body and excludes `Task(subagent_type=...)`.
- `python -m plamen_langgraph.cli instantiate ...` parses the same options as `recon`.
- Mocked `run_graph(target_phase="instantiate")` calls the runner twice in order: `recon`, then `instantiate`.
- If mocked recon fails, instantiate is not called and no `phase_runs` row for `instantiate` is created.
- Mocked successful instantiate writes `spawn_manifest.md`, records two phase rows, and marks the run `succeeded`.
- Missing `spawn_manifest.md` marks `instantiate` and the parent run `failed`.
- Invalid `spawn_manifest.md` schema marks `instantiate` and the parent run `failed`.
- `spawn_manifest.md` artifact row is recorded with `phase_name = "instantiate"`.
- Existing `run_recon_graph()` tests continue to pass unchanged.
- Legacy files such as `_v2_checkpoint.json` are still not created or modified.

Phase 3 test targets:

- `get_phase("breadth")` returns the canonical SC third phase metadata.
- `build_breadth_prompt()` includes the Phase 3 methodology body, lists
  manifest-derived expected outputs, and forbids inventory/depth/report work.
- `python -m plamen_langgraph.cli breadth ...` parses the same options as
  `recon` and `instantiate`.
- `python -m plamen_langgraph.cli breadth ... --single-node --base-run-id ...`
  parses single-node options and preserves the target phase.
- Mocked `run_graph(target_phase="breadth")` calls the runner in order:
  `recon`, `instantiate`, then `breadth`.
- Mocked `run_phase_node("instantiate", base_run_id=...)` calls the runner once
  for `instantiate` when the base run has successful `recon`.
- Mocked `run_phase_node("breadth", base_run_id=...)` calls the runner once for
  `breadth` when the base run has successful `recon` and `instantiate`.
- Single-node `instantiate` fails before invoking Codex when the base run lacks
  a successful `recon` phase row or recon artifacts.
- Single-node `breadth` fails before invoking Codex when the base run lacks
  successful `recon`/`instantiate` phase rows or has an invalid
  `spawn_manifest.md`.
- Single-node runs create a new `runs` row with
  `execution_mode = "single_node"` and `base_run_id` set.
- Single-node runs do not mutate the base run status or existing base
  `phase_runs` rows.
- If mocked `recon` fails, neither `instantiate` nor `breadth` is called.
- If mocked `instantiate` fails, `breadth` is not called and no `phase_runs` row
  for `breadth` is created.
- Mocked successful breadth writes every manifest-derived `analysis_*.md`
  output, records three phase rows, and marks the run `succeeded`.
- Missing manifest-derived breadth output marks `breadth` and the parent run
  `failed`.
- Stub manifest-derived breadth output marks `breadth` and the parent run
  `failed`.
- Extra non-manifest `analysis_*.md` files do not make the breadth phase pass.
- Forbidden later-phase files such as `analysis_rescan_*.md`, inventory, depth,
  verify, or report outputs do not count as breadth completion.
- Breadth artifact rows are recorded with `phase_name = "breadth"`.
- Existing `run_recon_graph()` and `run_instantiate_graph()` tests continue to
  pass unchanged.
- Legacy files such as `_v2_checkpoint.json` are still not created or modified.

Phase 4 test targets:

- `get_phase("rescan")` returns the canonical SC rescan phase metadata and is
  available in Light, Core, and Thorough modes.
- `build_rescan_prompt()` includes the Phase 4 methodology body, lists
  manifest-derived first-pass breadth outputs, lists the deterministic rescan
  required outputs, and forbids inventory/depth/report work.
- `python -m plamen_langgraph.cli rescan ... --mode core` parses the same
  options as `breadth`.
- `python -m plamen_langgraph.cli rescan ... --mode light` parses and runs the
  same target phase.
- `python -m plamen_langgraph.cli rescan ... --mode core --single-node
  --base-run-id ...` parses single-node options and preserves the target phase.
- Mocked `run_graph(target_phase="rescan")` calls the runner in order:
  `recon`, `instantiate`, `breadth`, then `rescan`.
- Mocked `run_phase_node("rescan", base_run_id=...)` calls the runner once for
  `rescan` when the base run has successful `recon`, `instantiate`, and
  `breadth`.
- Single-node `rescan` fails before invoking Codex when the base run lacks
  successful predecessor phase rows.
- Single-node `rescan` fails before invoking Codex when `spawn_manifest.md` is
  invalid or manifest-derived first-pass breadth outputs are missing/stub.
- Prefix-mode `rescan` is not called if `breadth` fails.
- Mocked successful rescan writes
  `analysis_rescan_gap_sweep.md`,
  `analysis_rescan_cross_check.md`, and
  `analysis_percontract_scope_review.md`, records four phase rows, and marks
  the run `succeeded`.
- Missing required rescan output marks `rescan` and the parent run `failed`.
- Stub required rescan output marks `rescan` and the parent run `failed`.
- Byte-identical copies of first-pass breadth output fail the lightweight
  duplicate guard.
- Extra `analysis_rescan_*.md` files do not compensate for a missing required
  rescan output.
- Forbidden later-phase files such as inventory, depth, verify, or report
  outputs do not count as rescan completion.
- Rescan artifact rows are recorded with `phase_name = "rescan"`.
- Existing `run_recon_graph()`, `run_instantiate_graph()`, and
  `run_breadth_graph()` tests continue to pass unchanged.
- Legacy files such as `_v2_checkpoint.json` are still not created or modified.

Phase 5 test targets:

- `get_phase("inventory")` returns the LangGraph single-inventory phase
  metadata.
- `build_inventory_prompt()` includes the inventory methodology body, lists the
  exact discovery source files, and forbids sharded inventory/depth/report work.
- `python -m plamen_langgraph.cli inventory ...` parses the same options as
  `rescan`.
- `python -m plamen_langgraph.cli inventory ... --single-node --base-run-id ...`
  parses single-node options and preserves the target phase.
- Mocked `run_graph(target_phase="inventory")` calls the runner in order:
  `recon`, `instantiate`, `breadth`, `rescan`, then `inventory`.
- Mocked `run_phase_node("inventory", base_run_id=...)` calls the runner once
  for `inventory` when the base run has successful `recon`, `instantiate`,
  `breadth`, and `rescan`.
- Single-node `inventory` fails before invoking Codex when the base run lacks
  successful predecessor phase rows.
- Single-node `inventory` fails before invoking Codex when breadth or rescan
  prerequisite artifacts are missing/stub.
- Prefix-mode `inventory` is not called if `rescan` fails.
- Oversized discovery source file count fails `inventory` before invoking Codex
  with `inventory source set too large; needs sharded inventory support`.
- Oversized discovery source byte count fails `inventory` before invoking Codex
  with the same fail-closed error.
- Mocked successful inventory writes `findings_inventory.md`, records five
  phase rows, and marks the run `succeeded`.
- Missing `findings_inventory.md` marks `inventory` and the parent run
  `failed`.
- Stub `findings_inventory.md` marks `inventory` and the parent run `failed`.
- Missing required inventory sections or field labels marks `inventory` and
  the parent run `failed`.
- Missing Source Summary accounting for any discovery source file marks
  `inventory` and the parent run `failed`.
- Legacy sharded inventory artifacts such as `inventory_shard_plan.md`,
  `inventory_chunk_a.manifest.md`, or `findings_inventory_chunk_a.md` do not
  satisfy inventory completion.
- Forbidden later-phase files such as depth, verify, or report outputs do not
  count as inventory completion.
- Inventory artifact rows are recorded with `phase_name = "inventory"`.
- Existing Phase 1-4 tests continue to pass unchanged.
- Legacy files such as `_v2_checkpoint.json` are still not created or modified.

Do not require a real Codex CLI call in unit tests. Real Codex invocation can be covered by a manual smoke test.

## Manual Smoke Test

Use a small local repository as target:

```bash
python -m plamen_langgraph.cli recon /path/to/small/project
```

Phase 2 smoke command:

```bash
python -m plamen_langgraph.cli instantiate /path/to/small/project
```

Phase 3 smoke command:

```bash
python -m plamen_langgraph.cli breadth /path/to/small/project
```

Phase 4 smoke command:

```bash
python -m plamen_langgraph.cli rescan /path/to/small/project --mode core
```

Phase 5 smoke command:

```bash
python -m plamen_langgraph.cli inventory /path/to/small/project --mode core
```

Single-node smoke command after a successful prefix run:

```bash
python -m plamen_langgraph.cli instantiate /path/to/small/project
# copy the printed run_id
python -m plamen_langgraph.cli breadth /path/to/small/project \
  --single-node \
  --base-run-id <printed-run-id>
python -m plamen_langgraph.cli rescan /path/to/small/project \
  --mode core \
  --single-node \
  --base-run-id <breadth-run-id>
python -m plamen_langgraph.cli inventory /path/to/small/project \
  --mode core \
  --single-node \
  --base-run-id <rescan-run-id>
```

Then verify:

```bash
ls -la /path/to/small/project/.lg_scratchpad
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite ".tables"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase, status from runs;"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select id, phase, execution_mode, base_run_id, status from runs order by created_at;"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase_name, status, returncode from phase_runs order by started_at;"
sqlite3 /path/to/small/project/.lg_scratchpad/plamen_lg.sqlite "select phase_name, path, exists from artifacts order by created_at;"
```

Expected result:

- `runs.status = succeeded` if all required recon artifacts exist.
- `phase_runs.status = succeeded`.
- required recon artifacts exist under `.lg_scratchpad`.
- Phase 2, Phase 3, and Phase 4: `spawn_manifest.md` exists under
  `.lg_scratchpad`.
- Phase 2 only: `phase_runs` contains exactly one `recon` row and one
  `instantiate` row.
- Phase 3 only: manifest-derived `analysis_*.md` files exist under
  `.lg_scratchpad`.
- Phase 3 only: `phase_runs` contains exactly one `recon` row, one
  `instantiate` row, and one `breadth` row.
- Phase 3 only: `artifacts` contains one `breadth` row per manifest-derived
  output.
- Phase 4 only: required rescan outputs exist under `.lg_scratchpad`.
- Phase 4 only: `phase_runs` contains exactly one `recon` row, one
  `instantiate` row, one `breadth` row, and one `rescan` row.
- Phase 4 only: `artifacts` contains one `rescan` row per required rescan
  output.
- Phase 5 only: `findings_inventory.md` exists under `.lg_scratchpad`.
- Phase 5 only: `phase_runs` contains exactly one `recon` row, one
  `instantiate` row, one `breadth` row, one `rescan` row, and one `inventory`
  row.
- Phase 5 only: `artifacts` contains one `inventory` row for
  `findings_inventory.md`.
- Single-node only: the new `runs` row has `execution_mode = single_node`,
  `base_run_id` set to the referenced prefix run, and only the target
  `phase_runs` row under the new run id.
- Single-node only: the referenced base run remains `succeeded`.
- no legacy full-pipeline checkpoint is written by the new implementation.

## Acceptance Criteria

Phase 1 is complete when:

1. All new implementation files live under `plamen_langgraph/`.
2. Existing `plamen.py` and `scripts/plamen_driver.py` behavior is unchanged.
3. `python -m plamen_langgraph.cli recon /path/to/project` runs a LangGraph graph.
4. The graph executes exactly one phase: `recon`.
5. Codex CLI is invoked through a dedicated runner wrapper.
6. stdout, stderr, JSONL events, prompt snapshot, and final message are saved under `.lg_scratchpad`.
7. SQLite records run, phase, and artifact status.
8. Recon artifacts are checked and recorded.
9. Unit tests pass with a mocked Codex runner.
10. A manual smoke test can run against a small repo.

## Phase 2 Implementation Plan

Phase 2 should implement the actual second smart-contract phase from
`SC_PHASES`:

```text
recon -> instantiate
```

Rationale:

- `instantiate` is the canonical second phase in `scripts/plamen_types.py`.
- It consumes recon artifacts and produces the breadth spawn contract.
- It validates multi-node graph routing without adding parallel workers.
- It exercises a stricter phase-specific validator through `spawn_manifest.md`.

Do not implement `inventory_prepare` in Phase 2. In the legacy SC graph it is a
later mechanical step after breadth/rescan, not the second phase.

Phase 2 development checklist:

1. Add generic phase helpers in `plamen_langgraph/plamen_lg/phases.py`:
   - `get_phase(name, pipeline="sc")`
   - `expected_phase_artifacts(name)`
   - `build_phase_prompt(name, config)`
   - keep `get_recon_phase()` and `build_recon_prompt()` as wrappers if tests use them
2. Add `build_instantiate_prompt(config)` using `prompts/shared/v2/phase2-instantiate.md`.
3. Generalize graph output paths from recon-only names to `_lg_<phase>_*`.
4. Add an `instantiate` node with the behavior described above.
5. Add `run_graph(config, target_phase)` and keep `run_recon_graph()` as a wrapper.
6. Add `run_instantiate_graph()` or route the CLI command directly to `run_graph(..., "instantiate")`.
7. Add phase-specific artifact validation for `spawn_manifest.md`.
8. Update the README to document the new command and files.
9. Add unit tests before manual smoke testing.
10. Run the existing Phase 1 tests to prove recon behavior did not regress.

Phase 2 acceptance criteria:

1. `python -m plamen_langgraph.cli recon /path/to/project` still runs only `recon`.
2. `python -m plamen_langgraph.cli instantiate /path/to/project` runs `recon -> instantiate`.
3. If `recon` fails, `instantiate` is not executed.
4. `spawn_manifest.md` is required, substantial, schema-valid, and recorded in SQLite.
5. The run has two successful `phase_runs` rows when both phases pass.
6. No breadth agents are spawned.
7. No `analysis_*.md`, inventory, depth, verification, scoring, or report artifacts are required by Phase 2.
8. No legacy checkpoint is written.
9. Unit tests pass with mocked runners.
10. A manual smoke test can produce a valid `spawn_manifest.md`.

## Phase 3 Implementation Plan

Phase 3 should implement the actual third smart-contract phase from
`SC_PHASES`:

```text
recon -> instantiate -> breadth
```

Rationale:

- `breadth` is the canonical third phase in `scripts/plamen_types.py`.
- It consumes the `spawn_manifest.md` contract produced by `instantiate`.
- It produces the first-pass `analysis_*.md` discovery artifacts consumed by
  later inventory/depth/report phases.
- It is the first LangGraph phase that needs manifest-exact dynamic artifact
  expectations instead of only static artifact names.

Do not implement `rescan`, `inventory_prepare`, inventory, depth, verification,
scoring, or report work in Phase 3. Do not replace the legacy parallel worker
scheduler yet. The first Phase 3 target is a correct, testable breadth phase
boundary; parallel fan-out can be added after worktree/container isolation is
designed.

Phase 3 development checklist:

1. Add `breadth` to `SUPPORTED_TARGET_PHASES`.
2. Add `build_breadth_prompt(config, open_outputs=None)` using
   `prompts/shared/v2/phase3-breadth.md`.
3. Add `run_breadth_graph()` as a wrapper around
   `run_graph(config, target_phase="breadth")`.
4. Extend `build_graph()` so `target_phase = "breadth"` compiles
   `recon -> instantiate -> breadth`.
5. Add `run_phase_node(config, phase_name, base_run_id, runner=None)` for
   explicit single-node execution.
6. Add `--single-node` and `--base-run-id` CLI options. In single-node mode,
   route to `run_phase_node()` instead of the prefix graph.
7. Add idempotent store migration support for `runs.base_run_id` and
   `runs.execution_mode`.
8. Add a breadth precondition check: skip the breadth node unless
   `instantiate` succeeded and is in `completed_phases`.
9. Add single-node prerequisite validation:
   - `instantiate` requires successful `recon` in the base run
   - `breadth` requires successful `recon` and `instantiate` in the base run
   - predecessor artifact gates must pass before invoking Codex
10. Add a local breadth manifest parser wrapper around
   `parse_breadth_manifest_outputs()` or an equivalent compatibility parser in
   `plamen_langgraph/plamen_lg/artifacts.py`.
11. Add `expected_breadth_artifacts(scratchpad)` and use it inside the breadth
   node before calling `check_artifacts()`.
12. Add `validate_phase_artifacts("breadth", scratchpad, records)` with
   manifest-exact missing/stub/forbidden-output checks.
13. Teach the graph node to record one artifact row per manifest-derived
   breadth output, not just one `analysis_*.md` glob row.
14. Add `breadth` to the CLI with the same options as `recon` and
    `instantiate`.
15. Update `plamen_langgraph/README.md` to document the breadth command,
    single-node command shape, and `_lg_breadth_*` debug files.
16. Add unit tests before manual smoke testing.
17. Run the existing Phase 1 and Phase 2 tests to prove behavior did not
    regress.

Phase 3 acceptance criteria:

1. `python -m plamen_langgraph.cli recon /path/to/project` still runs only
   `recon`.
2. `python -m plamen_langgraph.cli instantiate /path/to/project` still runs
   `recon -> instantiate`.
3. `python -m plamen_langgraph.cli breadth /path/to/project` runs
   `recon -> instantiate -> breadth`.
4. `python -m plamen_langgraph.cli breadth /path/to/project --single-node
   --base-run-id <id>` runs only `breadth` after validating predecessor success.
5. Single-node `instantiate` runs only `instantiate` after validating `recon`
   success.
6. Single-node runs create new run rows with `execution_mode = "single_node"`
   and do not mutate their base runs.
7. If `recon` fails, neither `instantiate` nor `breadth` is executed in prefix
   mode.
8. If `instantiate` fails, `breadth` is not executed in prefix mode.
9. `spawn_manifest.md` is revalidated before breadth work starts.
10. The breadth gate requires every manifest-derived first-pass `analysis_*.md`
   output to exist and be substantial.
11. Extra non-manifest `analysis_*.md` files do not satisfy the gate.
12. Later-phase output families do not satisfy the gate.
13. The prefix run has three successful `phase_runs` rows when all three phases
    pass.
14. Breadth artifact rows are recorded with `phase_name = "breadth"` and exact
    manifest-derived paths.
15. No inventory, depth, verification, scoring, or report artifacts are
    required by Phase 3.
16. No legacy checkpoint is written.
17. Unit tests pass with mocked runners.
18. A manual smoke test can produce a valid `spawn_manifest.md` and the
    manifest-derived breadth analysis files.

## Phase 4 Implementation Plan

Phase 4 should implement the mandatory rescan phase:

```text
recon -> instantiate -> breadth -> rescan
```

Rationale:

- `rescan` is the canonical post-breadth additional discovery phase in
  `scripts/plamen_types.py`.
- It consumes the first-pass breadth outputs and intentionally searches for
  findings the first pass missed.
- It produces additional discovery artifacts consumed later by inventory:
  `analysis_rescan_*.md` and `analysis_percontract_*.md`.
- It is required in Light, Core, and Thorough so every LangGraph run has the
  same discovery producer sequence before inventory.

Do not implement `inventory_prepare`, inventory, semantic invariants, depth,
RAG, chain, verification, scoring, or report work in Phase 4. Do not replace
the legacy parallel worker scheduler yet. The first Phase 4 target is a
correct, testable rescan phase boundary with deterministic required outputs;
dynamic rescan manifests and parallel fan-out can be added after
worktree/container isolation is designed.

Phase 4 development checklist:

1. Add `rescan` to `SUPPORTED_TARGET_PHASES`.
2. Add `get_phase("rescan")` support using LangGraph phase metadata that is
   available in every supported mode.
3. Add `build_rescan_prompt(config, open_outputs=None)` using
   `prompts/shared/v2/phase4-rescan.md`.
4. Add `run_rescan_graph()` as a wrapper around
   `run_graph(config, target_phase="rescan")`.
5. Extend `build_graph()` so `target_phase = "rescan"` compiles
   `recon -> instantiate -> breadth -> rescan`.
6. Extend `_predecessors_for("rescan")` to require `recon`, `instantiate`, and
   `breadth`.
7. Ensure there is no mode gate that skips or fails `rescan` for Light/Core.
8. Add `rescan` to the CLI with the same options as `breadth`.
9. In CLI single-node mode, require `--base-run-id` for `rescan`.
10. Add `RESCAN_MIN_BYTES = 200` and `RESCAN_REQUIRED_ARTIFACTS` in
    `plamen_langgraph/plamen_lg/artifacts.py`.
11. Add `expected_rescan_artifacts()`, `rescan_open_outputs()`, and
    `forbidden_rescan_artifacts()`.
12. Extend `validate_phase_artifacts("rescan", scratchpad, records)` with the
    rescan contract described above.
13. Reuse the breadth parser to derive first-pass outputs; do not accept
    arbitrary `analysis_*.md` files as breadth prerequisites.
14. Add a lightweight byte-identical duplicate guard comparing required rescan
    outputs against manifest-derived first-pass breadth outputs.
15. Teach the graph node to record one artifact row per required rescan output.
16. Update `plamen_langgraph/README.md` to document the rescan command,
    all-mode behavior, single-node command shape, and `_lg_rescan_*` debug
    files.
17. Add unit tests before manual smoke testing.
18. Run existing Phase 1, Phase 2, and Phase 3 tests to prove behavior did not
    regress.

Phase 4 acceptance criteria:

1. `python -m plamen_langgraph.cli recon /path/to/project` still runs only
   `recon`.
2. `python -m plamen_langgraph.cli instantiate /path/to/project` still runs
   `recon -> instantiate`.
3. `python -m plamen_langgraph.cli breadth /path/to/project` still runs
   `recon -> instantiate -> breadth`.
4. `python -m plamen_langgraph.cli rescan /path/to/project --mode core`
   runs `recon -> instantiate -> breadth -> rescan`.
5. `python -m plamen_langgraph.cli rescan /path/to/project --mode light`
   also runs `recon -> instantiate -> breadth -> rescan`.
6. `python -m plamen_langgraph.cli rescan /path/to/project --mode core
   --single-node --base-run-id <id>` runs only `rescan` after validating
   predecessor success and artifacts.
7. If `recon`, `instantiate`, or `breadth` fails, `rescan` is not executed in
   prefix mode.
8. `spawn_manifest.md` and manifest-derived breadth outputs are revalidated
   before rescan work starts.
9. The rescan gate requires
   `analysis_rescan_gap_sweep.md`,
   `analysis_rescan_cross_check.md`, and
   `analysis_percontract_scope_review.md` to exist and be substantial.
10. Extra `analysis_rescan_*.md` or `analysis_percontract_*.md` files do not
    satisfy missing required outputs.
11. Later-phase output families do not satisfy the gate.
12. Byte-identical copies of first-pass breadth outputs fail the duplicate
    guard.
13. The prefix run has four successful `phase_runs` rows when all four phases
    pass.
14. Rescan artifact rows are recorded with `phase_name = "rescan"` and exact
    required paths.
15. No inventory, depth, verification, scoring, or report artifacts are
    required by Phase 4.
16. No legacy checkpoint is written.
17. Unit tests pass with mocked runners.
18. A manual smoke test can produce valid first-pass breadth outputs and the
    required rescan/per-contract outputs.

## Phase 5 Implementation Plan

Phase 5 should implement a single LangGraph inventory phase:

```text
recon -> instantiate -> breadth -> rescan -> inventory
```

Rationale:

- LangGraph should keep the initial post-rescan path simple and avoid porting
  the legacy `inventory_prepare` plus `inventory_chunk_a/b/c` plus merge flow.
- `inventory` is the canonical boundary between discovery producers and
  downstream analysis. Downstream phases should consume `findings_inventory.md`
  instead of reading raw `analysis_*.md` families directly.
- Single-phase inventory is simpler to route, store, retry, and validate.
- Large audits should fail closed before Codex runs rather than producing a
  silently incomplete inventory. Sharded inventory can be reintroduced later
  with explicit LangGraph support when thresholds are exceeded in practice.

Do not implement semantic invariants, depth, RAG, chain, verification, scoring,
or report work in Phase 5. Do not implement dynamic inventory shards yet. The
first Phase 5 target is a correct, testable single inventory phase boundary
with fail-closed source-size gating.

Phase 5 development checklist:

1. Add `inventory` to `SUPPORTED_TARGET_PHASES`.
2. Add `get_phase("inventory")` support with expected artifact
   `findings_inventory.md`.
3. Add `build_inventory_prompt(config, source_files=None)` using
   `prompts/shared/v2/phase4a-inventory-base.md`.
4. Add `run_inventory_graph()` as a wrapper around
   `run_graph(config, target_phase="inventory")`.
5. Extend `build_graph()` so `target_phase = "inventory"` compiles
   `recon -> instantiate -> breadth -> rescan -> inventory`.
6. Extend `_predecessors_for("inventory")` to require `recon`, `instantiate`,
   `breadth`, and `rescan`.
7. Add `inventory` to the CLI with the same options as `rescan`.
8. In CLI single-node mode, require `--base-run-id` for `inventory`.
9. Add `INVENTORY_MIN_BYTES`, `INVENTORY_MAX_SOURCE_FILES`, and
   `INVENTORY_MAX_SOURCE_BYTES` in
   `plamen_langgraph/plamen_lg/artifacts.py`.
10. Add `inventory_source_files()`, `inventory_source_size_issues()`,
    `expected_inventory_artifacts()`, and `forbidden_inventory_artifacts()`.
11. Extend `validate_phase_artifacts("inventory", scratchpad, records)` with
    the inventory contract described above.
12. Teach the graph node to fail before invoking Codex when
    `inventory_source_size_issues()` returns any issue.
13. Teach the graph node to record one artifact row for `findings_inventory.md`.
14. Update `plamen_langgraph/README.md` to document the inventory command,
    fail-closed source-size behavior, single-node command shape, and
    `_lg_inventory_*` debug files.
15. Add unit tests before manual smoke testing.
16. Run existing Phase 1-4 tests to prove behavior did not regress.

Phase 5 acceptance criteria:

1. `python -m plamen_langgraph.cli recon /path/to/project` still runs only
   `recon`.
2. `python -m plamen_langgraph.cli instantiate /path/to/project` still runs
   `recon -> instantiate`.
3. `python -m plamen_langgraph.cli breadth /path/to/project` still runs
   `recon -> instantiate -> breadth`.
4. `python -m plamen_langgraph.cli rescan /path/to/project --mode core` still
   runs `recon -> instantiate -> breadth -> rescan`.
5. `python -m plamen_langgraph.cli inventory /path/to/project --mode core`
   runs `recon -> instantiate -> breadth -> rescan -> inventory`.
6. `python -m plamen_langgraph.cli inventory /path/to/project --mode core
   --single-node --base-run-id <id>` runs only `inventory` after validating
   predecessor success and artifacts.
7. If `recon`, `instantiate`, `breadth`, or `rescan` fails, `inventory` is not
   executed in prefix mode.
8. Breadth and rescan artifact gates are revalidated before inventory work
   starts.
9. Oversized discovery source file count or total byte size fails before
   invoking Codex with `inventory source set too large; needs sharded inventory
   support`.
10. The inventory gate requires `findings_inventory.md` to exist, be
    substantial, contain required sections and field labels, and account for
    every discovery source file.
11. Legacy sharded inventory files do not satisfy the gate.
12. Later-phase output families do not satisfy the gate.
13. The prefix run has five successful `phase_runs` rows when all five phases
    pass.
14. Inventory artifact rows are recorded with `phase_name = "inventory"` and
    exact required path `findings_inventory.md`.
15. No semantic invariant, depth, verification, scoring, or report artifacts
    are required by Phase 5.
16. No legacy checkpoint is written.
17. Unit tests pass with mocked runners.
18. A manual smoke test can produce valid discovery outputs and
    `findings_inventory.md`.

Deferred after Phase 5:

- worktree isolation
- parallel worker policy
- richer automatic resume semantics
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
- automatic resume behavior is equivalent or better
- artifact gates are equivalent
- failure handling is tested
- there is a migration path for existing `.scratchpad` runs
