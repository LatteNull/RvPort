## Context

后端已经在 source/x86 构建完成后生成 `SharedLlvmBitcodeArtifactSet@2.0`，并把 manifest、逐 TU raw BC、scope 和相关 sidecar 作为不可变制品保存到对象存储。该协议区分平台 artifact key 与消费者内部身份，并保存完整计划分母、源码身份、编译上下文、target、ABI、profile、capability 和开放/闭合 scope。

`floating-point-precision-scanner` 当前通过 `fp-precision-scanner scan` 接收版本化 request，读取同源码版本的 `compile_commands.json`、源码和可选共享 BC，输出唯一的结果 schema v2。`memory-order-analyzer` 当前通过 `analyze-project` 接收 `UnifiedMemoryOrderAnalysisRequest v1`，统一编排 ingestion、AST/IR、执行根、线程、同步、对象来源和风险投影，输出 `UnifiedMemoryOrderAnalysisReport v1`、Finding schema 2.0 与审计目录。后端无需也不得调用其内部阶段 CLI。

后端现有 KB 和依赖分析已经形成任务队列、Worker Handler、运行记录、逐条结果、分页查询、节点内迁移输入确认、报告、对象存储和归档模式。本次集成应复用这些基础能力，同时保持两个工具的协议、状态和业务字段差异。所有工具在 `backend-worker` 内以本地子进程运行，不增加扫描容器、Docker socket 或远端 SSH 工具安装。

## Goals / Non-Goals

**Goals:**

- 为浮点精度和强弱内存序提供两个独立的后端节点、任务类型、API 与 latest/readiness 状态。
- 从当前源码版本和成功 source/x86 构建确定性解析源码、compile database 与共享 BC v2，并安全物化到任务私有目录。
- 只调用两个工具公开的统一入口，严格校验版本化请求、结果、退出码和制品边界。
- 将每条 Finding 独立入库，支持分页、过滤、排序、详情、人工确认、报告和归档。
- 支持运行日志、项目 SSE、取消、超时、部分结果、对象存储和历史运行查询。
- 在 Worker 镜像中固定安装工具和 LLVM 21 运行组件，并通过真实 E2E 验证。

**Non-Goals:**

- 不修改前端页面或前端工作流。
- 不修改两个分析器的规则、算法、内部阶段协议或输出 schema。
- 不让 Java 解析或重建 memory-order 内部 P/A/R 阶段。
- 不生成新的 BC，不改变 source/x86 构建成功条件，也不把分析成败反向写为构建失败。
- 不引入独立扫描容器、Docker socket、远端扫描器部署或目标程序执行。
- 不兼容旧的浮点或内存序输出 schema；协议不匹配必须明确失败。

## Decisions

### 1. 两个领域节点共享执行内核但保持独立 API

新增 `FLOATING_POINT_ANALYSIS` 和 `MEMORY_ORDER_ANALYSIS` 两个任务类型，以及 `floating-point-analysis` 和 `memory-order-analysis` 两个 stage。两者共用制品 resolver/materializer、受控进程执行、运行表、Finding 表、对象存储和清理逻辑；各自由 adapter 构造请求、解释状态并投影业务字段。

外部接口保持领域化：

```text
POST /api/projects/{projectId}/floating-point-analyses
GET  /api/projects/{projectId}/floating-point-analyses/latest
GET  /api/projects/{projectId}/floating-point-analyses
GET  /api/projects/{projectId}/floating-point-analyses/{runId}
GET  /api/projects/{projectId}/floating-point-analyses/{runId}/findings
GET  /api/projects/{projectId}/floating-point-findings/{findingId}

POST /api/projects/{projectId}/memory-order-analyses
GET  /api/projects/{projectId}/memory-order-analyses/latest
GET  /api/projects/{projectId}/memory-order-analyses
GET  /api/projects/{projectId}/memory-order-analyses/{runId}
GET  /api/projects/{projectId}/memory-order-analyses/{runId}/findings
GET  /api/projects/{projectId}/memory-order-findings/{findingId}
```

确认/撤回沿用节点迁移输入 API 或提供上述 Finding 下的等价领域路由，最终都操作同一 reference。选择领域 API 而不是公开通用 `/analyzers/{type}`，是因为浮点 validation plan、profile 和 evidence 与内存序 Scope、verdict、evidenceChain、breaks 的含义不同。

### 2. 以不可变输入解析结果作为一次运行的身份

创建任务时重新校验当前项目权限和 readiness，并锁定：

- 当前 `source_revision_id`；
- 成功的 source/x86 `build_run_id`；
- `compile_commands.json` stored artifact；
- `SharedLlvmBitcodeArtifactSet@2.0` stored artifact、artifact set ID 与语义摘要；
- 浮点扫描使用的 source/target profile、build context 与当前环境配置版本；
- 工具版本、请求 schema、结果 schema 和 policy。

运行记录不在执行期间追随新的源码或环境选择。源码更新后旧运行仍可查看，但 latest/currentSourceRevision/staleReasons 必须说明其已过期。浮点运行绑定环境配置版本；内存序统一请求当前不消费目标环境参数，因此不伪造该依赖，只绑定源码、构建和 BC 身份。

### 3. readiness 允许可审计的部分 BC，但要求至少一个可用成员

两类任务都要求当前源码版本存在成功 source/x86 构建、同源码版本的 compile database、合法 v2 manifest 和至少一个校验成功的 produced BC record。`READY` artifact-set 可直接运行；`PARTIAL` 在仍有 produced record 且计划分母/失败项完整时允许运行，但 readiness 返回 warning，结果不得被提升为完整分析。`FAILED`、`NOT_ATTEMPTED`、历史 v1、哈希错误、路径不安全或没有 produced record 时阻止创建任务。

浮点扫描额外要求能够根据当前源/目标运行环境解析受支持的 source/target profile；无法确定架构、ABI 或 profile 时返回明确阻塞原因。memory-order 的开放 scope、AST-only 或局部失败由工具统一报告为 partial/inconclusive，后端不自行补齐或声称安全。

### 4. resolver 与 materializer 不信任数据库路径或归档内容

公共 resolver 通过业务关联查找 stored artifact，不接受客户端传入对象 key、服务器路径或任意构建 ID。materializer 在任务私有目录中流式下载，校验 size/SHA-256，使用安全路径工具拒绝绝对路径、`..`、反斜杠逃逸、链接、设备文件、重复条目、未声明文件和解压预算超限。源码、compile database、manifest 和 BC 必须通过 source identity、compile context 与 record digest 的交叉校验。

任务目录包含只读输入、可写输出、请求文件和取消标记。任务结束后删除物化源码和临时输出；已上传的不可变结果及显式保留的诊断制品不受影响。所有返回与日志必须隐藏宿主路径、对象 key、环境变量值和凭据。

### 5. 浮点 adapter 直接消费结果 schema v2

adapter 根据工具最新 request schema 构造请求，默认启用该 schema 的全部稳定规则，而不是 `factsOnly`。请求使用同源码 revision 的 `compile_commands.json`、项目根、Shared BC manifest 固定 SHA-256、source/target profile、build context、预算和缓存策略。Worker 执行：

```text
fp-precision-scanner validate-request --request request.json
fp-precision-scanner scan --request request.json --output result.json --clang <locked-clang> --ir-worker <locked-worker>
```

只接受 `schemaVersion=2.0` 且通过 bundled JSON Schema 校验的结果。每个 finding 投影 code/category/severity/confidence/status、双语说明/影响/建议/测试建议、主位置、occurrences、validationPlan 和完整原始 Finding。diagnostics、assessments、layer denominators、profile/build-context 指纹和 semantic digest 保存在运行摘要或结果 artifact 中。

退出码映射为：0=成功完整，4=成功但分析状态 `PARTIAL`，2/3/5=任务失败；无论是否存在 Finding，只有协议状态和 schema 一致时才能提交成功结果。

### 6. memory-order adapter 只调用统一 analyze-project

adapter 将平台 v2 records/scopes 确定性转换为工具要求的 `ExternalBitcodeBundleManifest`，保留计划分母、produced/missing/failed、source/compile/input digest、producer、target、DataLayout、ABI、profile、capability 和 scope 边界。平台 artifact key 不得作为分析器内部 ArtifactKey；工具必须自行计算内部身份。

adapter 创建 `UnifiedMemoryOrderAnalysisRequest v1`，使用固定 `policy_id=unified-project-analysis-v1`、`policy_preset=bounded-default-v1`、`scope_selection=all`、`source_assistance=auto`、默认预算、持久 cache namespace 和任务 cancel file，然后只执行：

```text
python -m memory_order_analyzer analyze-project \
  --request request.json --output output/ \
  --artifact-store cache/ --ir-worker moa-worker \
  --source-worker memory-order-source-worker
```

后端校验 `UnifiedMemoryOrderAnalysisReport v1`、Finding schema 2.0、request/bundle/semantic digest 以及引用文件的路径和哈希。正式 `findings` 与 `source_candidates` 都逐条保存，但用 record kind/verdict 区分；`discharged_assessments`、unsupported、frontier、diagnostics、scope execution 和 data 审计文件保存在结果 bundle，不伪装成风险 Finding。

退出码映射为：0=`SUCCEEDED/COMPLETE`，3=`SUCCEEDED/COMPLETE_WITH_RISK`，2=`SUCCEEDED/PARTIAL` 或任务取消后的 `CANCELLED`，1=`FAILED`。后端必须同时核对 report 的 `status/verdict/exit_code`，冲突时按协议错误失败。`no-finding-within-supported-model` 不得展示为全程序安全。

### 7. 使用共享运行表和逐条 Finding 表

新增通用表（最终命名按现有 Liquibase 命名规范）：

```text
specialized_analysis_runs
  id, project_id, task_id, analyzer_type
  source_revision_id, build_run_id, artifact_set_id
  environment_config_version_id nullable
  tool_version, request_schema_version, result_schema_version, policy_id
  status, verdict, exit_code, summary_json
  request_artifact_id, result_json_artifact_id, result_html_artifact_id
  finding_count, candidate_count, diagnostic_count
  started_at, finished_at, created_at

specialized_analysis_findings
  id, run_id, project_id, source_revision_id, analyzer_type
  external_finding_id, finding_kind, finding_code, category
  severity, confidence, result_status
  title, title_en, message, message_en
  suggestion, suggestion_en, test_suggestion, test_suggestion_en
  file_path, start_line, start_column, end_line, end_column
  requires_human_confirmation, semantic_digest, detail_json
  created_at
```

唯一约束至少覆盖 `(run_id, external_finding_id)`，查询索引覆盖 project/run/analyzer/severity/status/path/code/created time。`detail_json` 只保存单条 Finding 的版本化详情，不保存整个扫描结果；大型 request/result/output tree 进入对象存储。运行导入使用事务：先校验完整结果，再写 run summary 和 findings，最后刷新迁移输入并提交终态，避免半导入结果被 latest 或报告读取。

### 8. 迁移输入、报告和归档按来源类型隔离

增加 `FLOATING_POINT_FINDING` 与 `MEMORY_ORDER_FINDING`。浮点使用 finding severity；memory-order 使用 conclusion severity。两者归一化到现有风险枚举：CRITICAL/HIGH/MEDIUM/INFO 默认 CONFIRMED，LOW 默认 CANDIDATE；人工确认要求不改变默认风险政策，但在列表中显式返回。

成功或可查询的 partial 运行完成后，以项目、源码版本和 source type 清空并重建当前输入。失败、取消或结果未通过 schema 校验不得清空旧输入。历史运行、Finding 和 `report_inputs` 快照保持不可变。

迁移报告把两类结果作为代码 Finding，沿用模块→文件→问题类型→行号组织；浮点附带影响、测试建议和 validation plan，内存序附带并发模式、同步缺口、evidence breaks、假设与限制。后端分别生成 JSON 与轻量 HTML 结果，并以 analyzer node type/candidate type 登记当前源码版本的归档候选。

### 9. 任务、事件、latest 与 overview 使用领域状态而非进程退出码

任务创建、排队、开始、进度、日志、成功/失败/取消和项目上下文变化都通过现有 task event 与 Redis 跨进程 SSE 发布。latest 优先返回当前运行中的任务；否则返回当前源码版本最新终态。overview 为两个 stage 返回 current status、run ID、Finding 数量、partial/diagnostic 摘要和 stale 状态。

执行结果中的风险结论不改变任务基础成功语义。特别是 memory-order exit 3 必须发布 `task.succeeded`，而不是进入 RabbitMQ 重试或死信。可预测的 schema/input/toolchain 错误直接失败；暂时性对象存储或基础设施错误按现有任务重试政策处理。

### 10. Worker 镜像固定工具链并隔离 Python 依赖

Docker 多阶段构建两个 C++ worker，运行镜像保留所需 LLVM/Clang 21 动态库。Python 使用固定路径的隔离环境；若两个工具锁定依赖可共存，可使用一个只读 analyzer venv，否则使用两个 venv，但配置对 Java 暴露独立可执行路径。memory-order 当前通过 `PYTHONPATH` 运行时，镜像必须复制固定源码树并设置只读模块路径，不能从宿主目录动态加载。

配置包括 enable、可执行路径、worker 路径、cache 根、workspace 根、最大 wall time、输出/解压预算和并发预算。API 进程不要求安装工具；Worker 启动时执行离线版本/doctor 检查并将不可用状态暴露给 readiness，而不是等任务开始后才报模糊错误。

### 11. 测试边界与真实验收

Java 单元测试 mock JDBC/jOOQ、对象存储和外部进程返回值，覆盖正常、异常和 edge case：权限、readiness、路径逃逸、哈希错误、schema 错误、超时、取消、partial、空 Finding、重复 Finding、退出码冲突、事务回滚、迁移输入刷新、latest 和归档。项目整体与受影响模块行/分支覆盖率至少 90%，未加载源码必须进入统计。

独立 E2E 模块在容器中使用真实 C/C++ fixture 先生成成功 x86 构建、真实 compile database 和 Shared BC v2，再分别调用两类创建 API，等待 Worker 完成，校验 Finding、详情、分页过滤排序、日志、SSE、JSON/HTML、对象存储、迁移输入和归档。异常流程使用损坏 manifest、无 produced BC、工具 schema 不匹配和取消；清理必须删除本次数据库、对象存储、cache 与 runtime 临时数据。

## Risks / Trade-offs

- [两个工具 schema 演进速度不同] → 每次运行固定 tool/request/result schema，adapter 严格校验，版本不兼容时拒绝导入而不是猜测转换。
- [memory-order 输出树和证据链体积较大] → 数据库逐条保存摘要与单 Finding 详情，完整审计树压缩后进入对象存储，并设置文件数量、单文件和总大小预算。
- [PARTIAL 容易被误认为完整结论] → 运行、latest、Finding 和报告都保留 status/verdict/frontier/diagnostic；禁止把零 Finding 翻译为安全。
- [工具 cache 在多 Worker 间不共享] → cache 仅优化性能，不参与正确性；默认允许每个 Worker 本地内容寻址缓存，后续再评估共享 cache。
- [source/target profile 无法从环境可靠解析] → readiness 明确阻塞浮点扫描并返回缺失字段，不使用架构名称猜测 ABI。
- [子进程取消不能立即生效] → memory-order 使用 cancel file 协作停止，通用执行器在宽限期后终止进程树；任何未原子发布的结果不得导入。
- [Finding 默认确认可能放大报告数量] → 沿用全局风险政策和节点内人工撤回，不在 adapter 中增加隐式过滤。

## Migration Plan

1. 增加数据库表、枚举、索引和 jOOQ 元数据，但保持新 stage 禁用。
2. 在 Worker 镜像构建并固定两个工具及 LLVM 21 组件，增加离线版本/doctor 验证。
3. 实现公共 resolver/materializer/process runner 及两类 adapter，用 fixture 验证 schema 和退出码映射。
4. 实现任务、API、latest/readiness/overview/SSE、迁移输入、报告和归档接入。
5. 在测试环境启用功能，运行真实 BC E2E、单元测试和覆盖率门禁，再默认启用。
6. 回滚时禁用两个 task type 和创建 API；数据库与历史 artifacts 保留只读，不删除已生成报告或归档。

## Open Questions

无阻断性开放问题。首版两类分析均默认扫描当前源码版本的全部可用 scope/TU，不向前端暴露工具内部规则、scope、root 或预算参数；后续若有明确产品需求再增加受控高级选项。
