## Context

当前数据采集顺序是 scope 内逐 TU compile-only BC/AST 事实先生成，P2/P3 再使用显式 roots，P4 最后把所有 member 的局部 publication facts 与线程图组合。该实现已经避免“只看 load/store 就报警”，但线程创建证据分别存在于 A1 source facts、P3 LLVM local facts、A3 `std::thread` sidecar 和 P2 adopted calls 中，没有一个产物统一回答创建点基数、入口覆盖、可达上下文和缺失证据。P1 `ModuleFacts v2`、P2 `EffectSummary v1`、P3 `ThreadContextGraph v1`、P4 与 A1–A5 均已有稳定协议和回归，本 change 不能用架构调整破坏它们。

R1 因而采用 additive orchestration：继续允许 P1/A1 在 scope 内生成全量基础事实，在其上建立轻量视图和 root plan；真正把 P1 改为按函数懒提取留给 R3。输入限定 GCC/Clang 用户态 C/C++，四种语言 profile 独立，`compile_commands.json` 只提供 TU 配置，目标成员仍由显式 `ScopeManifest` 决定。

目标数据流为：

```text
compile_commands + ScopeManifest
              │
       P1 ModuleFacts + A1 source/entity/binding
              │          P3 pthread local + A3 C++ lifecycle/profile
              └────────────────────┬─────────────────────────────┘
                                   ▼
                     lightweight global evidence view
                                   ▼
                  AST candidates ∪ BC/IR candidates
                                   ▼
                     ThreadCreationSiteIndex v1
                                   ▼
                 explicit/main/exported/thread roots
                                   ▼
                       ExecutionRootIndex v1
                                   ▼
              bounded adopted-call/wrapper fixed point
                                   ▼
                    RootDrivenAnalysisPlan v1
                         │                   │
                         ▼                   ▼
                    P2 roots mode       P3 roots mode/A3 overlay
                         └──────────┬──────────┘
                                    ▼
                       RootDrivenAnalysisReport v1
```

## Goals / Non-Goals

**Goals:**

- 以一个版本化协议统一 AST 与 BC/IR 的线程创建候选、证据分类和 root 身份。
- 支持显式程序/库/框架入口、受限自动 main、直接 pthread 和 A3 已验证 `std::thread` callable。
- 从正式 roots 有界生成 reachable function/context/TU 与 P2/P3 demand，保留每条采用和缺失证据。
- 为 root coverage、reachable coverage、候选相关完整性、预算、缓存和双语诊断提供稳定分母。
- 保持所有旧命令、产物、风险规则和缓存兼容，并为 R2/R3 提供清晰输入边界。

**Non-Goals:**

- 不修改或重新发布 P1–P4/A1–A5 的既有版本。
- 不将 P1 转为真正的函数级按需 extraction，不宣称不可达函数未被底层扫描。
- 不生成并发访问对、P4 finding/discharged、安全结论或通用 data-race/HB。
- 不支持通用函数指针、虚调用、线程池、executor、自定义异步框架自动识别、fence 或 RMW/CAS。
- 不从编译数据库、共同头文件、目录或符号名称猜测 target scope、exported roots 或线程语义。

## Decisions

### 1. 使用 additive R1 sidecar，而不是升级 P1/P3/P4

新增五个公开产物并保持旧协议只读：

- `ExecutionRootDiscoveryRequest v1`：scope、root seed、是否发现 main、按 TU 的 source/IR/P3/A3/P2 引用、模型和预算。
- `ThreadCreationSiteIndex v1`：AST 与 IR 候选并集、对齐组、分类、callback/handle/success 证据和 frontier。
- `ExecutionRootIndex v1`：正式、候选和失败 roots，以及创建来源或 external-parent 语义。
- `RootDrivenAnalysisPlan v1`：reachable functions/contexts/TUs、P2/P3 demand、adopted edges、frontier和依赖切片。
- `RootDrivenAnalysisReport v1`：层级状态、完整分母、缓存、双语诊断和退出码。

选择 sidecar 而不是 P3 v2，是因为入口发现先于线程图且同时依赖 A1/A3；把它塞回 P3 会使旧 pthread 模型、缓存和 P4 传递身份全部失效。旧 P4 继续作为兼容基线，R1 只报告计划，不解释历史 finding。

### 2. R1 先复用现有局部事实，缺字段时只增加独立补充事实

轻量视图优先消费：P1 function/call/symbol、A1 `SourceSemanticFacts`/`ProgramEntityIndex`/`SourceIRBinding`、P2 adoptions、P3 `ThreadLocalFacts`、A3 local/lifecycle/profile。P3 local worker 可以在没有最终线程图前提供直接 pthread IR 候选，解决 root discovery 的自举问题；A3 提供 `std::thread` 的 source/ABI wrapper 证据。

实现审计若发现 required 字段无法从这些产物无损得到，只允许由 source/IR worker发布 R1 独立补充事实，并以新 kind/digest 被请求引用；禁止给 `ModuleFacts v2`、A1、P3 或 A3 偷加字段。与“直接重写 P1 extractor”相比，该方案更容易回归和回滚，代价是 R1 阶段仍会读取 scope 内全部基础事实。

### 3. 候选取并集，exact 采用取证据交集

AST 与 IR 分别形成候选后按稳定 callsite/source binding 对齐。初始分母为并集，以避免优化、no-debug 或单侧失败把创建点静默删除；正式 root 采用则要求对应分类的全部证明条件：

| 分类 | 条件 | 能否建立正式 root |
| --- | --- | --- |
| `dual-exact` | AST/IR callsite、callback、ABI/profile、scope 唯一一致且无 opposed evidence | 是 |
| `ir-exact` | AST 不可用；已验证直接 pthread 或已锁定 runtime profile、callback SSA与定义唯一 | 是，但 source completeness 降低 |
| `source-candidate` | 可信 AST 有候选，IR/runtime 证据缺失 | 否 |
| `ambiguous` | 多候选、AST/IR 冲突、定义或 wrapper 不唯一 | 否 |
| `unsupported` | 已识别形状超出模型/profile | 否 |
| `failed` | 输入、worker、schema、profile 或关键绑定失败 | 否 |

LLVM callback metadata 只能作为支持证据，不能单独证明新线程、并行、创建成功或生命周期。函数名、类型名、mangled name 和相邻源码位置同样不能单独升级分类。

### 4. ExecutionRoot 同时表达程序入口与线程入口

只定义 ThreadEntry 会遗漏父线程 create/join 前后的效果，因此统一使用 ExecutionRoot。请求中的显式 roots 始终优先；自动 main 必须由调用方启用，且只接受 closed scope 内唯一相容 external definition。库 exported roots 和框架线程 roots 必须显式列出并绑定 program entity，使用 external-parent 语义；不会枚举全部 external symbols。

pthread/std::thread root 绑定创建点、callback、抽象参数和父 root/context。同一 callback 在两个 callsites 可复用分析模板，但创建来源和动态实例 identity 不合并。AST-only/ambiguous root 进入索引和 frontier，不进入 P2/P3 正式 roots。

### 5. 可达规划使用受限固定点而非全定义扫描

planner 从正式 roots 开始，只沿以下边扩展：

1. P1/A1 唯一且 ABI/profile 相容的直接绑定；
2. P2 已 adopted 的 direct-call edge；
3. 明确版本化且当前请求启用的 wrapper 摘要；
4. exact 创建点到 callback root 的 spawn edge。

每个 context identity 包含 scope、root、artifact/function、抽象实参、调用/创建来源、模型和预算。递归 SCC 与重复创建执行有界迭代并产生 merged/repeated frontier；间接/虚调用、开放外部边界或歧义 wrapper不得从候选中任取目标。输出列出 demanded 与 observed-but-not-demanded facts，明确 R1 尚未让 P1 懒提取。

### 6. 现有 P2/P3 由计划显式驱动且保持原输出

R1 为每个正式 root/context生成 P2 `mode=roots` 请求，绝不回退到 `all-defined`。pthread program roots使用现有 P3 roots模式；A3 exact callable 作为函数效果 root并引用 A3 lifecycle overlay，不伪装为 P3 原生 pthread create。R1 在独立输出子目录运行或引用既有 P2/P3 结果，并验证实际 roots、scope和 digest与计划一致；不改写 P2/P3报告。

若 R1 计划与 P3/A3 实际发现的 callback/instance 不一致，报告生成 `plan-observation-mismatch` frontier并降级，而不是让后执行阶段静默扩大或缩小 root 集合。

### 7. 完整性按 root 依赖切片而不是全局一刀切

报告至少记录：

- creation sites：planned/source/IR/aligned/exact/candidate/ambiguous/unsupported/failed；
- roots：seeded/discovered/formal/candidate/failed；
- reachability：functions/contexts/TUs/call edges planned/completed/partial/failed；
- downstream demand：P2/P3 planned/completed/partial/failed；
- frontier：root、call、wrapper、profile、TU、budget 与 dependency slice。

无关失败 TU 可以不降低某个 root plan，但必须留在顶层 scope diagnostics；相关缺口使该 root 和总报告 partial。零创建点只有在完整分母闭合时才表示“本 scope/request 未观察到受支持创建点”，仍不表示无并发或安全。报告固定 `safety=not_evaluated`、`findings=null`。

### 8. CLI、输出、缓存与预算

新增用户入口建议为：

```bash
python3 -m memory_order_analyzer plan-execution-roots \
  --request /input/root-request.json \
  --artifact-store /artifacts \
  --output /output/root-plan \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

输出目录必须不存在，包含 `request.json`、`thread-creation-sites/index.json`、`execution-roots/index.json`、`plans/<digest>.json`、引用或子运行的 `effects/`/`threads/` 和 `report.json`。缓存使用 `execution-root-driven-analysis-v1` 命名空间，key 覆盖全部依赖、root seeds、model/wrapper/profile、预算和实现 identity；cold/warm semantic digest 排除命中计数。

预算覆盖 members/TUs、source/IR/binding candidates、roots、functions、contexts、edges、wrapper depth、SCC iterations、frontier、诊断、worker/request 时间和输出字节。退出码为 `0` complete、`2` partial/unknown/unsupported、`1` invalid/全部不可用；不使用风险码 `3`。用户字段提供中文和英文，翻译不参与 identity。

### 9. 文档和阶段拆分

新增 `doc/EXECUTION_ROOT_DRIVEN_ANALYSIS.md` 说明架构、协议、CLI、证据分类、完整性和限制；README 概览改为“全局基础事实 + root-driven 深度计划”；路线图修正 A5 已于 2026-09-22 同步归档，并新增：

- R1：本 change 的 root discovery/planning；
- R2：`ConcurrentAccessCandidateGraph` 与协议消费者适配；
- R3：按函数/上下文的真正懒提取和规模验证。

验证文档与机器 acceptance 必须区分实际执行结果、设计边界和历史 DevKit 证据；零 finding、exit 0 或成功 BC 编译均不得写成安全证明。

## Risks / Trade-offs

- [R1 仍需读取全 scope 的 P1/A1/P3 local facts，短期性能收益可能有限] → R1 的验收重点先放在 root 覆盖和语义正确性，记录 demanded/observed 比例，为 R3 是否值得重构提供数据。
- [AST 与 IR 候选并集会增加 candidate/frontier 数量] → exact 采用保持严格交集证明，使用稳定对齐键、显式预算和候选相关切片控制规模。
- [现有 P3 会再次发现 pthread callbacks，与 R1 计划可能重复] → 以 identity/digest 对账，重复 exact 事实去重，任何集合差异产生 frontier而不是任选一方。
- [无 main 的库和框架入口容易被遗漏] → exported/framework roots 必须显式声明，报告单列 seed coverage，不把缺失配置解释为无并发。
- [标准库或优化变化导致 std::thread profile 漂移] → 继续复用 A3 verified profile；失配为 unsupported/partial，不做符号相似匹配。
- [新编排层与旧命令同时存在会增加操作复杂度] → 保留旧 CLI 作为兼容基线，README 提供推荐 R1 路径，所有产物有独立 namespace 和明确迁移说明。

## Migration Plan

1. 添加协议清单、schema、契约和合成单元测试，不改变 CLI 默认路径。
2. 实现现有 P1/A1/P2/P3/A3 产物适配与候选并集/对齐，建立四语言 fixture。
3. 实现 ExecutionRootIndex、planner、预算、缓存、报告和 `plan-execution-roots` CLI。
4. 接入 P2/P3 roots 子运行与 plan-observation 对账，保持旧命令输出 golden 不变。
5. 更新 README、架构/验证/acceptance 和路线图，运行全量离线 quality gate。

回滚只需移除新 CLI、R1 schema/模块和独立缓存 namespace；因为旧协议和命令未修改，历史产物无需迁移或重写。若实施中发现必须修改 P1–P4/A1–A5 协议，应停止并修订本 change，而不是隐式升级。

## Open Questions

- 当前无阻塞提案的问题。默认设计确定为：自动 main 必须由 request 启用；exported/framework roots 必须显式声明；R1 只规划并验证既有 P2/P3 执行，不实现 R2 风险候选。
