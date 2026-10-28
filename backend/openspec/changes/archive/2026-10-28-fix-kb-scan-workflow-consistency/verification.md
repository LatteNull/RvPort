# 实施与验收记录

工作目录：`D:\projects\RvPort\backend`，独立 backend OpenSpec 根。Docker 命令从 `D:\projects\RvPort` 执行。

## 范围与回归矩阵

本次修改 KB 输入/视图/repository、上下文解析器、创建及 worker、workflow readiness、project overview、迁移输入解析，并新增 0128 数据迁移及其 jOOQ 生成结果。未修改扫描器实现。工作区既有内存序、浮点等其他变更保留。

| 设计场景 | 验证证据 |
| --- | --- |
| 无成功构建，创建前拒绝且无副作用 | `KbScanServiceTests.rejectsScanWithoutCurrentSuccessfulBuildBeforeAnyCreationSideEffects` |
| 缺源码/环境/构建、全部构建状态、BOTH 和归属错误 | `KbScanContextServiceTests` |
| 活动优先、最近终态、ID 并列排序、不回退旧成功 | `KbScanRepositoryTests`、`KbScanDatabaseTests` 的真实 SQL |
| 创建和上游变更共享锁，写入失败回滚 task/event/scan，提交后才分发 | `KbScanDatabaseTests`，使用真实 TaskService、TaskEventService、repository 和 Spring 事务代理 |
| 旧空上下文、不一致任务载荷、绑定源码继续执行 | `KbScanContextServiceTests.executionUsesPinnedSourceAndRejectsOldPayloadOrChangedContext` |
| worker 前置失败不运行 scanner、不导入或标成功 | `KbScanRuntimeServiceTests.scanRejectsMissingOrStaleBuildBeforeLaunchingScanner` |
| 绑定构建的 USED/NOT_AVAILABLE/FALLBACK、归属和内容异常、脱敏 | `KbCompileDatabaseTests`、`KbScanRuntimeServiceTests` |
| 运行中上下文变化、零 finding、取消、超时 | `KbScanRuntimeServiceTests` |
| CURRENT/STALE/EMPTY、无 active source 的历史、当前失败不回退 | `KbScanLatestServiceTests` |
| overview 状态矩阵及先推荐 x86 | `ProjectWorkflowStatusServiceTests` |
| 报告 KB readiness、新输入过滤历史 confirmed、保留历史记录 | `StageReadinessServiceTests`、`MigrationInputServiceTests`、`MigrationInputSourceResolverTests` |
| DTO 中英文、安全字段和访问控制 | `KbScanLatestServiceTests`、`KbScanServiceTests` |
| 单次 latest 响应不混合并发上下文 | `KbScanDatabaseTests`，读取期间由另一连接修改运行环境，当前响应保持旧快照，下一请求为 STALE |

## 已取得的基线及迁移证据

- 基线 Java：1743 项，失败 0，错误 0，跳过 1 个需显式测试数据库的迁移用例；JaCoCo 整体及包门槛通过，822 个自有类纳入。
- 基线 Python：49 项全部通过。使用 `coverage --branch --source=src/main/resources/analysis,src/main/resources/bitcode`，纳入未加载脚本。
- 数据库：`KbScanDatabaseTests,LiquibaseMigrationTests` 2 项全部通过，退出码 0。包含旧版本 103 个 changeset 升级至 106、重复升级、旧数据保留、部分空/负版本/非法外键拒绝、真实查询排序、并发锁和事务回滚验证。
- jOOQ 在独立 PostgreSQL 18.4 容器完成生成；生成差异共 6 个文件，仅 KB 新字段、索引、外键和反向关系。

数据库测试命令（凭据通过本机忽略目录中的测试 env 文件传入）：

```powershell
docker run --name rvport-kb-consistency-database-final-2 --network rvport-kb-consistency-codegen --memory=4g --cpus=2 --env-file .migration-reports/fix-kb-scan-workflow-consistency/codegen.env -e MAVEN_OPTS=-Xmx1024m -e RVPORT_MIGRATION_TEST_ENABLED=true -e RVPORT_MIGRATION_TEST_JDBC_URL=jdbc:postgresql://rvport-kb-consistency-db:5432/rvport_codegen -e RVPORT_MIGRATION_TEST_USERNAME=rvport_codegen rvport-backend-kb-consistency:verify sh -c 'mvn -B -s /opt/maven-cache/settings.xml -Dmaven.repo.local=/opt/maven-cache/repository -Dtest=KbScanDatabaseTests,LiquibaseMigrationTests test'
```

最终镜像上的成功日志为 `.migration-reports/fix-kb-scan-workflow-consistency/database-final-2.log`，Surefire 已导出到 `database-final-surefire/`，2 项通过、无跳过、退出码 0。先前定向验证记录仍保存在 `database-test-3.log`、`database-surefire/`。数据库网络、容器和随机 schema 均为本次独立创建，不连接已有部署或 SSH。

## 最终单元测试与覆盖率

最终测试镜像：`rvport-backend-kb-consistency:verify`，镜像 ID `sha256:2220fde5760d8be356d1f57aff2f33d2e2f4659eb5ae859222a98bc09fa86c10`。

```powershell
docker build --target unit-test -t rvport-backend-kb-consistency:verify -f backend/Dockerfile .
docker run --name rvport-kb-consistency-unit-accepted --memory=5g --cpus=2 -e MAVEN_OPTS=-Xmx1024m rvport-backend-kb-consistency:verify
```

容器入口执行 `mvn -B -s /opt/maven-cache/settings.xml -Dmaven.repo.local=/opt/maven-cache/repository clean verify`。1783 项，失败 0，错误 0，跳过 2 个显式启用数据库的用例；这两个用例另行在独立数据库运行。退出码 0，JaCoCo 全部门槛通过。日志为 `final-unit-build-3.log`、`final-unit-3.log`，Surefire 位于 `surefire/`，HTML/XML/CSV 位于 `jacoco/`。

| 统计范围 | 行 covered/total | 行覆盖率 | 分支 covered/total | 分支覆盖率 |
| --- | --- | --- | --- | --- |
| Java 整体，825 个类 | 23825/24601 | 96.846% | 9171/10018 | 91.545% |
| kb | 745/759 | 98.155% | 292/311 | 93.891% |
| kb.runtime | 508/523 | 97.132% | 279/298 | 93.624% |
| workflow | 239/239 | 100.000% | 94/104 | 90.385% |
| project | 458/469 | 97.655% | 169/183 | 92.350% |
| migration | 671/676 | 99.260% | 284/308 | 92.208% |
| report（消费者回归范围） | 992/1036 | 95.753% | 371/409 | 90.709% |
| report.runtime（消费者回归范围） | 816/837 | 97.491% | 302/330 | 91.515% |
| Python 整体 | 636/655 | 97.099% | 238/253 | 94.071% |
| prepare_specialized_analysis.py | 293/310 | 94.516% | 111/122 | 90.984% |
| produce_bitcode.py | 343/345 | 99.420% | 127/131 | 96.947% |

Java 覆盖率统计全部自有可执行类，包括未加载类；唯一源码排除为生成的 `cn/rvport/backend/jooq/**`，其对应数据库行为另行验证。第三方 jar 不属于项目源码。未缩小自有业务逻辑统计范围，保留既有 BUNDLE/PACKAGE LINE/BRANCH ≥0.90 及已有更严格的 CLASS 验收规则。

Python 命令：

```powershell
docker run --name rvport-kb-consistency-python --memory=2g --cpus=2 -e PYTHONPATH=/workspace/tools/memory-order-analyzer/python rvport-backend-kb-consistency:verify sh -c 'python3 -m coverage run --branch --source=src/main/resources/analysis,src/main/resources/bitcode -m pytest src/test/python && python3 -m coverage json -o /tmp/backend-python-coverage.json && python3 -m coverage report --fail-under=90'
docker cp rvport-kb-consistency-python:/tmp/backend-python-coverage.json .migration-reports/fix-kb-scan-workflow-consistency/python-coverage.json
docker run --rm --memory=1g --cpus=1 --mount 'type=bind,source=D:\projects\RvPort\.migration-reports\fix-kb-scan-workflow-consistency,target=/reports' rvport-backend-kb-consistency:verify python3 /reports/summarize-coverage.py
```

49 项全部通过，退出码 0。全量资源脚本（包括未加载文件）纳入；除标准库和第三方依赖外无排除项。最后一个容器命令独立检查整体、全部 Java 包及每个 Python 脚本的行/分支均 ≥90%，退出码 0。统计报告为 `coverage-summary.json`、`python-coverage.json`，日志为 `coverage-gate.log`、`python-unit.log`。以上文件均在根目录 `.migration-reports/fix-kb-scan-workflow-consistency/`。

## Compose 与文档验收

从 `D:\projects\RvPort` 根目录执行以下命令，全部退出码为 0：

```powershell
docker compose --env-file .migration-reports/fix-kb-scan-workflow-consistency/compose.env -f docker-compose.yml -f .migration-reports/fix-kb-scan-workflow-consistency/compose.override.yml --parallel 1 build
docker compose --env-file .migration-reports/fix-kb-scan-workflow-consistency/compose.env -f docker-compose.yml -f .migration-reports/fix-kb-scan-workflow-consistency/compose.override.yml up -d --wait --wait-timeout 240
docker cp .migration-reports/fix-kb-scan-workflow-consistency/api-smoke.py rvport-kb-consistency-backend-1:/tmp/kb-api-smoke.py
docker exec rvport-kb-consistency-backend-1 python3 /tmp/kb-api-smoke.py
docker exec rvport-kb-consistency-backend-1 curl -fsS -o /dev/null -w '%{http_code}' http://frontend
```

使用独立项目 `rvport-kb-consistency`、专用网络和项目数据卷，随机测试凭据保存在忽略目录的 env 中。API/worker 各限制 2 CPU、2 GiB、Java heap 1 GiB；数据库、RabbitMQ、MinIO 各 1 CPU、768 MiB，Redis 与前端各 1 CPU、256 MiB。构建并发参数为 1，分析工具的 C++ 编译并发为 2。前端和 MinIO 的当前构建输入命中缓存，后端重新构建，镜像 ID 保存于 `compose-images.txt`；后端最终镜像为 `sha256:dc952d518d4774c42aae459a71295165288b2e4f87e01ccee021ad87c81d7901`。

一次 `up -d --wait` 启动全部默认服务，结果如下：

| 服务 | 结果 |
| --- | --- |
| frontend、backend、postgres、rabbitmq、redis、minio | 全部 running / healthy |
| backend-worker | running；未定义容器 healthcheck，管理 API 确认 ONLINE、活动任务数 0 |
| 前端 HTTP | 容器网络内访问返回 200 |
| 空库初始化 | 106 个 changeset 已应用，Liquibase 锁已释放 |

实际业务流程由容器内临时脚本执行：登录新建隔离数据库的管理员、修改初始密码、创建项目与两个环境记录、设置项目运行环境、上传仅含 `main.c` 的 ZIP。环境使用不可路由的测试名称 `kb-smoke.invalid`，没有发起连通性检查或 SSH。断言结果：

- overview KB 为 `PENDING / KB_SCAN_MISSING`，没有误报 DONE。
- latest 为 `EMPTY`，默认当前列表为空。
- readiness 的 `X86_BUILD` 为 `MISSING / X86_BUILD_MISSING`。
- 创建 KB 扫描返回 `409 PREREQUISITE_NOT_SATISFIED`，details 指明 `stageId=kb` 和 `X86_BUILD_MISSING`。
- 请求前后 overview 的任务和事件游标不变；数据库复核 `tasks=0`、`kb_scan_runs=0`。
- worker 已在线且活动任务为 0，没有执行扫描或真实远端操作。

成功扫描、零 finding、失效历史、排队与执行期间上下文变化由前述单元测试及独立数据库测试覆盖；本次未新增 E2E 或真实 SSH 支持设施。

日志复核：没有后端或 worker 的运行失败。PostgreSQL 空库首次被 Liquibase 探测时记录一次 `databasechangeloglock` 尚不存在，随后初始化成功且锁已释放；另有单机 MinIO、RabbitMQ 默认发现/弃用提示及 Java Netty native access 警告，不影响本次启动和业务断言。原始日志保留，不将其描述为“完全无警告”。

报告均位于根目录 `.migration-reports/fix-kb-scan-workflow-consistency/`：`compose-build.log`、`compose-up.log`、`compose-ps.json`、`compose-services.log`、`compose-images.txt`、`api-smoke.log`、`frontend-http.txt`、`compose-database-state.txt`。临时脚本和 env 不进入公开源码，验收环境无业务数据；复现应创建新的隔离数据卷并重新生成随机测试凭据。

中文接口/运维说明及本记录的新增相对链接已检查，`git diff --check` 通过；在 `D:\projects\RvPort\backend` 执行 `openspec validate fix-kb-scan-workflow-consistency --strict` 通过。本次只实施 backend 独立 OpenSpec change，未归档、提交或推送。

验收后执行同一 env/override 的 `docker compose down`（未加 `-v`）及 `docker stop rvport-kb-consistency-db`，均退出 0。测试服务已停止，专用数据卷、镜像和报告保留；原有部署继续运行。OpenSpec apply 状态为 `all_done`，25/25 项完成，下一阶段为显式执行归档。

## 规范同步与归档

2026-10-28 经用户授权完成 sync 和 archive：将 `backend-api-design`、`backend-database-design`、`kb-scan-runtime` 共 4 项新增及 4 项修改要求合并到 backend 主规范，保留未涉及的原有内容。归档前 change 严格校验通过；主规范执行 `openspec validate --specs --strict --no-interactive`，37 项全部通过。归档至 `backend/openspec/changes/archive/2026-10-28-fix-kb-scan-workflow-consistency/`，移动时逐文件校验 SHA256，包含 `.openspec.yaml` 的全部文件保留；同步更新接口说明中的验收记录链接。

本阶段仅修改规范和文档，不重新运行代码测试或生成新的覆盖率结果；实现验收证据见上文。OpenSpec 流程结束，未提交或推送 Git 变更。
