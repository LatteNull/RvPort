# KB Scanner 开发与验证

[English](development.md) | 简体中文

从仓库根目录执行以下命令。源码、规则和被扫描样例只读；依赖、测试与输出留在独立 Docker 环境中。

```powershell
docker compose -f tools/kb-scanner/compose.test.yml build kb-scanner-test
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

`tests/run_container_tests.py` 为容器默认测试入口，依次运行测试驱动逻辑单测、全源码隔离单测门槛、各专项门槛及完整回归；任一步失败均返回非零状态。本地及 CI 应从当前源码重新构建镜像并执行此默认入口。整体与受影响模块行/分支均至少 90%，统计包括未加载的自有代码。测试夹具、第三方和生成数据不计入业务源码；集成、契约和真实解析器回归不替代隔离单测。

专项示例（仍在仓库根目录）：

```powershell
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --graph-unit
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --architecture-candidate-noise-unit
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --runner-unit
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --knowledge-unit
```

以上局部命令用于快速定位，不能代表完整入口通过。全量通过也不能抵消独立子集的失败，子集覆盖率不会跨进程合并。

测试与质量清单位于 `tests/*inventory.json`；当前可执行清单统一要求行/分支至少 90%。模块的 `unit` 是主测试，`supportingUnits` 列出同一模块的跨目录辅助测试；采用该结构的领域入口通过 `tests/unit_mapping.py` 加载并按测试 ID 去重，保留已有目录发现。移动或新增测试时同步更新映射，辅助测试应直接验证对应模块行为。文件缺失、越界、导入失败或空测试模块均使入口失败。原生崩溃清单中标注 `coverageGate` 的模块交由对应入口验证；性能清单保留点分模块名和既有隔离全量发现。

冻结的事实哈希、V1/V2 reader、断点语义、恶意输入无副作用、原生崩溃和确定性回归都应保留。不要自动改写人工 oracle 或历史差异账本来接受新行为。

默认回归仅使用仓库内夹具，已移除退役外部 AVX 工程的专用扫描测试、矩阵条目及性能测量路径。通用 schema、源码上下文与证据链合同继续使用本地样例验证；历史 JSON 账本及其结构合同保留用于追溯，不再要求对应外部源码存在。`scripts/measure_evidence_graph_qualification.py` 默认扫描 `tests/fixtures/source-evidence-chain`，需要自定义时使用 `RVPORT_KB_FIXTURE`。

当前开源快照使用 `tests/fixtures/open-source-regression-baseline.json`，记录代码版本、知识来源、事实分类计数及五个本地矩阵样例。该基线与当前事实合同、知识 manifest 和独立组件断言共同验收。旧账本只保存部分摘要，不能据此断言旧产物与当前产物语义等同；重新建立基线必须核对来源、审查差异并保留历史账本。

## 全源码覆盖

默认入口的 `--source-evidence-chain-unit` 已执行全源码隔离单测门槛。单独复验并保留报告可从仓库根目录执行：

```powershell
docker run --name rvport-kb-coverage --memory=4g --cpus=2 --network=none rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /tmp/kb-coverage
docker cp rvport-kb-coverage:/tmp/kb-coverage .migration-reports/kb-coverage
docker rm rvport-kb-coverage
```

此命令使用前面 Compose 构建的镜像，将报告保存在独立容器的可写层，导出后移除该容器。默认入口报告在 `/tmp/kb-source-chain-unit`（JSON、HTML 和摘要），专项报告在 `/tmp/*coverage.json`，测试驱动报告在 `/tmp/kb-runner-coverage.json`。Compose 默认使用 tmpfs；需要在容器退出后导出报告时使用上述可写容器方式，不挂载真实运行数据。

测试驱动门槛单独覆盖映射加载器、容器编排入口以及本次调整的架构家族性能和 CMake 报告审校工具；通过伪扫描、伪时钟验证正常、失败和性能异常路径，不把真实解析回归充作单元测试。

如需额外执行包含历史组件用例的全量 discover，以下命令在同一开发容器内执行，工作目录为工具根目录；通过 Docker 启动 shell，不在宿主机运行 Python：

```sh
export COVERAGE_FILE=/tmp/kb-all.coverage
python -m coverage run --branch --source=kb_scanner,scripts,tools -m unittest discover -s tests/unit -t .
python -m coverage json -o /tmp/kb-all-coverage.json
```

报告须涵盖上述三个源码目录中未加载的文件；分别按 `covered_lines / num_statements` 和 `covered_branches / num_branches` 验收整体与受影响模块双 90%。测试退出非零或任何门槛不足均不能通过；覆盖率统计范围见根目录 [测试与覆盖率范围](../../../docs/测试与覆盖率范围.md)。

## 维护约束

前端位置测试必须覆盖 UTF-8、CRLF、EOF 及 fake Node 的 Point getter 拒绝；真实 Tree-sitter 解析作为单独回归。输入缺失、预算耗尽、损坏 manifest、Clang 不可用和投影发布失败应有异常测试。

只修改 runtime/test 锁文件中明确需要的依赖，并重新构建测试镜像。扫描器不执行被扫描工程的 Make、CMake、RPM、Shell 或测试命令。Compose 禁网、只读根目录和能力限制由 `compose.test.yml` 管理。

根 `.dockerignore` 为构建选择清单、夹具和文档保留精确例外；不要让 `build-*` 缓存排除规则误删这些已跟踪输入。最终验证须使用正常构建的镜像，不能向旧容器补复制源码后宣称构建路径已通过。

依赖与来源见 [依赖清单](dependency-inventory.zh-CN.md)；知识刷新见 [知识维护](knowledge.zh-CN.md)。
