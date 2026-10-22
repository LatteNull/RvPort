# KB Scanner 开发与验证

[English](development.md) | 简体中文

从仓库根目录执行以下命令。源码、规则和被扫描样例只读；依赖、测试与输出留在独立 Docker 环境中。

```powershell
docker compose -f tools/kb-scanner/compose.test.yml build kb-scanner-test
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

`tests/run_container_tests.py` 为容器默认测试入口，运行各专项门禁及完整回归。全源码覆盖另外按下述命令统计，不能用专项门禁代替。整体与受影响模块行/分支均至少 90%，统计包括未加载的自有代码。测试夹具、第三方和生成数据不计入业务源码；集成、契约和真实解析器回归不替代隔离单测。

专项示例（仍在仓库根目录）：

```powershell
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --graph-unit
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --architecture-candidate-noise-unit
```

测试与质量清单位于 `tests/*inventory.json`；历史清单中的旧阈值只用于追溯，当前迁移验收必须满足双 90%。冻结的事实哈希、V1/V2 reader、断点语义、恶意输入无副作用、原生崩溃和确定性回归都应保留。不要自动改写人工 oracle 或历史差异账本来接受新行为。

## 全源码覆盖

以下命令在同一开发容器内执行，工作目录为工具根目录；通过 Docker 启动 shell，不在宿主机运行 Python：

```sh
export COVERAGE_FILE=/tmp/kb-all.coverage
python -m coverage run --branch --source=kb_scanner,scripts,tools -m unittest discover -s tests/unit -t .
python -m coverage json -o /tmp/kb-all-coverage.json
```

报告须涵盖上述三个源码目录中未加载的文件；分别按 `covered_lines / num_statements` 和 `covered_branches / num_branches` 验收整体与受影响模块双 90%。测试退出非零或任何门槛不足均不能通过。现有专项 runner 仍有历史阈值，不能将其成功等同于整个迁移范围达标；覆盖率统计范围见根目录 [测试与覆盖率范围](../../../docs/测试与覆盖率范围.md)。

## 维护约束

前端位置测试必须覆盖 UTF-8、CRLF、EOF 及 fake Node 的 Point getter 拒绝；真实 Tree-sitter 解析作为单独回归。输入缺失、预算耗尽、损坏 manifest、Clang 不可用和投影发布失败应有异常测试。

只修改 runtime/test 锁文件中明确需要的依赖，并重新构建测试镜像。扫描器不执行被扫描工程的 Make、CMake、RPM、Shell 或测试命令。Compose 禁网、只读根目录和能力限制由 `compose.test.yml` 管理。

依赖与来源见 [依赖清单](dependency-inventory.zh-CN.md)；知识刷新见 [知识维护](knowledge.zh-CN.md)。
