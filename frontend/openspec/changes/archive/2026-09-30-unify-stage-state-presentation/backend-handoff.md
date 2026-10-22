# 阶段状态展示：后端契约核对与修复请求

以下可直接转发后端。核查日期：2026-09-30。结论来自当前代码静态阅读，未在真实环境执行并发或失败任务；本轮未修改后端。

## 背景

前端已确认两套默认展示：

- x86 构建、构建验证、自动化测试采用“当前条件＋历史记录”。历史跨源码版本，暂不新增版本筛选；已有运行任务不额外触发前端全局禁用，新建以服务端实际执行条件为准。
- 依赖、知识库、内存序、浮点、报告、优化、归档采用“当前概览＋历史入口”。可执行阶段在等待、排队、运行期间不提供再次执行入口；优化是被动聚合。
- 当前门禁变化不能改写旧任务的真实状态，历史阅读也不应受当前门禁限制。

为避免 readiness 与提交结果矛盾，请协助对齐以下契约。建议优先修复第 1 项；第 2–4 项先确认业务必需条件；第 5–6 项需要明确策略。

下述 Java 路径除另有说明外，相对 `backend/src/main/java/cn/rvport/backend/`。

## 1. 自动化测试门禁使用了测试自身状态，应修正

**现有实现：** `workflow/StageReadinessService.java` 的 `test()` 优先取当前上下文最新 automated test，将其状态和 ID 映射为 `BUILD_VALIDATION`。只有不存在测试记录时，才查询两侧 BOTH 构建结果；双方成功才返回 `sourceBuildRunId`、`targetBuildRunId`。`automatedtest/AutomatedTestService.java` 的 `create()` 又要求这个条件满足。

**影响（静态推导，尚未实测）：**

- 已有测试运行时，新建测试被当成“构建验证未满足”拒绝。前端同批 SOURCE/TARGET 使用 `Promise.allSettled` 并行提交，存在一侧先创建、另一侧随后被门禁拒绝的时序风险。
- 测试失败、取消、超时会阻断同上下文再次测试，即使构建仍然有效。
- 测试成功后，readiness 不再核验两侧构建，且缺少上述构建 ID；测试自身状态不应冒充构建事实。

**请求：** `BUILD_VALIDATION` 始终依据当前有效的两侧构建，返回稳定、可追踪的构建引用。是否允许多批测试并发作为独立执行策略表达，不能借用构建条件实现。明确同批两侧创建及失败侧补交行为。

**建议验收：** 两侧构建有效时，覆盖无测试、已有运行测试、失败/取消/超时/成功测试，以及同批两侧提交和失败侧补交；readiness 引用始终指向构建。

关联：`backend/src/test/java/cn/rvport/backend/workflow/StageReadinessServiceTests.java` 包含按最新测试状态推导条件的断言，需同步修正；前端提交入口为 `frontend/src/pages/project-detail/StageDrawer/AutomatedTest/useTestBatchSubmission.ts`。

## 2. 知识库 readiness 与创建校验不同

readiness 要求 `ACTIVE_SOURCE` 和 `X86_BUILD`；`kb/KbScanService.java` 的 `create()` 主要解析源码、校验工作副本，没有使用相同 x86 构建门禁。

请确认扫描是否必须依赖当前有效 x86 构建，并统一 readiness 与 POST。这里核查的是创建契约差异，不表示扫描运行时绝不使用构建相关内容。

建议覆盖无构建、构建运行、失败、成功四种状态，检查可提交语义一致。readiness 入口是 `workflow/StageReadinessService.java` 的 `analysis()`。

## 3. 内存序/浮点分析的实际制品条件未完整进入 readiness

readiness 主要返回当前源码、最新 x86 构建状态、专项工具健康；`analysis/SpecializedAnalysisService.java` 的 `create()` 还要求环境完整、compile database、Shared Bitcode manifest/bundle 及其版本和有效制品，并使用 `findLatestSucceededSourceBuildWithCompileDatabase` 选择可用成功构建。

由此可能出现：

- readiness 满足，POST 因缺少制品拒绝。
- 最新构建运行/失败导致 readiness 受阻，而创建仍可能使用更早的有效成功构建。

请统一本次分析的构建选择规则，并让 readiness 与创建共享必要条件和输入引用。若允许复用旧成功构建，请明确源码、环境、制品的兼容范围；若不允许，创建也应遵守最新构建规则。

建议两种分析分别覆盖：缺 compile database、缺/无效 Bitcode、工具不可用、环境不完整、最新构建运行/失败但存在旧成功制品。readiness 入口为 `StageReadinessService.specializedAnalysis()`。

## 4. 评估报告的硬前置需要明确

readiness 返回 `KB_SCAN`、`DEPENDENCY_ANALYSIS`、`INCLUDED_FINDINGS`、`COMPARABLE_REPORT`；前端目前以前三项判断可执行。`report/ReportService.java` 的 `create()` 只要求 `INCLUDED_FINDINGS` 并校验当前源码；有源码时，纳入问题数量为零也会返回满足。

请明确哪些是硬前置，哪些仅提供信息或可选能力，并对齐 readiness、POST 和前端。我们没有要求问题数必须大于零；零问题报告是否有效按业务定义。可比较报告也不能无意升级为生成硬前置。

建议覆盖 KB/依赖未执行、运行或失败，问题为零，以及没有可比较报告的情况。readiness 入口为 `StageReadinessService.report()`。

## 5. 构建/测试并发：确认工作目录隔离或调度策略

前端不计划用“存在运行任务”统一禁止创建构建，这不等于底层并发安全已经验证。

静态核查发现：

- `BuildValidationService` 创建未见同目录活动构建互斥。
- 构建复用源码部署目录，回退路径基于源码版本而非运行 ID；SOURCE_ONLY 与 BOTH 的 SOURCE 侧可能共享目录。
- Worker 支持多个消费者，队列本身不能证明同目录任务串行。
- 测试虽关联 buildRunId，但实际在指定 workingDirectory 执行，关联 ID 不能证明输出已做不可变快照。

请确认同环境、同源码目录的多个构建，以及构建与测试重叠时，是否有隔离目录、制品快照或资源锁/调度。若不支持同时执行，请由服务端按真实共享资源约束，返回明确的等待/冲突原因，避免依赖前端按钮。

这是待确认风险，不是已经实测的数据损坏。建议验证两个构建重叠、SOURCE_ONLY 与 BOTH 重叠、测试时重建、跨环境执行。

核查入口：`BuildValidationService.createOne/remotePath`、`SourceDeployExecutor.ensureDeployed`、`BuildValidationHandler`、`AutomatedTestHandler`、`WorkerConcurrencyController`，以及前端 `useTestBatchSubmission.ts` 的 workingDirectory 输入。

## 6. latest 与活动任务的选择语义

多处 latest 查询优先活动任务，再按创建时间选择；专项分析存在先跨源码选择记录、再标注 freshness 的实现。latest 因而未必是创建时间最新记录，也不代表全部活动任务。

请明确各阶段 latest 的选择范围、源码/环境变化时的 freshness 判定，以及多活动任务时如何选择。前端需要区分当前有效结果与仍运行的旧版本任务；若单个 latest 无法表达两者，请明确可依赖的查询或补充契约。

当前概览型运行时隐藏再次执行入口是前端产品规则；创建路径未见统一的自身活动任务互斥，因此不能承诺多标签页/客户端只能创建一个任务。若业务确需互斥，应由后端实现；不因前端隐藏按钮就默认增加全局互斥。

## 7. 跨版本历史与测试批次分页

构建、依赖、知识库列表 `effectiveCurrentOnly()` 默认 true，可用 `includeStale=true` 或 `currentOnly=false` 退出当前约束。前端历史查询会显式使用现有参数并移除当前源码/环境绑定；执行输入查询仍保留当前上下文。这部分优先前端适配，无需后端统一改默认值。

自动化测试列表没有同样的参数，前端按实际契约查询。默认展示单位已确定为批次，请确认现有 tests/comparisons 查询是否支持跨版本批次完整聚合和正确分页，不能将一页原始测试行当作完整批次页；若不足，再明确批次列表接口需求。

历史详情、日志和下载继续按记录身份及权限读取，不因当前源码切换或 readiness 不满足而不可访问。

补充接口限制：知识库扫描列表当前只支持 `startedAt` 等排序，不支持 `createdAt`；前端暂用 `startedAt desc`。若要求所有历史严格按创建时间倒序，请提供该排序字段与稳定次序。自动化测试支持 `createdAt` 排序但响应不含该字段，前端保留服务端顺序，暂不展示伪造的创建时间；当前通过读取全部原始页再按批次分页保证完整性，大规模历史建议提供服务端批次分页。

## 希望后端反馈

1. 测试门禁修复方案及稳定构建引用契约。
2. 知识库、专项分析、报告各自必需条件、输入选择规则和修复范围。
3. 构建/测试并发已有的隔离调度保证，以及 latest/freshness 语义。
4. 跨版本测试批次列表及分页是否已有完整支持。

前端据此完善适配，不会忽略后端拒绝、伪造条件满足或把未验证并发写成已支持能力。
