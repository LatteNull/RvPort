# 验收与基线审校

## 范围与原因

验证基于 `master` 的 `dc6a276` 及本 change 工作区修改，日期为 2026-10-26。原知识检测入口只执行固定目录中的 76 个测试，漏载归一化、宏和用途分析相关辅助测试；`normalization/cpp.py` 为 88.31% 行、86.36% 分支。全量发现与独立子门槛采用不同集合，因此本地全量通过不能证明 CI 的独立门槛通过。

共享映射加载器加载 `unit`、`supportingUnits` 并保留已有 discover，按测试 ID 去重，拒绝缺失、越界、空测试和导入错误。各领域只补对应行为的辅助映射；原本使用隔离全量发现的候选、RPM、性能入口继续保留原范围。历史 80% 分支门槛统一为 90%。未修改 `kb_scanner` 业务实现或 `rulesets` 知识数据。

根 `.dockerignore` 原来的 `tools/**/build-*` 还会误排除构建选择清单、夹具和支持文档。增加这些输入的精确例外，并在新镜像中逐文件比对修改文件 SHA-256；最终验收不补复制业务源码。

## 退役 AVX 处理

按用户追加授权删除两个专用外部 AVX 回归文件，移除混合测试、活动兼容矩阵和性能测量中的外部工程路径。通用 V1/V2 投影、原始源码证据链和默认测量改用已跟踪的 `source-evidence-chain`；历史 schema 示例按自包含 reader 合同检查，不再读取旧运行目录。仍保留 x86/AVX 指令检测及仓库内有效用例。

历史 JSON 账本、人工 oracle 及其结构合同保留用于追溯，不再要求退役工程存在。当前兼容矩阵有五个本地样例，包含恶意静态输入和工作区越界；相应断言继续检查无副作用、确定性、结论和证据。

## 当前开源基线

新增 `tests/fixtures/open-source-regression-baseline.json`，旧差异账本不改写。当前知识文件从开源迁移提交 `eb73f68` 追溯，摘要、六类计数和来源元数据与既有 `test_fact_data_contract.py`、知识 manifest 相符。

| 数据 | 历史记录 | 当前已提交快照 | 核对结果 |
|---|---|---|---|
| Clang | 303286 字节，`adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7` | 相同 | 字节和分类计数一致 |
| GCC | 362118 字节，`89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9` | 350593 字节，`22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191` | 六类计数相同；当前来源为 `vendor/gcc/gcc/config/i386`，与当前 manifest 和事实合同一致 |
| CMake README | `b7093780cee4f4a5170a8703cd6b525254ca2edb991a352b17457881eed6530d` | `1d2e0dbf4616b8e89677f26e0fb54c0343a9d9f464e50973edfadc1c82f187e6` | 将 RvPort 名称还原为旧名称后与历史摘要完全匹配；代码夹具未变 |

GCC 旧摘要不能由单纯 LF/CRLF 转换复原，不能声称仅是换行差异。历史产物缺少可重建的完整内容，也不能用摘要推断全部语义相等。四个小样例的 V1/V2 报告及日志重新冻结，仍由独立的 schema、双语建议、未知状态、静态输入、原始源码和证据链断言验收。

五个本地兼容样例与合并历史差异账本比较：`classification-assessment`、`malicious-static-input` 全部签名字段相同；`generated-and-curated-facts`、`build-selection`、`workspace-escape` 仅 `semanticFindingsSha256` 不同，其余摘要、计数、严重性、阻断/可操作数量、退出码、制品和诊断摘要一致。记录差异而不据此宣称历史报告语义完全相等。

## 验证命令与报告

所有 Python 测试、覆盖率及构建在 Docker 中执行。工作目录为仓库根 `D:\projects\RvPort`，测试容器禁网、2 CPU、4 GiB，报告目录 `.migration-reports/kb-unit-mappings-20261026/` 不纳入公开源码。

```powershell
docker build -t rvport-kb-scanner-test:mappings -f tools/kb-scanner/Dockerfile.test --resource memory=4g --resource cpu-quota=200000 --resource cpu-period=100000 .
docker run --name rvport-kb-mappings-complete --memory=4g --cpus=2 --network=none --cap-drop=ALL --security-opt=no-new-privileges rvport-kb-scanner-test:mappings
docker cp rvport-kb-mappings-complete:/tmp/kb-source-chain-unit .migration-reports/kb-unit-mappings-20261026/complete-source-chain-unit
```

完整入口依次执行 18 个子命令及组件/集成/合同回归。全源码统计包含未加载的 `kb_scanner`、`scripts`、`tools` 中 190 个源文件；测试、非部署归档、规则数据和第三方依赖不属于业务源码分母。修改的测试驱动支持代码另设双 90% 门槛；测量脚本也加入全源码门槛的逐模块检查。真实解析器和组件回归不作为隔离单测覆盖率证据。

最终测试镜像：`sha256:6e1f4ea2d87fbbf3da75d3a0e7d0986426d66c3788cc0abbbb05565247f28343`。镜像中的 57 个变更源码、清单、基线和文档文件与工作区 SHA-256 一致，两个退役测试文件不存在。

| 默认入口阶段 | 测试数 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|---:|
| runner | 18 | 99.38% | 99.46% |
| 全源码隔离单测 | 865 | 98.89% | 96.23% |
| RPM 架构 | 852 | 98.74% | 96.65% |
| 候选语义 | 852 | 98.76% | 96.88% |
| 性能 | 852 | 98.20% | 94.78% |
| 候选噪声 | 852 | 97.72% | 93.66% |
| 知识生产 | 11 | 98.28% | 92.31% |
| 知识检测 | 103 | 98.63% | 96.08% |
| 前端 | 112 | 98.67% | 96.13% |
| 原生解析支持 | 6 | 100.00% | 100.00% |
| 证据图 | 55 | 97.57% | 92.62% |
| 构建选择 | 140 | 98.40% | 95.99% |
| 分类评估 | 149 | 97.80% | 94.61% |
| 兼容切换 | 63 | 98.81% | 96.64% |
| 投影可达性 | 126 | 97.54% | 94.06% |
| schema 设计合同 | 13 | 不适用 | 不适用 |
| schema V2 投影 | 130 | 99.07% | 97.22% |
| 架构枚举 | 246 | 97.36% | 93.21% |

上述 18 个阶段均通过，子集之间存在重复用例，不应把测试数相加当作独立测试总数。各专项还逐模块满足双 90%；原失败的 `normalization/cpp.py` 为 93.51% / 93.94%。共享加载器为 93.33% / 100%，容器编排入口为 99.80% / 99.23%；架构家族性能、CMake 审校和证据图测量脚本均为 100% / 100%。

报告：`complete-default.log`、`complete-source-chain-unit/{summary.json,coverage.json,html/}`、`complete-coverage-reports.tar.gz`（16 个专项原始 JSON）、`complete-coverage-summary.json`、`complete-runner-coverage.json`、`complete-knowledge-coverage.json`、`image-source-verification.log`。此前诊断日志包含已修复失败及主动停止的旧源码轮次，以 `complete-*` 报告和最终容器退出码为准。

最终完整回归为 267 项，全部通过（303.828 秒）；完整默认入口退出码为 0，无失败、错误或 OOM。容器状态保存于 `complete-container-state.json`。

## 根 Compose 验收

2026-10-26 已完成当前源码的根 Compose 构建、一次全部默认服务启动及业务检查。为避免 Compose Bake 并行构建多个模块，实际按 `frontend`、`minio`、`backend` 分别执行 Compose build；worker 复用同一个新后端镜像。

独立项目为 `rvport-kb-mappings-check`，新建网络及五个独立数据卷，全部发布端口绑定 `127.0.0.1:0`。后端限制 1 CPU、2 GiB，其余每服务 1 CPU、1 GiB；依赖使用本地 PostgreSQL 18.4、RabbitMQ 4.3.2、Redis 8.8.0 镜像。未连接旧部署的数据库、数据卷或真实 SSH 环境。Node/npm 官方源参数仅用于本次构建，部署配置未修改。含临时密钥的 `compose.env` 与覆盖配置均保存在忽略的报告目录，不纳入源码。

工作目录为仓库根 `D:\projects\RvPort`，实际命令如下（依次执行）：

```powershell
docker compose --env-file .migration-reports/kb-unit-mappings-20261026/compose.env -f docker-compose.yml -f .migration-reports/kb-unit-mappings-20261026/compose.override.json --parallel 1 build frontend
docker compose --env-file .migration-reports/kb-unit-mappings-20261026/compose.env -f docker-compose.yml -f .migration-reports/kb-unit-mappings-20261026/compose.override.json --parallel 1 build minio
docker compose --env-file .migration-reports/kb-unit-mappings-20261026/compose.env -f docker-compose.yml -f .migration-reports/kb-unit-mappings-20261026/compose.override.json --parallel 1 build --build-arg NODEJS_MIRROR=https://nodejs.org/dist --build-arg NPM_REGISTRY=https://registry.npmjs.org backend
docker compose --env-file .migration-reports/kb-unit-mappings-20261026/compose.env -f docker-compose.yml -f .migration-reports/kb-unit-mappings-20261026/compose.override.json up -d --wait --wait-timeout 300
docker cp .migration-reports/kb-unit-mappings-20261026/compose_smoke.py rvport-kb-mappings-check-backend-1:/tmp/compose_smoke.py
docker exec rvport-kb-mappings-check-backend-1 /opt/kb-scanner-venv/bin/python /tmp/compose_smoke.py
docker exec -w /app/tools/kb-scanner rvport-kb-mappings-check-backend-1 /opt/kb-scanner-venv/bin/python -m kb_scanner scan --input /app/tools/kb-scanner/tests/fixtures/source-evidence-chain --rules /app/tools/kb-scanner/rulesets/riscv-porting --output /tmp/kb-mapping-smoke --schema-version 2.0
docker cp .migration-reports/kb-unit-mappings-20261026/verify_deployed_scan.py rvport-kb-mappings-check-backend-1:/tmp/verify_deployed_scan.py
docker exec rvport-kb-mappings-check-backend-1 /opt/specialized-analysis-venv/bin/python /tmp/verify_deployed_scan.py
docker compose --env-file .migration-reports/kb-unit-mappings-20261026/compose.env -f docker-compose.yml -f .migration-reports/kb-unit-mappings-20261026/compose.override.json down --volumes
```

以上构建、启动、业务流程和扫描命令均退出 0。临时脚本只用于隔离环境验收，保存在报告目录；登录脚本要求全新数据卷，验证首次改密后创建项目。验收结果：

- 六个带健康检查的服务全部 healthy；worker 无独立 healthcheck，运行状态、应用启动及 RabbitMQ 连接日志正常。七个服务均无重启、无 OOM。
- 前端首页、CSRF、管理员登录与首次改密、项目创建、详情、列表和概览全部通过。
- 新后端容器中的真实 KB Scanner 扫描退出 0，生成 `scan-result.json`、`scan-report.html`、`scan.log`。V2 JSON Schema 校验通过，`_mm256_setzero_si256` 的完整证据链包含 `Makefile`、`main.cpp`、`wrapper.h`。
- 新部署镜像中 57 个受检文件与完整单测镜像记录的 SHA-256 一致，两个退役专用测试不存在；未用旧镜像或临时复制业务源码替代验收。
- 日志审校发现首次建库探测 `databasechangeloglock` 不存在，随后 Liquibase 成功执行全部 103 个 change set 并释放锁；直接查询确认 103 条记录、锁为 false。其余为 Java 原生访问、RabbitMQ 弃用及单节点初始化等提示，没有持续应用错误。
- 导出报告后删除本次独立 Compose 容器、网络和五个数据卷，保留镜像缓存及报告。

最终镜像：后端 `sha256:a12ace955c71844d95cd6f4835ec5a6b9f8e82db9d9b9ee9e96a16ecf9f7bfcd`；前端 `sha256:d4d57c5edffa830c06e08f2f48ae0a040166c26b1523bbe31599ed7bbaf4e0c4`；MinIO `sha256:20ad508173d49492a61332e3fe9fa8d63651f2987f259de99016b87b29c1e2f2`。

最终证据：`compose-build-{frontend,minio}.log`、`compose-build-retry.log`、`compose-up.log`、`compose-smoke.log`、`compose-kb-verification.log`、`compose-kb-output/`、`compose-source-verification.log`、`compose-services.log`、`compose-database-check.log`、`compose-ps.json`、`compose-verified-state.json`、`compose-image-ids.txt`、`compose-down.log`。

此前的下载及环境中断保留诊断记录，不计作通过：两轮 LLVM 下载触发低速保护；随后单独构建原 Dockerfile 的 `bitcode-toolchain` 缓存（2 CPU、4 GiB，原始包和裁剪包 SHA-256 均通过）及 `specialized-analysis-tools` 缓存（2 CPU、6 GiB）成功。一轮构建遭遇 Docker 连接 EOF，引擎恢复后现有容器运行时长重置，本次没有执行引擎或现有部署的重启命令，未发现容器 OOM 事件，原因未确认；另一轮会话中断，BuildKit 历史确认为 Canceled。最终 `compose-build-retry.log` 为成功构建，旧诊断日志不能替代该结果。

## 规范同步

主规范 `openspec/specs/kb-scanner-unit-suite-mappings/spec.md` 已同步五项要求及十个场景，覆盖映射、错误传播、独立覆盖率、完整入口及自包含回归。以下命令在 `D:\projects\RvPort\tools\kb-scanner` 执行并通过：

```powershell
openspec validate fix-unit-suite-mappings --strict
openspec validate kb-scanner-unit-suite-mappings --type spec --strict
```

代码和文档差异通过 `git diff --check`；新增主规范为纯文档，不另行声称代码覆盖率。

## 归档

14/14 项任务完成后，在 KB Scanner 独立根执行以下命令成功归档。`--skip-specs` 仅避免重复应用已人工同步并严格校验的 delta，没有跳过归档校验。

```powershell
Set-Location D:\projects\RvPort\tools\kb-scanner
openspec archive fix-unit-suite-mappings --yes --skip-specs
```

归档位置为 `openspec/changes/archive/2026-10-26-fix-unit-suite-mappings/`，活动 change 目录已不存在。proposal、apply、sync、archive 流程结束；未创建 Git commit。
