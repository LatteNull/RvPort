# 统一项目级内存序分析

[English](UNIFIED_PROJECT_ANALYSIS.md) | 简体中文

`analyze-project` 是后端生产集成的唯一入口。它接收一份 `UnifiedMemoryOrderAnalysisRequest v1`，读取请求引用的外部 `ExternalBitcodeBundleManifest`，按显式 Scope 隔离分析，并输出 `UnifiedMemoryOrderAnalysisReport v1`。既有高级 CLI 保留给开发、诊断和协议回归，不要求后端依次调用。

## 输入边界

- Project 是一次任务的聚合边界；Scope 是跨 TU 语义边界；BC/TU 是不可拆分的输入原子。
- 请求的 `scope_selection` 可为 `all`，也可给出排序且去重的 `scope_ids`。
- bundle 必须声明 planned TU 分母、BC digest、producer/LLVM 版本、target、DataLayout、ABI、语言标准、profile、physical TU、source lineage、Scope 和生成失败项。
- 不同 target、DataLayout、ABI 或 Scope 的证据只做项目级并列聚合，绝不简单链接或合并成一个程序结论。
- `compile_commands.json` 只可用于外部生成的源码 profile/SourceIRBinding；统一入口不从中生成 BC，也不以它推断完整 Scope。

生产入口禁止调用 GCC/Clang driver、`-emit-llvm`、linker、CMake configure/build、网络、SSH 或目标程序。允许的可执行组件仅是锁定版本的 LLVM reader/分析 worker 和 source worker。

## 请求与执行 DAG

公共请求只暴露 bundle、Scope 选择、`source_assistance`、显式 root、固定 policy、预算、cache/resume、deadline 和 cancel file。内部 stage 开关不是公共合同。

```text
bundle preflight / external BC ingestion
  ├─ AST source facts（每个计划 TU 独立）
  └─ ModuleFacts / LLVM lightweight index
          ↓
ExecutionRoot + ThreadEntry bootstrap
          ↓
R3 bounded demand worklist
          ↓
P2 effects + P3/A3 lifecycle + A4 synchronization + A5 provenance
          ↓
R2 concurrent-access candidates
          ↓
P4 publication + A6 fence/RMW/CAS overlay
          ↓
Finding projection + Scope/project aggregation
```

`UnifiedAnalysisPlan` 为每个 Scope 固化 stage ID、版本、producer、输入/输出 kind、依赖、适用条件、预算、缓存和失败策略。task ID、绝对输出路径、时间、调度顺序和 cache hit/miss 不进入 semantic digest。root/direct-call/callback/递归扩展使用有界单调 worklist；超预算形成非空 frontier，不回退到 all-defined 扫描。

## AST/IR 四模式

AST 是每个计划 TU 的独立事实层，不是 BC 失败后临时补跑：

| 模式 | 可用证据 | 允许的外部结论 |
| --- | --- | --- |
| `ast-ir` | AST 与相容 IR | 可继续既有受限正式分析 |
| `ir-only` | IR 可用，AST 不可用/不可信 | 保留 IR provenance；源码位置可能 unavailable |
| `ast-only` | AST 可信，BC/IR 不可用 | 仅 source-only candidate、partial/unknown 和 breaks |
| `failed` | AST 与 IR 均不可用/不可信 | failed 或候选相关 frontier |

`source_assistance=auto` 使用可用可信 AST；`required` 把相关 AST 缺失传播为 incomplete；`disabled` 明确只走 IR。fatal diagnostic、error recovery、profile 冲突或 source digest 不匹配的 AST 不可采用。AST-only 不得建立运行时对象身份、alias/noalias、byte overlap、ThreadInstance、RF/MO/release sequence、SW/HB、formal risk 或 bounded discharge。

完整性按候选依赖切片传播：无关失败 TU 不降低独立候选；相关或相关性未知的失败必须降级。零候选不能掩盖未分析或未知相关性。

## Scope 隔离、恢复与失败传播

协调器最多有限并行执行互不依赖的 Scope，结果按稳定 Scope ID 排序发布。单个 Scope/stage 失败不会删除其他 Scope 已完成的发现。每个 `ScopeAnalysisExecutionRecord` 保存 TU 模式、stage 状态、完整性分母、诊断和 frontier。

缓存键包含规范化请求、bundle/Scope、record digest、stage/version 和预算。只缓存 `complete` 且依赖闭合的 Scope payload 和不可变 artifact；读取时重新校验 namespace、key、payload digest、schema、Finding、artifact path/digest。partial、cancelled、worker crash、损坏或冲突缓存不得当作成功复用。cache hit 只进入运行元数据，不改变 semantic digest。

deadline 与 cancel file 在 ingestion、Scope 和主要 stage 边界协作式检查。停止后不再调度新 Scope，已完成结果仍原子发布；未完成节点不会写入成功缓存。fresh output 先在同目录临时树中生成，成功或可审计的停止报告完成后一次替换，已有目标目录会被拒绝。

## 输出与后端责任

主要输出：

- `request.json`、`plan.json`、`report.json`；
- `scopes/<scope>/execution.json`；
- `findings/`、`source-candidates/`、`discharged-assessments/` 的逐项 JSON；
- `source-snapshots/<sha256>/source` 与带 digest 的 `artifacts.json`；
- `data/` 下保留既有 stage 原始事实与报告，供离线审计。

后端只需准备外部 bundle/可选源码请求、运行一次命令、按退出码和 report 状态结束任务、保存完整输出，并可逐条持久化 Finding。后端不得重建内部 stage 请求或根据某一阶段的空数组自行判定安全。前端列表读取结论摘要，详情直接读取自包含 evidenceChain；扩大代码上下文必须按 artifact index 和源码 digest 读取分析时 snapshot。

## 项目结论与退出码

| 退出码 | verdict | 含义 |
| --- | --- | --- |
| 0 | `no-finding-within-supported-model` | 所选相关切片完整，受支持模型内无 formal risk |
| 3 | `risk` | 所选相关切片完整，存在 formal risk |
| 2 | `inconclusive` | partial/unknown/ambiguous/AST-only/open Scope/预算/取消/可保留失败；优先于 risk |
| 1 | `failed` | 请求无效、无法建立任何所选 Scope 或所有证据失败 |

`complete`、exit 0、零 Finding 或 `discharged-within-bounded-model` 均不得翻译为全程序安全。
