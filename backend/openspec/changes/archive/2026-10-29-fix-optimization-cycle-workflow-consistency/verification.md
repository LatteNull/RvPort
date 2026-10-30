# 实施验证记录

日期：2026-10-29。范围：backend；前端代码未修改。实现、单元测试、覆盖率与完整运行验收均已完成。

## 已完成的后端验证

所有编译、测试、覆盖率统计及数据库验证均在 Docker 执行。源码与镜像标识、完整日志和报告位于根目录 `.migration-reports/fix-optimization-cycle-workflow-consistency/`，不提交私有运行资料。

| 验证 | 命令入口与结果 |
|---|---|
| 当前源码测试镜像 | 根目录 `docker build --target unit-test -t rvport-optimization-unit:local -f backend/Dockerfile .`，退出码 0 |
| 定向回归 | 容器内 `mvn -B -s /opt/maven-cache/settings.xml -Dmaven.repo.local=/opt/maven-cache/repository -Dtest=Optimization*Tests,ProjectWorkflowStatusServiceTests,StageReadinessServiceTests test`，100 项通过 |
| 完整 Java | `docker run --name rvport-opt-unit-final --memory=6g --cpus=2 -e MAVEN_OPTS=-Xmx1536m rvport-optimization-unit:local`；镜像执行完整 `clean verify`，退出码 0；1823 项，1821 通过、0 失败、0 错误、2 跳过 |
| 独立 PostgreSQL | `OptimizationEvidenceDatabaseIT` 显式执行，1 项通过，退出码 0；仅连接 `rvport-opt-query-db` 专用容器，在随机 schema 中建表、验证并清理 |
| 资源 Python | 容器内 `python3 -m coverage run --branch --source=src/main/resources/analysis,src/main/resources/bitcode -m pytest src/test/python`，49 项通过；整体及每个脚本的独立行/分支检查退出码 0 |

2 项跳过为既有需显式数据库环境的 `migratesEmptyDatabaseAndSeedsDefaultAdmin`、`upgradesLegacyRowsEnforcesConstraintsOrdersRunsAndSerializesCreation`；未将其计为已执行。此次新增的数据库验证已单独执行，不以此替代单元测试。

独立数据库验证覆盖真实 SQL 的批次活动优先、startedAt 为空、不完整新批次、旧源码/旧环境/SOURCE_ONLY 隔离、比较两侧精确关联、失败比较遗留 EQUIVALENT、防止回退成功、重建导致下游失效以及两个连接间 REPEATABLE_READ 快照。无 schema 变更、无 jOOQ 生成、无历史数据回填；已有聚合列表仅对唯一当前轮次追加有界验证链查询，其余历史聚合保持原有范围。

早期失败已诊断修复：新构造器的旧测试夹具、不能 mock record 的 Mockito 配置、数据库夹具的 jOOQ API 调用，以及 PowerShell 对未加引号的 Maven `-D` 参数拆分。最终完整日志和报告来自修复后当前源码，不复用失败或历史结果。

## 覆盖率

Java 范围为全部 `backend/src/main/java` 自有代码，包括未加载类，共 831 个 JaCoCo 分析类。保留 BUNDLE、所有 PACKAGE 及既有 CLASS 的行/分支至少 90% 自动门槛。Python 范围为 analysis 和 bitcode 的全部资源脚本，包括未加载源码；每个脚本也单独达标。

| 范围 | 行 covered/total | 行覆盖率 | 分支 covered/total | 分支覆盖率 |
|---|---:|---:|---:|---:|
| Java 整体 | 23974/24738 | 96.912% | 9281/10128 | 91.637% |
| optimization | 452/456 | 99.123% | 164/170 | 96.471% |
| project | 460/471 | 97.665% | 171/185 | 92.432% |
| workflow（关联回归） | 239/239 | 100.000% | 94/104 | 90.385% |
| buildvalidation（复用查询） | 1089/1123 | 96.972% | 442/489 | 90.389% |
| automatedtest（关联回归） | 369/371 | 99.461% | 127/140 | 90.714% |
| testcomparison（关联回归） | 354/369 | 95.935% | 104/111 | 93.694% |
| Python 整体 | 636/655 | 97.099% | 238/253 | 94.071% |
| prepare_specialized_analysis.py | 293/310 | 94.516% | 111/122 | 90.984% |
| produce_bitcode.py | 343/345 | 99.420% | 127/131 | 96.947% |
| 后端 Java + Python 合计 | 24610/25393 | 96.916% | 9519/10381 | 91.696% |

跨语言合计按 covered/total 累加，不平均百分比。没有缩小业务源码分母或新增排除项。生成 jOOQ 类型属于自动生成代码，第三方依赖不属于自有实现，测试代码/夹具/临时验收运行器不属于生产源码；排除依据沿用[覆盖率范围](../../../../../docs/测试与覆盖率范围.md)。本次不声明整个多工具仓库覆盖率，前端覆盖率按现行规则不验收。

报告：`jacoco/index.html`、`jacoco/jacoco.xml`、`jacoco/jacoco.csv`、`surefire-reports/`、`python-coverage.json`、`java-coverage-summary.json`、`backend-combined-coverage.json`，均位于上述本地报告目录。

## 完整运行验收

前端从当前源码构建独立开发镜像，在 CPU=2、内存=6 GiB 容器顺序执行 `pnpm lint && pnpm typecheck && pnpm test && pnpm build`，退出码 0；128 个测试文件、697 项测试全部通过，生产构建通过，前端文件零修改。jsdom 伪元素提示与构建分块大小提示为非阻塞警告，未放宽检查。

从 `D:\projects\RvPort` 根目录执行以下完整命令，均退出码 0：

```powershell
docker compose --env-file .migration-reports/fix-optimization-cycle-workflow-consistency/compose.env -f docker-compose.yml -f .migration-reports/fix-optimization-cycle-workflow-consistency/compose.override.yml --parallel 1 build
docker compose --env-file .migration-reports/fix-optimization-cycle-workflow-consistency/compose.env -f docker-compose.yml -f .migration-reports/fix-optimization-cycle-workflow-consistency/compose.override.yml up -d --wait --wait-timeout 300
```

本次使用 `rvport-opt-consistency` 专用 Compose project、独立网络/卷/端口。构建服务顺序执行，Maven 堆上限 1536 MiB，CMake 并发 2；API/worker 各限制 2 CPU、2 GiB，其他服务分别限制 1 CPU 和 256–768 MiB。API 与 worker 使用同一当前源码镜像，不连接已有部署数据库或真实 SSH。

| 默认服务 | 验收状态 |
|---|---|
| backend | running、healthy |
| backend-worker | running，管理 API 返回 ONLINE、activeTaskCount=0；无独立容器 healthcheck |
| frontend | running、healthy，HTTP 200 |
| postgres / rabbitmq / redis / minio | 全部 running、healthy |

API 验证通过：

- 登录、修改开发初始密码、创建项目、配置两侧环境、上传/激活源码。
- 无轮次时 latest 为 EMPTY；首次上传但未构建时 optimize 为 PENDING/OPTIMIZATION_BUILD_MISSING，latest 为 CURRENT 且验证未完成；summary 不出现成功组合，nextAction 指向 build。
- optimize readiness 的 ACTIVE_SOURCE 为 SATISFIED；优化 overview、latest 和详情的当前验证事实一致。
- 新源码创建第二轮，旧轮次可只读查看且不提供当前归档建议；换环境保留轮次 CURRENT 归属但保持未完成。
- 切回原源码复用原轮次，按当前环境版本重算，轮次数仍为 2。
- 在本次隔离数据库中显式构造“无 active 源码但有历史”后，API latest 为 STALE、当前优化 overview 无轮次、workflow 为 PENDING/ACTIVE_SOURCE_MISSING，历史轮次完整保留。该场景标明数据库夹具，不冒充用户界面操作。
- 未创建构建、测试或 SSH 连接；完整成功链与错误关联等场景由单元测试和独立 PostgreSQL 测试提供证据，未宣称真实 SSH 端到端链路通过。

首次 API 验收使用的临时测试密码超出既有 16 字符限制，服务正确返回 400；修正测试夹具后重跑全部场景通过，业务代码与校验规则未因此改变。

证据：`compose-build.log`、`compose-up.log`、`compose-ps-final.json`、`compose-images.json`、`runtime-final.log`、`api-smoke-2.log`、`api-no-active.log`、`frontend-http.json`。API/worker 最终日志未发现 ERROR 或异常堆栈。

已确认测试卷的 Compose project 标签均为本次专用项目，然后删除本次 Compose 容器/卷、独立数据库与测试容器及专用网络。已有部署仍正常运行，未向其部署本次修改。报告及构建镜像保留，清理记录见 `compose-down.log`、`test-containers-removed.txt`、`test-networks-removed.txt`。

## 部署与交接

接口与历史失效说明见[后端对接说明](../../../../docs/optimization-cycle-workflow-consistency.zh-CN.md)。回滚不丢失历史记录，但会恢复旧版本的错误完成判断。已复核 1132 个 backend 源码/测试/资源文件的 SHA-256 清单，验证后内容未变；Git 改动限定 backend，前端零修改。

已于 2026-10-29 同步主规范并归档；Git 提交与推送尚未执行。本记录与历史归档勾选不能代替后续版本的验收。
