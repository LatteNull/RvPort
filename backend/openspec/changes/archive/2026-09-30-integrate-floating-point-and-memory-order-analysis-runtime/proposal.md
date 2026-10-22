## Why

共享 LLVM BC v2 已能稳定描述源码版本、编译上下文、逐 TU BC、能力和 Scope，但后端尚未把已经具备统一调用协议的浮点精度扫描器和强弱内存序分析器接入任务、查询、人工确认、报告与归档闭环。现在需要以两个工具最新的版本化输入输出契约为边界，在 `backend-worker` 内直接运行分析，使分析结果可以被前端查询、确认并纳入迁移报告，而不让 Java 依赖工具内部分析阶段。

## What Changes

- 增加浮点精度扫描运行时：基于当前源码版本、成功的 source/x86 构建、`compile_commands.json`、共享 LLVM BC v2 以及项目当前源/目标环境上下文创建异步任务，在 Worker 内调用 `fp-precision-scanner scan`，校验并导入结果 schema v2。
- 增加强弱内存序分析运行时：将共享 LLVM BC v2 确定性适配为 `memory-order-analyzer` 外部 bundle，请求统一的 `analyze-project` 入口，并按照其统一报告、Finding schema 2.0 与退出码语义导入结果；Java 不编排 ingestion、AST/IR、线程建模或风险识别等内部阶段。
- 两类分析分别提供创建、latest、运行列表、运行详情、Finding 分页过滤排序、Finding 详情、人工确认和结果制品下载 API；所有接口校验项目权限并保持独立业务语义。
- 增加公共专项分析执行基础设施，用于解析和安全物化源码、compile database 与 BC bundle，管理工作目录、子进程、超时、取消、日志、缓存目录和结果原子导入；工具直接安装并运行在 `backend-worker`，不增加扫描容器或 `docker.sock`。
- 分别保存分析运行和逐条 Finding，保存工具原始 JSON 与后端生成的 HTML 到对象存储；数据库仅保存可查询、排序、过滤的结构化列、安全摘要和完整 Finding 详情，不把整个大型结果写入单字段。
- 明确工具状态映射：Finding 不导致任务失败；memory-order 退出码 `3` 表示成功发现风险，`2` 表示可查询的 partial/unknown/cancelled，只有协议所定义的失败才进入失败终态；浮点扫描的 `complete/partial/invalid_request/failed/internal_error` 按协议映射。
- 将两类 Finding 接入节点内迁移输入确认、当前源码版本失效判断、项目 overview、阶段 readiness、领域 latest、项目 SSE、评估报告与可插拔归档候选；重跑同类分析时按当前源码版本刷新同类候选，但保留历史运行与历史报告快照。
- 在后端/Worker 镜像中安装两套 Python 运行时依赖和 LLVM 21 工具二进制，固定版本并提供启动期可用性检查；不要求目标 SSH 环境安装扫描器。
- 增加独立 E2E 模块，使用真实源码、真实 `compile_commands.json`、真实 Shared LLVM BC v2 和真实工具二进制覆盖两类完整流程，并清理数据库、对象存储和临时目录测试数据。

## Capabilities

### New Capabilities

- `floating-point-analysis-runtime`: 浮点精度扫描的输入解析、Worker 执行、状态映射、运行与 Finding 持久化、查询、确认和结果制品。
- `memory-order-analysis-runtime`: 强弱内存序统一项目分析的 bundle 适配、Worker 执行、退出码/结论映射、运行与 Finding 持久化、查询、确认和结果制品。

### Modified Capabilities

- `shared-llvm-bitcode-artifacts`: 增加两类分析器对 v2 artifact-set 的 resolver、materializer、完整性校验与确定性适配要求。
- `task-runtime`: 增加两类任务类型、阶段元数据、Worker 日志/取消/终态、项目事件和运行中状态要求。
- `backend-api-design`: 增加两类分析的创建、latest、运行、Finding、确认和制品 API，并统一分页、过滤、排序和权限约束。
- `backend-database-design`: 增加分析运行、逐条 Finding、业务关联、查询索引和迁移输入 reference 的持久化要求。
- `backend-infrastructure`: 将两套分析工具、Python 隔离环境和 LLVM 21 worker 安装到 backend-worker 镜像，并增加版本和健康检查配置。
- `node-local-migration-input-confirmation`: 两类 Finding 在各自节点内按照风险等级进入候选/确认状态，并支持人工加入或撤回。
- `migration-input-refresh`: 当前源码版本下重跑同类分析时刷新该来源的当前候选，同时保留历史运行和历史报告快照。
- `migration-report-runtime`: 将确认后的浮点和内存序 Finding 纳入模块/文件/问题组织、风险摘要和测试建议。
- `project-archive-runtime`: 将两类分析的 JSON、HTML 与安全摘要作为当前源码版本的可插拔归档候选。
- `api-e2e-test-suite`: 增加真实工具、真实 BC、正常/异常/edge case、权限、分页和清理验证。

## Impact

- 影响后端数据库迁移与 jOOQ 元数据、任务类型/Handler、工作流阶段、overview/readiness/latest、迁移输入、报告、归档、对象存储、SSE 和 API DTO/Controller。
- 影响 backend-worker 镜像构建：需要安装浮点扫描 Python 包、memory-order Python 模块、`fp-ir-worker`、`moa-worker`、`memory-order-source-worker` 及 LLVM/Clang 21 运行库，并固定工具版本。
- 依赖现有 `SharedLlvmBitcodeArtifactSet@2.0`、当前源码工作副本、成功的 source/x86 构建和同源码版本的 `compile_commands.json`；不会改变 x86 构建成败语义。
- 不修改前端，不引入独立扫描容器，不开放工具内部阶段 API，也不兼容旧扫描结果 schema。
- 单元测试必须覆盖正常、异常和边界路径，mock 数据库、对象存储与外部进程边界；项目整体及受影响模块行覆盖率和可用分支覆盖率均须至少达到 90%。
