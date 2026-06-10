# Plamen 代码架构与完整执行流程

下面是基于源码梳理的 Plamen 架构和完整执行流程。

## 整体架构

Plamen 本质上是一个“Python 确定性 driver + Codex 子进程 + scratchpad artifact gate”的审计流水线。

```text
plamen CLI / Codex command
        ↓
plamen.py 生成 .scratchpad/config.json
        ↓
scripts/plamen_driver.py
        ↓
读取 SC_PHASES / L1_PHASES
        ↓
每个 Phase 构造 prompt
        ↓
codex exec 独立子进程执行
        ↓
写入 .scratchpad/*.md artifacts
        ↓
validators 校验产物、重试、断点续跑
        ↓
最终 AUDIT_REPORT.md
```

## 核心模块

- `plamen.py`：外层 CLI/wizard。负责解析 `plamen core/thorough/l1/resume/install`，生成 `.scratchpad/config.json`，然后启动 driver。
- `scripts/plamen_driver.py`：真正的流水线调度器。它是 phase sequencing 的唯一 owner。
- `scripts/plamen_types.py`：定义 `Phase`、`Checkpoint`、模型映射、SC/L1 phase graph。
- `scripts/plamen_prompt.py`：根据 phase 构造独立 prompt，优先使用 `prompts/shared/v2/*.md`，再 fallback 到旧 command prompt 的 section extraction。
- `scripts/plamen_validators.py`：artifact gate、phase containment、report/verify/inventory 等质量校验。
- `scripts/plamen_parsers.py`：解析 verification queue、report index、manifest、shards。
- `scripts/plamen_mechanical.py`：确定性机械步骤，比如 inventory shard plan、verification queue、report index/tier fallback。
- `scripts/recon_prepass.py`：LLM 前的机械 recon 预处理，生成 inventory/function/state/build 等基础 artifact。
- `scripts/codex_adapter.py`：安装/生成 Codex 配置、agent TOML、skills、commands。

## 启动流程

1. `plamen install` 走 `plamen.py`，调用 `_install_codex_adapter()`。
2. `_install_codex_adapter()` 会运行 `scripts/codex_adapter.py`，创建 `~/.codex/plamen -> PLAMEN_HOME` 链接，并复制 `AGENTS.md`、`config.toml`、`agents/`、`skills/`、`commands/` 到 `~/.codex`。
3. 真正开始审计时，`launch_v2()` 写入 `.scratchpad/config.json`，再 `subprocess.run([python, plamen_driver.py, config_path])`。

## Driver 主流程

1. driver 读取 config，强制 `cli_backend = codex`，初始化 `.scratchpad/_plamen.log`。
2. 运行 `run_recon_prepass(config)`，先机械生成基础 recon artifact。
3. 读取 `_v2_checkpoint.json`，支持 resume；如果 report 已存在但 `report_assemble` 未完成，会隔离旧报告。
4. 根据 `pipeline` 选择 `SC_PHASES` 或 `L1_PHASES`，并用 `validate_phase_graph()` 做启动前静态校验。
5. 遍历 phase：已完成的跳过，不在当前 mode 的跳过，剩余 phase 执行。
6. 每个 phase 先可能执行机械 shortcut，比如 `inventory_prepare` 直接写 shard plan，inventory 可机械合并 chunk，verification queue 可机械生成。
7. 需要 LLM 的 phase 进入 `run_phase()`。

## 单个 Phase 怎么跑

`run_phase()` 做这些事：

1. `build_phase_prompt()` 构造当前 phase 的专属 prompt。
2. 根据 LOC、hypothesis 数、mode、backend 动态扩 timeout。
3. 将 prompt 写到 `.scratchpad/_prompt_<phase>.attemptN.md`，这个文件就是子进程 stdin。
4. 预创建 expected artifact，构造 `codex exec` 命令。
5. `Popen()` 在目标项目根目录下启动 Codex 子进程，stdout/stderr 写入 `.scratchpad/_stdio_<phase>.attemptN.log`。
6. 子进程完成后，driver 运行 gate 和 phase-specific validators。
7. 通过则 checkpoint 标记完成；失败则写 retry hint、隔离 stale/foreign artifact、重试；关键 phase 多次失败会 halt。

## SC 审计完整 Phase 顺序

定义在 `SC_PHASES`：

```text
recon
→ instantiate
→ breadth
→ rescan            仅 thorough
→ inventory_prepare
→ inventory_chunk_a/b/c
→ inventory
→ invariants        core/thorough
→ depth
→ attention_repair  thorough
→ rag_sweep         core/thorough
→ sc_semantic_dedup
→ chain
→ chain_agent2
→ sc_verify_queue
→ sc_verify_* shards
→ sc_verify_aggregate
→ skeptic           thorough
→ crossbatch        core/thorough
→ report_index
→ report_body_writer_{critical_high,medium,low_info}
→ report_{tier} confirmation/merge
→ report_assemble
→ AUDIT_REPORT.md
```

## L1 审计完整 Phase 顺序

定义在 `L1_PHASES`：

```text
bake
→ recon
→ breadth
→ graph_sweeps      thorough
→ inventory_prepare
→ inventory_chunk_a/b/c
→ inventory
→ location_recovery thorough
→ invariants        core/thorough
→ depth
→ attention_repair  thorough
→ rag_sweep         core/thorough
→ verify_queue
→ semantic_dedup
→ verify_* shards
→ verify_aggregate
→ skeptic           thorough
→ crossbatch        core/thorough
→ report_index
→ report_body_writer_{critical_high,medium,low_info}
→ report_{tier} confirmation/merge
→ report_assemble
→ AUDIT_REPORT.md
```

## 关键设计点

- `Phase` 是调度最小单元：名字、prompt section、expected artifacts、timeout、model、mode、critical 都在这里定义。
- `.scratchpad/` 是状态中心：config、checkpoint、prompts、logs、phase outputs、retry hints、degraded sentinels 都在这里。
- driver 不信任 LLM 口头成功，只信 artifact gate。
- phase 之间用文件传递上下文，而不是把整条流水线塞进一个长上下文。
- 子进程隔离执行，能超时、重试、降级、断点恢复。
- 验证和报告前有多层机械校验，避免未验证 finding 混进最终报告。
- 当前版本已明确禁止手工编排 Plamen agents；Python driver 是唯一 phase sequencer。
