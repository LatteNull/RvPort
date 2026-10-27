# 换行与 Git 快照验收

## 根因与修复范围

2026-10-26，基于 `master` 的 `1f2746db0880cf93e16447b75ce696ae335c7e0f` 实施。Clang 事实文件在 Git 中为 LF、293356 字节，SHA-256 为 `947e2ad0797248f8179f2bc29f4e7e0591bd7a14801ba819c9e56d31926e9a8c`；旧 Windows 工作区为 CRLF、303286 字节，额外 9930 字节恰为 CR 数量。去除这些 CR 后与 Git blob 完全一致，JSON 值也一致。GCC 当前 Git 与工作区均为 350593 字节、`22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191`。

前一变更的验收仅比较工作区和 Docker 输入，错误地把工作区的 Clang 字节描述为已提交快照；此处明确纠正这一结论。Docker COPY 不会修正换行，Windows 默认 `git archive` 也可能进行转换。历史验收记录保留作为当时记录，不能替代本次 Git blob 验证。

增加 KB Scanner `.gitattributes` 的 LF 合同，安全规范 163 个工作区文件；每个规范后的内容均先与 HEAD blob 核对，未修改其 Git 内容。Clang/GCC 事实文件、生成规则内容和历史账本没有 Git 差异。活动 Clang 基线、knowledge manifest 及 scanner manifest 引用哈希同步更新。测试支持模块保留原始字节检查，遇到污染直接报错，不静默规范输入。

根提交技能增加条件式换行审计：区分工作区/index/blob/镜像，核对未修改依赖、受控 archive 和实际候选 tree，避免 PowerShell 文本管道改写字节；发现差异按验证失败停止。更新技能不构成执行提交和推送。

第一次完整回归额外暴露 5 个旧实现的活动摘要仍使用 CRLF/混合换行。对 `compile_commands.py`、`cpp_frontend.py`、`models.py`、`rules.py`、`report.py`，从前版测试容器读取原始文件，证明旧 SHA 匹配，且仅 CRLF→LF 后与当前 Git 字节完全相同；随后仅更新当前合同中的摘要，保留实现代码不变。证据为 `legacy-line-ending-audit.json`。第一次完整入口失败的记录为 `complete-before-legacy-fix.log`，不计作验收通过。

另外用临时 index 分别在 `core.autocrlf=true` 和 `false` 下检出这 5 个文件及两份编译器事实数据，Docker 比较确认 7 个文件均为 LF，两个检出与最终测试镜像逐字节相同。证据为 `checkout-audit.json`，真实 index 和全局配置未修改。

## 报告基线审校

前版活动基线可从提交 `1f2746db0880cf93e16447b75ce696ae335c7e0f` 的 `tests/fixtures/open-source-regression-baseline.json` 追溯。使用前一轮保留的完整产物与当前 LF 产物逐字段比较，共四组 V1/V2 报告和五个兼容矩阵报告。

- 13 份报告只改变 Clang SHA、由其派生的来源 ID，以及四个 V2 scan ID。来源 ID 按 `knowledge_source_id` 复算；scan ID 按 scanner manifest 的知识身份及原 workspace/target 参数复算，新旧值均匹配。
- 将上述已验证的标识映射回旧值后，13 份报告 JSON 完全一致，包括结论、建议、证据和所有其他字段。8 份扫描日志逐字节一致。
- 当前事实来源、六类计数、generatedSet 引用均通过独立核对。历史报告样例、历史账本及旧来源 ID 测试向量保留；增加 LF 来源 ID 向量。

证据位于忽略目录 `D:\projects\RvPort\.migration-reports\kb-lf-20261026\`：`worktree-lf-audit.json`、`baseline-diff.json`、`provenance-audit.log`、`baseline-review/`。活动基线记录了本次审校理由。

## 候选快照与命令

宿主机只编辑文件、操作 Git、调用 Docker 和读取报告。临时 `GIT_INDEX_FILE` 从 HEAD 加入本次作用域，构造候选 tree，结束后恢复环境变量；真实暂存区未改变，未创建提交。命令工作目录为 `D:\projects\RvPort`：

```powershell
. .migration-reports/kb-lf-20261026/prepare-snapshot.ps1
docker run --rm --name rvport-kb-snapshot-audit --memory=1g --cpus=1 --network=none --mount 'type=bind,source=D:/projects/RvPort/.migration-reports/kb-lf-20261026,target=/audit,readonly' --entrypoint python3 rvport-kb-scanner-test:lf /audit/verify_snapshot.py
cmd /d /c 'docker build -t rvport-kb-scanner-test:lf -f tools/kb-scanner/Dockerfile.test --resource memory=4g --resource cpu-quota=200000 --resource cpu-period=100000 - < .migration-reports\kb-lf-20261026\candidate.tar'
docker run --name rvport-kb-lf-final --memory=4g --cpus=2 --network=none rvport-kb-scanner-test:lf
```

脚本用 `git -c core.autocrlf=false archive` 导出 tree；Docker 审计器对每一个导出文件计算 Git blob 摘要（含 blob 头），检查遗漏、多出与不一致。正式测试候选 tree 为 `fc3423fefbb1af7b737985033f5a70a9fff43f0e`，4970 个 blob 全部匹配。测试镜像为 `sha256:9517c5e9f503f22d218d3954e743e8df2f554b5b06bc6fa01829661eb45f7ba0`。后续仅任务勾选和验收文档变动须单独说明，不能把未测试源码算入此结果。

## 单元测试与覆盖率

完整默认入口依次执行 18 个专项及最终组件/合同回归。已完成的专项结果如下，子集有重复用例，不能将数量相加当作独立测试总数。

| 范围 | 测试数 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|---:|
| runner | 24 | 99.41% | 99.50% |
| 全源码隔离单测 | 871 | 98.89% | 96.23% |
| 原失败的知识检测子集 | 103 | 98.63% | 96.08% |
| 原失败的 schema 设计合同 | 13 | 不适用 | 不适用 |
| 新增 `tests/source_baseline.py` | 6 个单测方法 | 100.00% | 100.00% |
| `normalization/cpp.py`（知识检测门槛） | 纳入上述子集 | 93.51% | 93.94% |

全源码统计包括 `kb_scanner`、`scripts`、`tools` 中未加载文件，沿用 `tests/source-chain-test-inventory.json` 的整体及逐模块双 90% 门槛；测试与夹具、非部署历史归档、规则数据及第三方依赖不作为业务源码。新增和既有测试驱动支持模块另有 runner 双 90% 门槛。测试支持模块共 33 条语句、16 个分支，全部覆盖。原生解析和组件回归不替代隔离单测覆盖率。未降低门槛或删除完整性断言。

定向命令为 `docker run --name rvport-kb-lf-runner --memory=4g --cpus=2 --network=none rvport-kb-scanner-test:lf tests/run_container_tests.py --runner-unit`。最终候选镜像的默认入口也重新运行 runner；报告以 `complete-*` 为准。

最终完整入口退出 0：18 个专项全部通过，末尾 267 项组件/合同回归全部通过（249.199 秒），无失败、错误或 OOM。5 个保留实现的 LF 原始摘要断言也通过。

覆盖率报告含 190 个自有源码文件及 16 个专项原始 JSON，导出为 `complete-coverage-reports.tar.gz`，其中 `full-source/` 含 JSON、HTML、摘要和 coverage 原始数据。汇总为 `complete-coverage-summary.json`、`complete-full-source-summary.json`；日志为 `complete-final.log`，容器状态为 `complete-container-state.json`。初次失败日志和诊断报告保留，不能代替最终成功记录。

报告导出使用 Docker 内临时脚本打包 `/tmp/*coverage.json` 和 `/tmp/kb-source-chain-unit`，再执行：

```powershell
docker cp rvport-kb-lf-final:/tmp/kb-lf-final-reports.tar.gz .migration-reports/kb-lf-20261026/complete-coverage-reports.tar.gz
docker cp rvport-kb-lf-final:/tmp/coverage-summary.json .migration-reports/kb-lf-20261026/complete-coverage-summary.json
docker cp rvport-kb-lf-final:/tmp/kb-source-chain-unit/summary.json .migration-reports/kb-lf-20261026/complete-full-source-summary.json
```

## 根 Compose 验收

从经核对的候选 tar 在 Docker 中解包到忽略目录 `snapshot/`，从仓库根执行根 Compose，构建上下文指向该快照。依次构建 frontend、minio、backend，worker 使用同一新后端镜像。独立项目为 `rvport-kb-lf-check`，7 个服务使用独立网络和 5 个数据卷，所有发布端口为 `127.0.0.1:0`；每服务限制 1 CPU，后端 2 GiB，其余 1 GiB。未连接原部署数据或真实 SSH。

实际命令（工作目录 `D:\projects\RvPort`）：

```powershell
$composeArgs = @('compose', '--env-file', '.migration-reports/kb-lf-20261026/compose.env', '--project-directory', '.migration-reports/kb-lf-20261026/snapshot', '-f', '.migration-reports/kb-lf-20261026/snapshot/docker-compose.yml', '-f', '.migration-reports/kb-lf-20261026/compose.override.json')
docker @composeArgs --parallel 1 build frontend
docker @composeArgs --parallel 1 build minio
docker @composeArgs --parallel 1 build --build-arg NODEJS_MIRROR=https://nodejs.org/dist --build-arg NPM_REGISTRY=https://registry.npmjs.org backend
docker @composeArgs up -d --wait --wait-timeout 300
docker exec rvport-kb-lf-check-backend-1 /opt/kb-scanner-venv/bin/python /tmp/compose_smoke.py
docker exec rvport-kb-lf-check-backend-1 /opt/kb-scanner-venv/bin/python /tmp/verify_deployed_sources.py
docker exec -w /app/tools/kb-scanner rvport-kb-lf-check-backend-1 /opt/kb-scanner-venv/bin/python -m kb_scanner scan --input /app/tools/kb-scanner/tests/fixtures/source-evidence-chain --rules /app/tools/kb-scanner/rulesets/riscv-porting --output /tmp/kb-mapping-smoke --schema-version 2.0
docker exec rvport-kb-lf-check-backend-1 /opt/specialized-analysis-venv/bin/python /tmp/verify_deployed_scan.py
docker @composeArgs down --volumes
```

`compose-verify.ps1` 在调用验收脚本前通过 `docker cp` 将报告目录中的对应脚本和 `candidate-tree-files.txt` 复制到新后端容器的 `/tmp/`；不补复制业务源码。临时环境值和密钥仅在忽略目录。构建成功后，每轮均以一次 `up -d --wait` 启动全部默认服务，未拆分启动。

最终结果：

- 六个配置 healthcheck 的服务均 healthy；worker 无独立 healthcheck，额外等待其 `Started RvPortBackendApplication` 和 RabbitMQ `Created new connection` 日志后才执行验收。七个服务均运行、重启次数为 0、无 OOM。
- 前端首页、CSRF、登录与首次改密、项目创建/详情/列表/概览全部通过。
- 后端真实 KB 扫描退出 0，生成 JSON、HTML、log；V2 Schema 校验通过，`_mm256_setzero_si256` 完整证据链包含 Makefile、main.cpp、wrapper.h。
- 镜像中全部 KB 生产源码目录、知识数据及 4 项关键测试/属性输入共 232 个文件与候选 Git blob 完全一致。
- 首次建库日志中的 `databasechangeloglock` 不存在为初始化探测，随后 Liquibase 完成 103 项迁移并释放锁；数据库查询实测记录数 103、locked=false。其余 Java 原生访问等警告未导致启动失败，没有持续应用异常。
- 导出日志和扫描产物后清理本次全部 Compose 容器、独立网络和数据卷。已有 `rvport-migration-*` 和 `daily-intel` 继续运行，未对它们执行重启或清理。

第一次后端构建在 zstd-jni 下载近五分钟无进展时主动中止；下载地址 HEAD 返回 200，重试同一构建后成功下载并输出 Maven `BUILD SUCCESS`。Dockerfile 使用 `mvn -B -DskipTests package`，编译了 780 个生产源码和 273 个测试源码，但这不代表本轮执行了 Java 单元测试。最终成功日志为 `compose-build-backend-retry.log`，原停滞日志为 `compose-build-backend-stalled.log`。

第一轮启动检查返回时 worker 尚在初始化，因此未把它当作完整应用就绪证据。随后完善临时验收脚本，在同一组镜像、全新独立卷上重新完整启动，等待 worker 应用及 RabbitMQ 连接就绪，再重新执行业务与扫描检查。第一轮记录保留为 `initial-compose-*`，最终记录不带该前缀。

最终镜像：后端 `sha256:8d2c2bffd84ccd0a95fe5b01e7abd244c11be3298c1a3aed38ae8b3e5341e632`；前端 `sha256:45252565e1cc475b4861bc4d9a90b610d0267bf9fa25c30276ba7b010b35ab8d`；MinIO `sha256:4a06cf0c4455f592148596b0b42f6ea1f6843c50376a7c4818d4fa79428b376b`。

报告：`compose-isolation.json`、`compose-build-*.log`、`compose-up.log`、`compose-worker-readiness.log`、`compose-smoke.log`、`compose-source-verification.log`、`compose-kb-verification.log`、`compose-kb-output/`、`compose-database-check.log`、`compose-verified-state.log`、`compose-services.log`、`compose-image-ids.txt`、`compose-down.log`。

## 技能与 OpenSpec 交付

提交技能在 Docker 内运行 skill-creator 的 `quick_validate.py /skill`，输出 `Skill is valid!`；仅文档改动，不虚构代码覆盖率。内容审校确认已有双语提交格式、授权和失败停止规则保持不变。

在 `D:\projects\RvPort\tools\kb-scanner` 执行 `openspec validate fix-git-snapshot-line-endings --strict` 通过，Git 差异通过 `git diff --check`。验证后的任务勾选与验收文档变动不影响已测试源码；最终候选差异复核单独保存在报告目录。

proposal 和 apply 于 2026-10-26 完成。2026-10-27 根据用户授权同步主规范：新增 `kb-scanner-portable-source-baselines` 的 3 项要求和 6 个场景；更新 `kb-scanner-unit-suite-mappings` 的完整验收要求并新增导出换行场景，保留其余要求和场景。

以下终端命令在 `D:\projects\RvPort\tools\kb-scanner` 执行并通过：

```powershell
openspec validate fix-git-snapshot-line-endings --strict
openspec validate kb-scanner-portable-source-baselines --type spec --strict
openspec validate kb-scanner-unit-suite-mappings --type spec --strict
```

本阶段只同步规范和维护流程记录，没有修改可执行源码；执行内容与格式校验，不重复运行上一阶段的 Docker 单测、覆盖率及 Compose 验收，也不声称这些测试于本阶段重新执行。未 commit/push。

## 归档

2026-10-27 核对全部产物完成、10/10 项任务完成、两份 delta 与主规范内容一致后，在 KB Scanner 独立根执行：

```powershell
Set-Location D:\projects\RvPort\tools\kb-scanner
openspec archive fix-git-snapshot-line-endings --yes --skip-specs
```

命令成功，归档位置为 `openspec/changes/archive/2026-10-27-fix-git-snapshot-line-endings/`。`--skip-specs` 仅避免重复应用已经同步且严格校验通过的规范，没有跳过归档验证；`.openspec.yaml` 与全部产物一并保留，活动 change 目录已移除。proposal、apply、sync、archive 流程结束，没有后续 OpenSpec 阶段。未创建 Git 提交或推送。
