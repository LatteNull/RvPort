## Context

本变更位于 backend 独立 OpenSpec 根，依据 [proposal.md](proposal.md)。现有 `StageReadinessService.analysis()` 校验 active source 与 x86 构建，`KbScanService.create()` 未执行同等校验，`KbScanRuntimeService.resolveCompileCommands()` 在执行时重新寻找成功构建且允许无构建降级。`ProjectWorkflowStatusService.kb()` 和 `KbScanService.latest()` 只按源码版本查询，无法识别环境或构建变化。

已有规范同时允许无编译数据库的源码扫描和要求 x86 构建先成功。本设计保留成功构建后的编译数据库降级能力，收紧无成功构建的执行入口。数据库已经有 `build_runs` 和项目运行环境版本；`build_runs.environment_config_version` 在现有构建链路中记录的是项目运行环境版本，不能误当作单个环境实体的 `configVersion`。

## Goals / Non-Goals

**目标：**

- 创建、worker 准备、readiness、overview、latest 和 KB 当前结果消费者共用构建选择与扫描有效性规则。
- 只有绑定当前有效构建的成功扫描显示完成；运行事实和结果是否仍适用分别表达。
- 用增量迁移保留历史数据，提供可重复运行的 Docker 单元测试和覆盖率验收。

**非目标：**

- 不修改独立 KB Scanner 算法、其他专项扫描的状态规则或前端流程。
- 不重写通用任务框架，不恢复 CI、E2E、真实 SSH 测试支持设施。
- 不自动删除旧扫描，不推测旧记录的执行环境，不重新定义全项目环境版本传播机制。

## Decisions

### 1. 共用显式上下文解析器

新增 KB 领域上下文解析/有效性组件，输入项目和待扫描源码，返回前置条件、选中构建与安全原因码。该组件依赖 repository 与必要的环境摘要，不依赖 `KbScanService`、`StageReadinessService` 或 overview 聚合，避免循环依赖。

构建选择沿用当前 x86 节点：项目、源码、当前源环境、项目运行环境版本、`SOURCE_ONLY` 全部匹配，活动执行优先；没有活动执行时取最近创建的终态，时间相同以 ID 稳定排序。只有选中记录为 `SUCCEEDED` 才满足构建前置条件，不能绕过更新的失败或活动记录去找旧成功构建，`BOTH` 也不能替代。

readiness 使用 active source；显式传入本项目历史源码的创建请求使用该源码执行同一构建选择规则。跨项目访问先执行既有权限和归属校验。缺少源码、源环境或成功构建时复用 `409 PREREQUISITE_NOT_SATISFIED`；权限、资源不存在和非法请求保留既有安全错误。

不采用“只在 overview 增加一个判断”的方案，因为该方案无法防止无前置条件执行，也不能追溯扫描到底用了哪个构建。

### 2. 在创建事务中固定构建身份

新增 nullable 列 `source_environment_id`、`runtime_environment_version`、`build_run_id`，与现有 `project_id`、`source_revision_id` 组成执行上下文。新服务写入时必须完整，旧记录保持空值。运行记录是事实源，任务输入保存同一安全身份以用于审计；worker 必须以运行记录为准并验证两者一致，不能信任客户端提交的构建关联。

创建事务先读取上下文和构建，再校验、创建任务与扫描记录，提交后才投递消息。用条件写入或与构建/运行环境变更共用的事务锁实现提交前重验，避免校验与写入间的上下文漂移；不能仅在不参与上游更新的扫描表上加锁。若检测到变化，回滚全部写入。实施时结合现有 repository 的事务能力选定具体实现并用并发单元测试验证。

数据库增加外键、完整性检查和上下文筛选索引；项目/源码/环境与构建归属仍须业务层验证。jOOQ 只在独立 Docker 数据库迁移后生成。

### 3. worker 使用固定构建，并区分前置失败与证据降级

worker 开始执行前以扫描绑定的源码为查询对象，重新校验绑定构建的归属、成功态以及当前环境/该源码的构建选择是否仍匹配。仅 active source 切换不禁止基于仍可用历史源码执行，但结果只能作为历史；环境版本或该源码所选构建变化则阻止开始。旧队列载荷或运行记录没有完整上下文时受控失败，记录安全原因，不自动补绑。校验失败时不启动 scanner，不导入 findings，不写成功态。

通过校验后，仅读取绑定构建的 compile database：可用时 `USED`；构建成功但未产生数据库时 `NOT_AVAILABLE`；缺失 artifact ID、下载失败、所有权不符或内容不可用时按既有安全降级路径 `FALLBACK`。这些结果都记录固定 `buildRunId`。成功构建是硬前置，compile database 仍是可降级证据。

扫描开始后出现新构建或环境变化，不要求强制杀死已运行进程。运行继续基于固定输入完成，其真实终态保留，但查询时立即按当前上下文判为历史，不能发布成当前完成事实。禁止执行过程中重新选构建。固定源码被移除、构建身份无效等无法安全执行的情况按失败处理。

### 4. 有效性与执行状态分离

当前有效上下文为 `(projectId, activeSourceRevisionId, sourceEnvironmentId, runtimeEnvironmentVersion, selectedSuccessfulSourceOnlyBuildId)`。匹配必须完整，不用源码相同或结束时间接近代替。

| 情况 | readiness 的 X86_BUILD | KB latest | overview 的 KB |
|---|---|---|---|
| 已上传源码，无构建，无扫描 | MISSING | EMPTY | PENDING / KB_SCAN_MISSING |
| 无有效成功构建，但有历史成功扫描 | MISSING、RUNNING 或 FAILED | STALE，保留历史状态 | PENDING / KB_SCAN_STALE |
| 有当前成功构建，无任何扫描 | SATISFIED | EMPTY | PENDING / KB_SCAN_MISSING |
| 当前构建匹配的扫描 PENDING/QUEUED/RUNNING | SATISFIED | CURRENT，返回活动执行 | RUNNING |
| 当前构建匹配的扫描 SUCCEEDED | SATISFIED | CURRENT | DONE / KB_SCAN_READY |
| 当前构建匹配的扫描 FAILED/CANCELLED/TIMEOUT | SATISFIED | CURRENT，返回对应终态 | BLOCKED |
| 扫描来自旧源码、旧环境版本、其他构建或上下文不完整 | 按当前构建事实返回 | 无当前记录时 STALE | 无当前记录时 PENDING / KB_SCAN_STALE |

同一有效上下文内保留“活动执行优先，否则最近终态”的已有规则；新失败扫描不能被更早成功覆盖。找不到当前扫描时，latest 才选最近创建的历史记录，返回 `STALE`；全无记录返回 `EMPTY`。没有 active source 时同样允许历史记录以 `STALE` 返回，禁止 `CURRENT`。

新增有效性原因以安全代码表达，例如 `KB_SCAN_CONTEXT_UNKNOWN`、`KB_SCAN_SOURCE_CHANGED`、`KB_SCAN_ENVIRONMENT_CHANGED`、`KB_SCAN_BUILD_CHANGED`、`KB_SCAN_BUILD_NOT_READY`。latest 外壳保持不变，原因和安全执行上下文放在 KB 结果 DTO 中；需要直接展示的说明使用 `message`、`message_en`。不暴露服务器路径、凭据、完整任务输入或对象存储 key。

失效是查询时计算的适用性，不能把历史 `SUCCEEDED` 改写成失败。重新选择曾使用的源码且其他上下文与同一构建身份仍完全匹配时，可以重新成为当前；运行环境版本递增或创建新的构建身份后不会因参数看起来相同而自动恢复。目标环境变化若递增现有全局运行环境版本，也按版本变化失效；环境名称等不改变版本的展示字段不触发本规则。

单次读取使用一致数据库快照或读取后版本重验，避免同一响应混合多个上下文。不同 HTTP 请求之间允许真实状态变化，不承诺跨请求全局快照。

### 5. 收口结果消费者与推荐顺序

overview、latest、默认 `currentOnly` 列表及 DTO 的当前性标记复用同一解析结果。历史列表/详情仍可读，不改变原运行状态；必要时保留旧字段并新增清晰的当前有效性字段，避免将“源码相同”混淆为“当前有效”。

报告 readiness 的 `KB_SCAN` 前置、当前 KB finding 自动选择以及新报告输入解析必须复用当前有效扫描选择，防止页面显示过期而报告仍自动消费旧结果。历史报告与已归档内容维持快照；不删除用户历史确认记录，生成当前报告时明确忽略或以现有前置错误拒绝过期 KB 来源。实施时逐一检查 `MigrationInputSourceResolver`、`ReportService` 及关联引用选择，避免只修状态入口。

overview 推荐顺序将 x86 构建置于 KB 之前，保持节点 ID 和状态枚举；针对 x86 未成功的情形，不把 KB 当作可立即开始的下一步。其他节点的执行优先规则不在本次重写。

### 6. 单元测试、覆盖率与验证入口

测试矩阵包含：首次上传、环境切换、旧源码、旧版本、旧成功后新构建运行/失败/取消/超时/成功、同一构建下扫描重试、活动执行优先、时间并列、显式历史源码、跨项目拒绝、空历史、缺少上下文、队列等待时漂移、运行中漂移、compile database 各降级分支、数据库写入回滚与无消息副作用、零 finding 成功、报告旧来源隔离及中英文错误字段。

保持 `backend/pom.xml` 已有 JaCoCo BUNDLE 和 PACKAGE 的 LINE/BRANCH 各 0.90 门槛。统计所有 `src/main/java` 自有可执行类，包括未被测试加载的类，仅排除生成的 `cn/rvport/backend/jooq/**`；第三方依赖不在自有代码分母。重点报告 `kb`、`kb.runtime`、`workflow`、`project` 和实际修改的报告/迁移包，不用变更行代替整体。后端资源 Python 按现有 coverage.py 入口单独验收；若声明全仓达标，必须取得各模块当前源码报告并按 covered/total 汇总，不能只凭 Java 结果。

实施阶段从 `D:\projects\RvPort` 执行以下已有入口，镜像从当前源码重建，唯一命名容器及报告目录避免覆盖其他任务：

```powershell
docker build --target unit-test -t rvport-backend-kb-consistency:local -f backend/Dockerfile .
docker run --name rvport-backend-kb-consistency-unit --memory=6g --cpus=2 -e MAVEN_OPTS=-Xmx1536m rvport-backend-kb-consistency:local
docker cp rvport-backend-kb-consistency-unit:/workspace/backend/target/surefire-reports ./.migration-reports/fix-kb-scan-workflow-consistency/unit
docker cp rvport-backend-kb-consistency-unit:/workspace/backend/target/site/jacoco ./.migration-reports/fix-kb-scan-workflow-consistency/jacoco
```

Dockerfile 的 unit-test 默认执行 Maven `clean verify`，使用容器内依赖缓存。先创建本次报告父目录；失败也导出报告及退出码，未生成的报告注明原因。构建按模块顺序执行并限制构建并发和 Docker builder 资源，不能并行拉起所有模块。Python、数据库迁移/jOOQ 的确切命令沿用 [开发指南](../../../../docs/开发指南.md)，使用独立数据库、网络和 volume，不能连接已有部署或真实 SSH。

实施最终还须从仓库根执行完整 Compose build，并以一次 `docker compose up -d --wait` 启动全部默认服务。使用本次专用 `COMPOSE_PROJECT_NAME`、测试 env 文件、空闲端口和必要的本地 override，保证 CPU/内存限制及独立网络/数据卷；记录最终实际完整命令和解析后的服务清单。检查健康、日志与代表性 API 流程。通过现有单元测试替身验证成功构建/扫描路径，Compose 验证首次上传无构建的拒绝与状态一致性；不为本变更新增真实 SSH 或 E2E 基础设施。

## Risks / Trade-offs

- [旧扫描在升级后显示历史] → 明确 `CONTEXT_UNKNOWN` 原因，保留详情和下载，引导基于成功构建重新扫描，不伪造回填。
- [每次新构建都要求重扫，即使产物内容相同] → 使用稳定且可审计的 build ID；内容等价复用留作独立需求。
- [成功构建缺少 compile database 导致结果信息较少] → 保留降级模式和原因；“完成”表达本次允许的扫描执行完成，不表示全部构建证据可用。
- [新增过滤造成查询放大或循环依赖] → 共用底层解析器、一次聚合复用查询结果、索引和 repository 查询单元测试。
- [当前消费者仍引用旧 finding] → 补充报告准入和来源选择测试，保留历史快照而阻止隐式复用。
- [整体覆盖率存在历史缺口] → 如实记录指标、包和未覆盖路径，不降低门槛；需要大规模无关改造时请求扩大范围，验收任务保持未完成。

## Migration Plan

1. 添加可空列、外键/完整性约束和索引；验证空库、旧数据升级和重复迁移。旧行不推测回填。
2. 在独立 Docker 数据库完成 jOOQ 生成，再更新上下文写入、读取和 worker 逻辑。
3. API 与 worker 协同升级；部署前排空旧 KB 队列，遗留任务若仍到达则受控失败，不自动补上下文。
4. 运行单元、覆盖率、迁移和完整 Compose 验收，记录旧数据只读可用及当前流程符合状态矩阵。
5. 回滚时保留新增 nullable 列和历史数据，协调回滚 API/worker；记录旧版本会恢复原有状态不一致风险，不以回滚视为本问题已修复。

## Open Questions

没有阻塞提案的产品决策。实施前需确认数据库事务重验方案及本次隔离 Compose 的空闲端口；这些属于实施配置，实际值记录在验收报告。若现有环境配置版本传播不足以表达其他配置变更，单独记录差距，不在本次暗中扩大到全项目版本机制重构。
