# 实施记录

## 最终状态

实现和测试已完成，最终证据及限制以 `verification.md` 为准。以下内容保留增量实施过程，不应把历史“尚未完成”段落当作当前状态。

## 2026-10-13 增量实现历史

- 已接入全部 19 种生产任务的业务发布入口；其中 ENV_RUN_SCRIPT 只有 tool_runs，无独立分析运行表。
- 新补齐源码同步、历史 SBOM、依赖自动修复、自动化测试、测试比较、报告及文件上下文、报告比较、复检和归档。文件/SSH/模型/对象上传不放入 Task 发布事务。
- 报告状态写入加入调用方短事务，取消 REQUIRES_NEW；报告成功与可降级的归档登记分别执行受保护事务，保留原来的归档失败不破坏报告语义。
- 正常重试保持同一 Task/domain run，由有效新句柄进入下一次执行；失败尝试的旧句柄不能重新发布。SOURCE_GIT_SYNC 使用不同临时目录，避免旧尝试删除新尝试目录；已移动的版本目录在提交结果未知时保留，不冒险删除有效源码。
- 资源检查点验证当前尝试；拒绝登记时取消刚创建的本地进程/资源。注册表按精确 handle 条件删除，防止旧 finally 删除别的尝试。
- 第一轮增量全量测试 1759 项（0 失败、0 错误、2 个既有外部测试跳过），JaCoCo 门禁通过。后续新改动仍在重新验证，不能把该结果当最终验收。
- 已增加独立 `TaskAttemptDatabaseIT`，通过环境开关显式运行，使用 Liquibase 初始化的隔离 PostgreSQL；不属于默认无外部服务的单元测试套件。实际结果待记录。

### 任务重试边界

所有任务沿用 TaskRetryPolicy：当前尝试的可重试错误在上限内将 Task 转为 QUEUED，旧句柄结束，新 claim 生成新 ID。领域 markRunning/create 保持原有重试行为，只有通过 publish 的当前尝试可调用。自动修复 item 的已完成状态保持，后续仅处理 pending items；部署按原有复用规则。WORKER_LOST 不自动重新入队，用户重跑创建新 Task。

以下旧进度段是增量验证历史，不表示当前仍未实现对应入口；最终数据库、分进程 E2E 和覆盖率验收仍须完成。

## 已核实的基线

2026-10-13 对本机 PostgreSQL 执行只读查询，发现 3 条 `DEPENDENCY_ANALYSIS` 的 Task 为 `FAILED`、关联 `dependency_analysis_runs` 为 `RUNNING`。未修改这些业务数据，截图中的远端实例也未作为本地验证结果使用。

## 收尾映射

所有映射按真实 `task_id` 更新，不按项目 latest 更新。收尾只处理 `PENDING/QUEUED/RUNNING`；保留成功、部分成功、失败等已有终态，以及已有 findings、制品和摘要。嵌套部署与环境采集可能复用父任务 ID，因此还需检查同一 taskId 下的其他显式登记表。

| 任务类型 | 领域记录 | 发布入口 |
|---|---|---|
| SOURCE_GIT_SYNC | source_imports | SourceFetchRuntimeService |
| SOURCE_DEPLOY | source_deploy_runs | SourceDeployHandler 及部署服务 |
| ENV_TEST_CONNECTION / ENV_COLLECT | environment_snapshots | SshRuntimeService |
| ENV_RUN_SCRIPT | 无独立领域表，仅 tool_runs | SshRuntimeService |
| SBOM_ANALYSIS（已弃用） | sbom_runs | SbomAnalysisRuntimeService |
| DEPENDENCY_ANALYSIS | dependency_analysis_runs | DependencyAnalysisHandler |
| DEPENDENCY_AUTO_FIX | dependency_auto_fix_runs / items | DependencyAutoFixHandler |
| KB_SCAN | kb_scan_runs | KbScanRuntimeService |
| KB_AI_EXTENSION | kb_ai_extension_runs | KbAiExtensionHandler 及服务 |
| FLOATING_POINT_ANALYSIS / MEMORY_ORDER_ANALYSIS | specialized_analysis_runs | SpecializedAnalysisRuntimeService 及导入服务 |
| BUILD_VALIDATION | build_runs | BuildValidationHandler |
| AUTOMATED_TEST | test_runs | AutomatedTestHandler |
| TEST_LOG_COMPARE | test_comparison_runs | TestComparisonHandler |
| REPORT_GENERATE | reports | ReportRuntimeService / 状态写入服务 |
| REPORT_COMPARE | report_comparison_runs | ReportComparisonRuntimeService |
| RECHECK_DIFF | recheck_runs | RecheckDiffRuntimeService |
| ARCHIVE_PROJECT | archives | ProjectArchiveHandler |

所有类型额外收尾同 taskId 的 `tool_runs`。自动修复 item 没有 `TIMEOUT` 状态，Task 超时映射为 item 的 `FAILED`，Task/run 仍保留 `TIMEOUT`。

## 当前实现边界

- 已加入失联清理事务内的领域收尾，以及独立于 Worker 保留期的有界历史对账。
- 对账沿用 cleanup 开关、周期和批量大小，只在 API/combined 节点运行；逐项事务，异常项不阻塞后面的 UUID 游标。
- 成功 Task 对应非终态记录只输出审计告警，不自动制造成功结果。
- 摘要合并安全错误码、原因和结束时间，不复制可能包含凭据或宿主路径的原始异常。
- 当前加入了 Task 和 runtime handle 的终态条件保护；**这不等价于完整执行尝试隔离**。

## 尚未完成，不能作为验收结论

- 原子认领及当前句柄校验已接入；仍需实际数据库竞争验证。
- 所有领域发布短事务接入同一尝试校验，包括结果、迁移输入、归档候选、制品登记与后继任务。
- 日志追加与最终游标隔离、旧尝试资源登记拒绝后的资源清理。
- 无原生 finished_at 字段的源码导入等记录，结束元数据的统一表达。
- 独立单测及整体/受影响模块 90% 行和分支覆盖率验收。
- 容器数据库竞争测试、隔离 fixture 的 API/Worker/SSE 验证及运维说明。

上线前必须排空旧 Worker，不能混合运行仍能绕过新检查的旧代码。数据库收尾不代表远端进程已经停止，不能声称远程副作用被回滚。

## 定向验证

2026-10-13 在 Linux Docker 的 `rvport-backend-quality:local` 中执行：

```sh
mvn -B -o -Dtest=TaskDomainFinalizationTests,WorkerCleanupItemServiceTests,TaskRepositoryTests,TaskRuntimeHandleRepositoryTests,TaskWorkerServiceTests test
```

39 个测试通过，0 失败、0 错误、0 跳过。测试使用模拟数据库/服务返回，不连接外部服务。报告位于 `backend/target/surefire-reports/`。此前已执行一次 `clean`，消除编译过程中修改源码导致的陈旧 class。

这只是定向验证，不代表完整覆盖率或端到端验收。`openspec validate fix-worker-lost-domain-run-finalization --strict` 与 `git diff --check` 已通过。

## 当前增量全量验证

2026-10-13 完整验证通过。测试容器需挂载整个工作区，并为用例要求的 `python` 提供指向镜像内 `python3` 的临时软链接；该链接只在临时容器中创建，不修改宿主机或业务镜像。

```powershell
docker run --rm --name rvport-worker-finalization-unit -v D:/projects/RvPort:/workspace -v "rvport-maven-cache:/root/.m2" -w /workspace/backend rvport-backend-quality:local -c "ln -s /usr/bin/python3 /usr/local/bin/python && exec mvn -B -o verify"
```

- 测试总数 1739，失败 0，错误 0，跳过 2。
- 跳过项为原有 `LiquibaseMigrationTests.migratesEmptyDatabaseAndSeedsDefaultAdmin` 和 `RealAdapterEnvironmentInfoSmokeTest.collectEnvironmentInfoWithRealAdapter`；本轮不启用外部环境测试，也不将其计作事务/E2E 验证。
- 全部后端自有编译类（含未加载类，852 个类）参与 JaCoCo；仅沿用生成的 jOOQ 代码排除，未新增业务代码排除。
- 整体：行 24571/25394（96.76%），分支 9189/10096（91.02%）。
- task 包：行 1977/2056（96.16%），分支 667/738（90.38%）。
- worker 包：行 934/969（96.39%），分支 280/310（90.32%）。
- 报告：`backend/target/site/jacoco/index.html`、`jacoco.xml`、`backend/target/surefire-reports/`。
- 执行日志：`backend/target/worker-finalization-verify.log`。

这是当前增量的质量基线。尚未完成的执行尝试隔离、领域发布事务和 E2E 不能据此标记完成；后续代码完成后必须重新运行全量门禁。当前未部署容器、未执行真实业务记录修复、未 commit/push。

## 执行尝试与发布保护增量

- `TaskAttemptService` 在同一事务内认领 Task 并插入活动句柄。复用现有活动句柄部分唯一索引，不新增 schema。认领先锁 Worker，发布先锁 Task，清理按 Worker、Task、句柄顺序加锁。
- 历史运行中 Task 如果没有活动句柄，不接受新代码的成功发布；其 Task 终态收敛仍由现有任务生命周期负责，本次历史对账不会凭空将运行中 Task 判失败。
- 进度、日志及 Worker 的成功、失败、重试迁移校验精确句柄 ID。重试异常在数据库事务提交之后抛出，避免回滚 QUEUED 状态。
- 依赖分析、SSH 环境采集、浮点/内存序专项分析、KB 扫描、KB AI 扩展、源码部署、构建验证及 BC 制品登记已接入短事务发布入口；其他领域入口仍待逐一接入，不能认为整体迟到写保护已经完成。
- 新增受保护制品写入重载，上传在 Task 锁之外，数据库登记在锁之内；提交后清理旧对象，明确回滚后清理新对象，结果未知时保留对象供排查。清理失败只记录异常类型，不覆盖原始错误。
- 本轮第一组定向测试：74 项通过，0 失败/错误/跳过；后续 SSH 与专项分析改动加入后正在重新执行全量门禁，旧覆盖率不能当作当前最终结果。

### 后续接入清单

- `SourceFetchRuntimeService`：源码版本创建、当前版本提升与导入状态，注意文件系统动作不能被 Task 长事务包住。
- `SbomAnalysisRuntimeService`：虽已弃用，仍需保护现有入口；其子 context 已传递发布校验。
- `DependencyAutoFixHandler`：安装结果、自动修复 item 与后继分析任务。
- `AutomatedTestHandler` / `TestComparisonHandler`：测试结果、报告制品、自动触发比较。
- `ReportRuntimeService` / `ReportComparisonRuntimeService` / `RecheckDiffRuntimeService`：报告、差异与当前引用；原有整段事务需要检查，避免外部处理持有 Task 锁。
- `ProjectArchiveHandler`：归档包上传与快照发布。
- `DefaultTaskExecutionContext` 的资源登记和旧尝试本地资源停止、注册表条件删除仍需补齐；目前进度和日志写入已经受保护。

本轮中间全量验证为 1751 项、0 失败、0 错误、2 个原有外部测试跳过；整体行 96.69%、分支 91.02%。构建/部署/BC 增量之后已再次执行验证，最终以最新日志为准。

### 本轮最终增量验证

2026-10-13 Linux Docker 中再次运行上文的 `mvn -B -o verify`，返回码 0：1754 个测试，0 失败、0 错误、2 个原有外部用例跳过。

统计全部 858 个后端自有编译类，包含未加载源码；仅排除自动生成的 jOOQ。整体行 24743/25591（96.69%），分支 9232/10142（91.03%）。受影响包的行/分支百分比如下：

| 包 | 行 | 分支 |
|---|---:|---:|
| worker | 96.41% | 90.29% |
| task | 96.16% | 90.38% |
| dependency | 96.01% | 90.44% |
| analysis | 96.09% | 90.42% |
| artifact | 93.53% | 93.14% |
| environment/runtime | 91.71% | 90.23% |
| kb/runtime | 96.30% | 90.78% |
| kb/ai | 97.40% | 90.40% |
| source/deploy | 96.37% | 90.26% |
| buildvalidation | 96.71% | 90.39% |
| buildvalidation/bitcode | 96.12% | 90.59% |

报告路径仍为 `backend/target/site/jacoco/index.html` 与 `backend/target/surefire-reports/`，执行日志为 `backend/target/worker-finalization-verify.log`。严格 OpenSpec 校验及 `git diff --check` 通过。该结果只验收本轮增量；任务 5.2 留待所有未完成实现接入后的最终重跑，数据库竞争测试与分离部署 E2E 仍未执行。本轮没有修改现存业务数据、重建运行中服务、commit 或 push。
