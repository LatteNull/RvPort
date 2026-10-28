# 历史实施记录与当前范围说明

## 范围

2026-10-28 用户明确当前 root 同时是文件修改边界：后续只允许修改 D:/projects/RvPort/tools/memory-order-analyzer/ 内的文件。当前 change 已收紧为工具实现及输出合同，前后端能力和任务已移出。前端事项见 [前端交接说明](frontend-handoff.md)，由前端 root 独立管理。

以下代码测试、后端修改和仓库级 Compose 均为 2026-10-27 已执行的历史记录，不是后续实施授权或当前任务。用户接受本次既有后端修改；不回滚，也不继续修改。旧 31/41 进度已被工具专属清单替代，移出的前端任务没有被标记为完成。本次 artifacts 修订不更改任何运行时代码，不重新执行 Docker 或声称产生新的覆盖率。

## 历史回归映射

| 需求 | 回归入口 | 验证边界 |
|---|---|---|
| R3 的 TU/artifact 反序、重复同值和冲突 | `tests/unit/test_unified_protocol_regressions.py` | 使用实际 request validator，仅隔离进程执行 |
| 显式 P3、多轮次与 thread-entry 共存、缺失和越界引用 | 同上 | P3/P4 实际 validator |
| R2 缺摘要、A5 双空输入 | 同上 | 启动前依赖检查 |
| 原子标准分组隔离和局部失败 | 同上、`test_advanced_atomic_analysis.py` | compiler-default、legacy、C++17/C++20 |
| C++ profile 零/多匹配与配置差异 | `test_unified_protocol_regressions.py` | standard/vendor/target/DataLayout/ABI；未知 vendor 不借用其他 TU 配置 |
| 普通向量/循环负例、原子/线程/wrapper 正例、跨配置隔离 | `tests/unit/test_result_policy.py` | 合成关系、TU/profile 身份、准入审计 |
| 同问题多位置与快照边界 | `test_finding_locations.py`、`test_finding_projection.py` | occurrences、主位置、缺源码与 evidenceChain 身份 |
| 缺 AST 与不适用的区别 | `tests/unit/test_result_policy.py` | 只有完整来源证据才允许跳过 |
| 2.0/3.0、置信度、证据等级、非原子缺口 | `tests/unit/test_finding_projection.py` | 实际 schema/validator，历史对象不变 |
| 5 TU 混合证据分母、四语言组合 | `tests/fixtures/unified-project-analysis/truth-matrix.json`、`tests/integration/test_unified_project_analysis.py`、`test_repaired_unified_results.py` | 真实 worker、2 Scope、AST/IR 混合缺口、冷/热一致 |
| 跨 Scope 未发布文件竞态、诊断预算与缓存 | `tests/unit/test_unified_coordinator.py`、`test_unified_contracts.py` | 读取前过滤临时项，完整诊断审计与截断分母，旧缓存隔离 |
| 真实源码/BC 与快照定位 | `tests/integration/test_finding_source_context.py`、`test_degraded_source_analysis.py` | Docker 中独立编译夹具，不运行被分析程序 |
| 后端类型、诊断去重/截断/历史未知 | `backend/src/test/java/cn/rvport/backend/analysis/MemoryOrderResultPolicyTests.java` | 只读转换，不改原始 detail |
| 导入状态/退出码合同、制品异常路径 | 同目录 `SpecializedAnalysisRuntimeServiceTests.java`、`SpecializedAnalysisRepositoryTests.java` | 真实协议校验、包预算/不安全条目、诊断脱敏 |
| Workflow 执行结束但分析 partial | `backend/src/test/java/cn/rvport/backend/project/ProjectWorkflowStatusServiceTests.java` | 运行/失败/取消/超时与双语完整性元数据 |
| 人工纳入仍是待核实项 | `backend/src/test/java/cn/rvport/backend/report/runtime/ReportDocumentOrganizerTests.java`、`ReportRuntimeServiceTests.java` | 正式风险与待核实输入、JSON/HTML 分开 |
| 历史 CONFIRMED 不升级、默认候选 | `backend/src/test/java/cn/rvport/backend/migration/MigrationInputSourceResolverTests.java` | 保留选择与原始证据、partial 分析局限 |

上表 `backend/` 路径相对仓库根，其余相对工具根。后端行仅用于追溯此前修改；外部页面测试由相应项目管理，不能当作本工具已验证功能。

## 历史接口摘要（非本 change 实施要求）

- `MemoryOrderFindingProjection` 新输出 `schemaVersion=3.0`，顶层报告 `finding_schema_version=3.0`；2.0 仍可读取。它们是结果协议版本，不是软件版本。
- `conclusion.evidenceLevel` 为 `source-only`、`incomplete` 或 `bounded-model`；`confidence` 允许 null，不应转换为 0%、50% 或 100%。源码候选为 info、非阻断、待核实。
- 后端 Finding 的 `findingKind` 区分 `FINDING`、`SOURCE_CANDIDATE`、`INCONCLUSIVE`、`DISCHARGED`。旧 medium/0.5 候选在响应层保守转换，原始值仍在 `detail`。
- summary 提供 `diagnosticCount`、`frontierCount`、`primaryDiagnostic`、`diagnostics`、`diagnosticsTruncated`、`diagnosticsAggregated`、`diagnosticsDownload`。明细包含双语 detail/suggestion、scope 和 references。历史未汇总时 diagnosticCount 为 null，不能显示零。
- Workflow 的内存序 PARTIAL 仍保留已有 DONE 依赖行为，同时提供 `analysisStatus=PARTIAL`、`analysisComplete=false`、`reasonCode=MEMORY_ORDER_PARTIAL` 与双语“部分分析完成”。前端应呈现警告态。
- 证据 steps 数组仍按稳定 ID 存储，显示顺序必须使用 `primaryPath`，其他连接使用 `edges`；断点在 `breaks`，预算在 `budget`。不能按数组顺序作为推理顺序。
- 报告人工纳入只改变输入选择；候选不升级为正式风险。新报告的 `pendingVerification`、`memoryOrderAnalysis` 表达待核实项和分析局限。

## 已执行基线

工具使用 `rvport-moa-repair-dev:llvm21`，镜像 sha256 `41d4f9692b48c56f54a2ef5e9c76dfcb79705f82a75974eb5d05aaf5fafe6d1d`。源码复制到专用 volume 的 `/output/baseline-source` 后执行 quality，未混入后续修改。

- Python：854 tests；行 14322/14680（97.56%），分支 7212/7663（94.11%）。
- C++：118 tests；行 5363/5402（99.28%），分支 4094/4427（92.48%）。
- 整体、语言和逐模块门槛通过。原始统计和排除理由位于仓库非公开 `.migration-reports/repair-memory-order-analysis-results/baseline-tool/`。
- 以上仅为工具修改前基线，不能替代当前源码验收；最终结果见下节。

## 历史验收结果

- `quality-002`：875 项 Python 单元、118 项 C++ 单元、98 项真实 worker 集成测试通过。单元总体行 19859/20256（98.04%）、分支 11402/12185（93.57%），逐语言和逐模块通过。后续补充 profile 边界与并发缓存回归，最终结果另行记录。
- `quality-003/004` 的单元与覆盖门槛通过，但混合 Scope 集成暴露了制品扫描读取另一 Scope 尚未发布文件的竞态，故不能作为最终验收通过证据。索引和缓存统一排除嵌套 `.task-*` 目录及点号开头的 `.tmp` 原子写入暂存项；针对目录、文件、缓存复制增加断言。修复后 35 项定向单元/真实组合测试及 `quality-005` 全量验证通过。
- 工具最终 `quality-005` 退出 0：884 项 Python 单元、118 项 C++ 单元、98 项真实 worker 集成通过。Python 行 14500/14857（97.60%）、分支 7309/7758（94.21%）；C++ 行 5363/5402（99.28%）、分支 4094/4427（92.48%）。整体及逐模块门槛通过，集成未混入单元覆盖。
- 后端 `backend-unit-006`：1736 项测试，0 failure/error，1 项依赖独立数据库的迁移测试未启用；`clean verify` 整体/包门槛通过。Java 行 23723/24509、分支 9016/9900。逐类复核发现 6 个受影响类仍有分支缺口，因此继续补充测试，并在 Maven 保留整体/包规则的同时增加这些类的独立 90% 门槛。
- 后端最终 `backend-unit-008`：1743 项测试，0 failure/error、1 项迁移测试未启用；`clean verify` 成功。整体行 23729/24509（96.82%）、分支 9046/9900（91.37%）；所有包及受影响类双指标门槛通过。镜像 `sha256:8ee028810106666733397d189fd4751f10ff3b8a4f39fa81db12ce4e29b8b0a4`；完整报告在 `.migration-reports/repair-memory-order-analysis-results/backend-008/`。后续工具竞态修复不改变 Java 源码或资源脚本。
- 后端资源 Python：49 tests，通过；整体行 636/655（97.10%），分支 238/253（94.07%）；prepare_specialized_analysis.py 行 94.52%、分支 90.98%，produce_bitcode.py 行 99.42%、分支 96.95%。统计纳入两个资源目录下全部未加载脚本。
- 后端基础镜像依赖下载曾停滞，改为使用本机依赖层，并在测试镜像中删除旧 src/target 后复制当前源码、执行 clean verify；未采用旧编译或测试结果。后续测试已在 network none 中运行。
- 隔离 Compose 使用 `rvport-moa-repair` 的独立卷/网络、专用测试凭据、端口 29180/29181 等及资源上限；未启动或访问已有部署数据库/SSH。配置与真实日志只保存在仓库 `.migration-reports/repair-memory-order-analysis-results/`。

## 历史覆盖率范围与排除项

此前工具、后端 Java、后端资源 Python 加权行覆盖 44228/45423（97.37%），分支 20687/22338（92.61%）。该合计只用于追溯原验收范围，不再作为当前工具 change 的统计口径，也不是整个仓库或前端覆盖率。当前工具独立口径为行 19863/20259（98.05%）、分支 11403/12185（93.58%）。工具递归统计全部自有 Python、C++ 和可执行头；历史 Java 统计全部业务类，资源脚本统计 analysis/bitcode 全部脚本，包括未加载源码。

仅排除第三方实现、测试框架/纯输入夹具、生成 jOOQ、生成协议元数据及经摘要核对的纯声明头；工具完整排除清单位于 `quality-005/coverage-summary.json`。Java 唯一业务源码范围排除为生成的 `cn/rvport/backend/jooq/**`。后端 `WorkflowStageResponse` 没有可执行分支，其分支指标不适用，不能宣称百分比。逐类 covered/total 在 `backend-008/affected-classes.json`。

## 历史实际单元命令

所有命令从 `D:/projects/RvPort/tools/memory-order-analyzer` 执行。容器使用独立 output volume；源码为当前文件的只读挂载/复制。具体 Docker 命令与隔离配置保存在非公开验收目录。

```text
# 工具测试容器内，源码快照 repair-source-005
PYTHONPATH=/output/repair-source-005/python python3 -m memory_order_analyzer.quality --output /output/repair-memory-order-analysis-results-005 --integration
# 当前源码后端测试镜像内
mvn -B -s /opt/maven-cache/settings.xml -Dmaven.repo.local=/opt/maven-cache/repository clean verify
# 后端资源脚本单元入口（容器工作目录 /workspace/backend）
python3 -m coverage run --branch --source=src/main/resources/analysis,src/main/resources/bitcode -m pytest src/test/python
```

所有原始报告导出至仓库 `.migration-reports/repair-memory-order-analysis-results/`：工具 `quality-005/{python,cpp,coverage-summary}.json` 及两种 HTML；Java `backend-008/{jacoco,surefire-reports}`；资源 Python `backend-python-001.json`；加权汇总 `coverage-summary.json`。

后端资源完整门槛脚本 `run-resource-tests.sh` 同步执行 coverage JSON 导出和全量/每脚本的行、分支双 90% 检查，并保留单元测试失败退出码。源码逐文件摘要在 `source-hashes.json`，该清单 SHA-256 为 `f422b3204670bc2be10dd97314cdafc3f47aed72bc84ddb94c1e385d6ed6ceb3`。

## 历史隔离 Compose 与业务验收

仓库完整 Compose 构建成功，后端运行镜像为 `sha256:649c05819d24ddd28ad1132202af730aac86e0e5e1e2c7f6f58044fb14b12277`。第三方依赖的 Docker Hub 拉取曾 TLS 超时，随后 PostgreSQL 镜像层在 Hub/ECR 均停滞；本次数据库改用已验证为空镜像数据目录的 PostgreSQL 18.4 / Alpine 3.24.1 依赖镜像，独立标签 `rvport-moa-repair-postgres:local`，摘要 `sha256:bd1890816ae0b8ad4644f05728570d4be774e1f1490d7232f5084b52ea335183`。此项是测试数据库的 OS 变体，非应用/分析器旧镜像替代；未复用现有数据卷。

首次 up 在拉取阶段失败，未创建服务；补齐依赖后，通过一次完整 `up -d --wait` 成功启动全部 7 个默认服务。6 个有健康检查的服务 healthy；backend-worker running，并实际执行了两轮分析和报告任务。空库 Liquibase 执行 103 个 changeset，之前执行数为 0。API 与 worker 日志未发现 ERROR/异常。生产前端镜像构建和服务健康通过，不代表前端功能与单元验收完成。

PostgreSQL 日志包含空库首次探测 `databasechangeloglock` 尚不存在的记录，随后 Liquibase 建表、取得锁并完成全部迁移；没有持续迁移失败。Alpine 初始化同时报告系统 locale 不可用，这是本次数据库 OS 变体的环境差异，未将其当作默认 Debian 镜像的验证结果。

所有命令保持工具根为 cwd；Compose 使用以下公共参数（env 内只有本次专用测试凭据）：

```powershell
docker compose --parallel 1 --project-directory D:/projects/RvPort --env-file D:/projects/RvPort/.migration-reports/repair-memory-order-analysis-results/compose/repair.env -f D:/projects/RvPort/docker-compose.yml -f D:/projects/RvPort/.migration-reports/repair-memory-order-analysis-results/compose/override.yml build
docker compose --parallel 1 --project-directory D:/projects/RvPort --env-file D:/projects/RvPort/.migration-reports/repair-memory-order-analysis-results/compose/repair.env -f D:/projects/RvPort/docker-compose.yml -f D:/projects/RvPort/.migration-reports/repair-memory-order-analysis-results/compose/override.yml up -d --wait --wait-timeout 240
```

一次性离线验收脚本为非公开 `compose/smoke.py`，仅在独立 Docker 网络运行。通过真实 API 登录、创建项目、上传两份合成 C11 源码；在独立数据库/MinIO 预置合成上游构建与编译数据库，SSH 地址为 `offline.invalid` 且未连接；应用生产分析流程不编译被分析程序。`prepare`、`analyze`、`rerun` 三阶段结果：

- 普通循环不导入为候选；原子源码产生 2 个 SOURCE_CANDIDATE、18 条诊断、0 个正式风险；severity=INFO、confidence=null、evidenceLevel=source-only。
- 任务 SUCCEEDED，领域 PARTIAL；Workflow DONE 同时给出 analysisComplete=false 和双语警告。API 详情的 primaryPath 全部引用真实 steps，AST-only 证据缺口保留。
- 默认纳入状态 CANDIDATE；人工确认一项后，原始 detail/verdict 不变。报告 pendingVerificationCount=1、highRiskIssueCount=0、codeFindingCount=0，保留 PARTIAL 局限与“零正式风险不代表迁移安全”。
- 第二轮分析生成新 Finding 身份，两个输入重新 CANDIDATE；上一轮 JSON、HTML、审计包和已生成报告内容逐字节/摘要不变。

证据位于 `compose/{build.log,up.log,up-002.log,health.json,images.txt,*-result.json,analysis.json,analysis.html,finding.json,overview.json,report.json,report.html}`，各服务日志另存。验收结束停止本次测试服务，保留独立卷与报告，未操作既有部署。

## 阶段交接

工具实施及其代码验证已完成；2026-10-28 的 artifacts 范围修订经内容、链接、边界和 OpenSpec 严格校验后完成。前后端工作已移交到各自 root，不再是本 change 的待办或归档前置条件；外部移交不等于实现完成。

2026-10-28 经用户明确授权，已将四份 delta 中的 17 条新增要求同步至本工具主规格，保留原有要求，并完成 change 及四份主规格的严格校验。22 项范围内任务全部完成，随后归档至 `openspec/changes/archive/2026-10-28-repair-memory-order-analysis-results/`，保留 `.openspec.yaml` 并修正交接文档的相对链接。

本轮只执行规格同步、归档及文档校验，没有重新运行代码测试或生成新的覆盖率结果。唯一 OpenSpec root 与文件修改边界均为 `D:/projects/RvPort/tools/memory-order-analyzer/`。本 change 流程结束，无后续阶段。
