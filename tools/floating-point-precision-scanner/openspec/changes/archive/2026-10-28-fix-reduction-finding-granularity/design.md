## Context

本变更的 OpenSpec 根为 `D:/projects/RvPort/tools/floating-point-precision-scanner`。动机和边界见 [proposal.md](proposal.md)。

当前规则注册表将 `reduction-reassociation@1.0` 的 scope 声明为 `loop`，但 `RuleContext.scope` 返回翻译单元 ID，`_reduction()` 收集该单元全部 reduction facts，只返回一个 assessment/Finding。`any(ambiguous)` 会让其他正常候选一起 unknown；TU 中任意 reduction IR 或 reassoc flag 又可能提高全部候选的置信度。`_finding()` 将其他 facts 的位置写成 related locations，后续 v2 投影和前端只是消费这一结果。

`facts.py` 已保存函数 ID、表达式范围和稳定 fact ID，但 AST 遍历目前只传递 `loop_kind`，不能用其区分两个 `ForStmt`；`accumulator` 还可能缺失。运行时已有 ABI、隐式转换逐候选评估路径，可复用其调度形式。现有 `evidence.py` 提供 source/IR bindings 与 ambiguity；不能假定 TU 内任意 IR 属于当前循环。

## Goals / Non-Goals

**目标**

- 独立循环、独立归约候选分别评估，分别处置；同一循环内不同累加器也保持独立。
- 每个候选拥有自己的身份、证据、状态、置信度、抑制与预算行为。
- 维持结果 schema v2、双语信息和既有风险边界，按当前源码提供可重复的测试证据。

**非目标**

- 不修改前端、Java 后端、其他扫描工具或其 OpenSpec 根；不调整位置选择器。
- 不扩展新的归约算法、跨函数数值稳定性证明或其他九条规则的业务语义。
- 不重写历史扫描，不创建数据库迁移、CI/E2E 基础设施或真实 SSH 测试环境。

## Decisions

### 1. 候选身份以独立递推为边界

引入内部归约候选描述，至少携带 TU/编译上下文、函数身份、最近所属循环的稳定身份、更新表达式身份、直接 source fact IDs 和必要位置。scope 由规则版本与这些稳定语义字段生成，不能使用 AST 内存地址、遍历序号、绝对路径或显示文本。

在事实提取层保存最近循环的规范化范围/稳定 ID，必要时解析累加器声明身份；同名变量、相同行号和相同 `loop_kind` 均不足以识别同一候选。嵌套循环使用直接所属的循环；分别维护候选，不能自动并入外层。以已有 source fact ID 区分直接更新，只有证据明确证明属于同一递推的多个事实才归为同一候选；完全相同的重复事实去重。当前支持范围外的复杂递推保留候选级 unknown，不为满足分组而扩大算法范围。

例如 `result += lane` 和随后另一循环的 `result += left[index] * right[index]` 产生两个候选。复用同一个 `result` 声明不能跨循环合并。同一循环内 `sum += x` 与 `product *= x` 也产生两个候选。同一候选的 phi、更新、绑定及来源位置可以成为多份证据，不因此增加 Finding 数。

不采用按 TU、函数或行号分组：这些粒度均无法表示独立风险；也不在前端拆分 occurrence，因为独立 assessment、置信度、计数和抑制必须由生产者给出。

### 2. 逐候选闭合证据与判断

从候选的直接 AST facts 出发，沿有效 binding 收集关联 IR、recurrence/reduction group、flags 和必要 profile/build context；记录可解析的 typed refs。相同函数或行号仅能作为定位线索，不能替代无歧义的关联。检查 binding 目标存在、范围/函数和 inline provenance 相容，排除其他候选的事实。

没有 IR 时，AST 足以支持的顺序敏感归约保持 heuristic，并要求人工确认。只有当前候选的有效关联 IR 和必要 profile/option 差异满足既有规范，才允许提升证据强度；不能仅凭同 TU 有 `llvm.vector.reduce.*` 或 reassoc flag 提升。补偿是否被破坏同样只能使用本候选证据。

候选自身递推不明确、绑定冲突或缺失决定性输入时，返回自己的 unknown。正常候选仍继续产生 matched 或 notMatched。定位未知不等于语义未知：若候选事实和递推身份仍可证明，按既有未知位置协议保留判断；无法安全区分候选身份时使用稳定的直接事实身份记录 unknown，不猜测循环或位置。无关候选的 ambiguity 不进入本候选评估。

### 3. 候选调度、异常与预算

新增归约逐候选评估入口，接入 `evaluate_rules()`，沿用 ABI/转换规则的多 assessment 模型。先按规范化函数、循环、表达式范围和稳定 fact ID 排序，再有界评估，避免先求值全部候选再截断。

`max_rule_candidates`、`max_rule_assessments` 和证据引用预算按独立候选/assessment 消耗；达到上限保留已完成结果并记录稳定 frontier、未评估范围与不完整状态。预算诊断和 frontier 本身遵守现有输出预算，不生成无限 unknown。零候选维持 `no_reduction` 的 notMatched 审计行为，不虚构风险候选。

候选级可分类输入异常生成该候选 failed/诊断，继续处理其他候选；整份 bundle 校验失败沿用现有输入层失败语义，不吞掉全局错误。通用异常保护仍保留，不改其他规则。

### 4. 结果、抑制和兼容性

每个 matched 候选生成一个 Finding；位置与 evidence chain 只来自该候选，主位置必须属于其关联位置集合。`affectedCount` 统计去重后的语义候选数量，普通独立归约 Finding 为 1，不按 AST/IR 证据条数计数。其他位置表示同一风险的证据，而非其他独立风险。归约候选不设置跨候选聚合键，不改变既有配置级风险聚合规则。

候选 ID 在抑制之前生成。仅覆盖一处更新的合法范围抑制不得隐藏另一候选；显式覆盖多个候选的范围按既有匹配规则逐候选处理与审计。summary、诊断归属、assessment refs、occurrence IDs 和 evidence-chain refs 与拆分后的结果一致。

将归约规则版本从 1.0 提升至 1.1，并同步 registry 摘要、文档与 fixtures，保持公共 schema v2。事实增加循环身份后同步事实 mapper/schema 版本及缓存指纹，避免旧缓存返回不含必要身份的事实；只作本工具内所需演进，不新增请求或结果协议主版本。冷/热缓存输出必须一致。新扫描使用新候选身份，旧扫描保持原样；不承诺新旧 Finding ID 或计数相同。添加无关候选不得改变既有候选的身份和证据。

### 5. 单元测试、覆盖率与验证

在 `tests/unit` 为候选构造、判断与引用筛选补充单元测试，在 `tests/contract` 验证 v2 结构和关联；真实 Clang fixture 验证事实能够区分循环，但不能代替单元测试。测试必须断言身份、位置、状态、引用集合与置信度，而不只断言 Finding 数量。

必测：同函数两个循环且复用累加器、跨函数、同循环独立累加器、嵌套循环、同一行不同列/宏位置、重复事实与输入重排、单候选多证据、未知位置、候选 unknown/failed 与正常候选共存、无关 IR、歧义/悬空 binding、补偿与非补偿共存、单元素/固定顺序、预算边界、候选级 suppression、冷/热缓存和双语完整性。固定语料的预期独立写出，不能用当前实现输出自动回填 oracle；真实 observed 需从本次源码生成。

Python 统计整个 `src/floating_point_precision_scanner`，包括未加载文件，整体和每个受影响模块的行/分支覆盖率均至少 90%。保持现有覆盖范围与更严格门槛，将新增受影响模块补入 `make coverage` 的自动 gate。C++ 继续运行 `make cpp-coverage`，覆盖所有 `src/cpp` 自有源码；如修改 C++ 则补足对应模块独立门禁。仅排除第三方 LLVM/GTest、生成构建文件和无运行行为的 `TYPE_CHECKING` 导入分支，不排除业务逻辑。历史缺口导致大规模范围扩展时先报告，不标记质量验收完成。

实现阶段在仓库根的 PowerShell 中按顺序执行以下现有入口；以下命令是待执行计划，本提案没有运行它们：

```powershell
Set-Location D:\projects\RvPort
docker build -f tools/floating-point-precision-scanner/Dockerfile.dev -t rvport-fp-granularity:local tools/floating-point-precision-scanner
docker run --name rvport-fp-granularity-unit --memory=8g --cpus=2 --network=none -e CMAKE_BUILD_PARALLEL_LEVEL=2 rvport-fp-granularity:local make lint typecheck coverage cpp-coverage
docker cp rvport-fp-granularity-unit:/workspace/artifacts/coverage ./.migration-reports/fix-reduction-finding-granularity/coverage
docker run --name rvport-fp-granularity-integration --memory=8g --cpus=2 --network=none -e CMAKE_BUILD_PARALLEL_LEVEL=2 rvport-fp-granularity:local make integration
```

执行前确认上述专用容器名称可用，并创建本次报告目标目录；失败时先导出已有报告与日志，不以旧容器或旧镜像重跑冒充当前源码。`make validation` 当前读取固定 observed 文件，单独运行不构成当前源码的真实扫描证据；实施时按工具现有验证说明重生成实际 observed 并记录其来源摘要，再执行语料门禁及适用的既有更严格门槛。

按仓库约定，代码交付前还需从仓库根对全部默认服务完成 Compose 构建，并以一次 `docker compose up -d --wait` 启动检查。使用专用 Compose 项目、隔离网络/卷、测试凭据和不冲突端口，先检查解析配置，确保没有现有部署数据卷或真实 SSH 目标；以构建并发 1 依次构建，应用适当资源上限。检查健康、日志及两处归约生成两条结果的代表性流程；不修改前端源码、不建立新 E2E 设施。如环境阻塞，明确保留该任务未完成。报告保存于 `.migration-reports/fix-reduction-finding-granularity/`，公开文档只记录脱敏命令、指标、范围和报告位置。

## Risks / Trade-offs

- 候选拆分后条目和 assessment 增多 → 候选预算提前生效，明确截断范围，不依靠合并隐藏数量。
- 实际 AST 缺少 accumulator 元数据 → 从已有声明/表达式事实补足可靠身份；仍不明确的复杂递推局部 unknown。
- binding 的 strong 标签不一定足以证明唯一递推 → 检查候选归属和冲突，保留歧义，禁止全 TU 证据兜底。
- 单元测试原本允许任意 IR 提升置信度 → 按规范修正预期，并增加无关 IR 负例，不能机械保留旧行为。
- 新版本 ID/计数变化 → 规则版本及缓存版本明确演进，保留历史结果，通过重新扫描获得新粒度。

## Migration Plan

先建立可复现的候选隔离用例，再实现事实身份、规则判断、调度和结果契约，最后完成 Docker 单测、覆盖率、当前语料及仓库级验收。全部通过后才同步规范并归档。部署使用包含本次工具版本的新镜像，无数据库迁移；若回滚，只恢复先前镜像供后续扫描使用，不改写已保存结果，也不声称旧版本已经修复。

## Open Questions

### 2026-10-28 授权补齐完整语料

此前十规则历史语料缺少可执行输入，用户已同意扩大范围补齐该验收缺口。新增固定输入与独立预期文件，运行器只读取输入，逐 case 在临时目录中调用真实 Clang/Scanner，需要共享 IR 时现场编译并生成符合公开协议的 manifest。libm 使用明确标记的固定测试 overlay。保留历史 oracle/observed 作为旧评分器回归基线，不再用其证明当前实现准确率。

`make validation` 必须先生成当前 observed，再评分；完整 v2 原始结果、源码与输入摘要一同导出。新评分模式比较所有候选状态、位置重数、affectedCount、扫描状态、诊断和抑制数量；重复 Finding 计 FP，mixed matched/unknown 不被第一条 assessment 掩盖。来源摘要或 case 集合不一致直接失败。独立语料的修订依据记录在 `review_basis`，禁止自动从 observed 回填预期。

新增运行器与评分器变更均补正常/异常单元测试并纳入逐模块 90% 行/分支门禁。继续保留十规则各 6 正例、6 反例、3 unknown，strict precision/recall 90%、整体 exact 95%、生命周期 exact 100% 和原 S/M/L 性能门槛。最终使用新源码镜像重跑全部工具检查与隔离 Compose 验收；此前通过记录仅作为历史追溯。

部署验收发现仓库 Docker 的 `tools/**/build-*` 排除规则会丢弃内部 build-context schema。修复限于本工具：将资源移动到 `schemas/contexts/v1/context.schema.json` 并更新 registry 路径，保留公开 `$id` 和请求合同；增加所有 schema 资源不命中构建输出名称的合同测试。随后重新构建和核对安装包全部源码/协议摘要，并在安装版本验证 libm 请求。

### 实施补充

- 内部版本为 facts 1.5 / mapper 1.2 / evidence 1.2 / registry 1.3，规则为 1.1；请求与结果版本不变。
- AST 的复合赋值位置通常指向左值，LLVM debug 位置指向运算符，因此有效关联还可使用
  已知表达式范围；保留函数、运算类型与候选唯一性检查，不用单独行号建立归属。
- 同循环同声明但运算类型不同的递推保留 unknown；复杂左值无可靠声明身份时也局部 unknown。
- 确定性置信度要求 build-faithful IR 的自身 reassoc/fast 标志，以及已知 profile 的
  `evaluation.value.reassociation` 明确从源 true 到目标 false。当前内置 profile 没有该字段，
  不据 x87 或其他无关差异推断重结合策略。

无须用户补充的产品范围决策。实施前需用真实 Clang 21.1.8 fixture 确认最近循环/累加器声明的可提取性，以及当前 binding 对同一行多个候选的区分能力；按上述保守边界处理缺失，不扩大算法或跨项目范围。
