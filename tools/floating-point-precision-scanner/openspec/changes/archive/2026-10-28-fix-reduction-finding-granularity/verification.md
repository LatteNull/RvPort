# 实施与验证记录

本文保留 2026-10-27 的历史过程；2026-10-28 用户已批准扩大完整语料范围，最新验收见
[扩大范围后的当前源码验收](verification-2026-10-28.md)。本文末尾的未完成状态仅代表当时状态。

日期：2026-10-27。修改范围仅为 `tools/floating-point-precision-scanner`，未修改前端、Java 后端或其他工具。
工作区同时存在其他任务的后端和 memory-order-analyzer 改动，未纳入本变更。

## 实施结果

- 最近循环与累加器声明构成稳定候选身份；嵌套循环、跨函数、同循环不同累加器分别评估。
- 每个候选独立生成 assessment/Finding，隔离 AST/IR 关联、置信度、unknown/failed、suppression 和预算。
- 本候选多个证据位置仍可共存，`affectedCount=1`；相同事实去重、输入重排稳定。
- 修复 AST 左值位置与 LLVM 运算符位置不一致造成的关联拒绝，使用已知表达式范围与运算类型校验。
- `reduction-reassociation` 为 1.1，facts 1.5、mapper 1.2、evidence 1.2、registry 1.3。请求与结果 v2 合同保持不变。

## 当前源码测试

开发镜像 `rvport-fp-granularity:local`：
`sha256:dd68f894374c2647020354c21c5930f91411ac0bc62943b784e59a1766108790`。
所有编译、测试和覆盖率均在 Docker 内执行，未使用宿主机编译器。

在 `D:/projects/RvPort` 执行：

```powershell
docker build -f tools/floating-point-precision-scanner/Dockerfile.dev -t rvport-fp-granularity:local tools/floating-point-precision-scanner
docker run --name rvport-fp-granularity-final --memory=8g --cpus=2 --network=none -e CMAKE_BUILD_PARALLEL_LEVEL=2 rvport-fp-granularity:local make lint typecheck coverage cpp-coverage integration validation
docker cp rvport-fp-granularity-final:/workspace/artifacts .migration-reports/fix-reduction-finding-granularity/final-artifacts
```

上述容器名为本次实际运行名称；重新执行时选择新的专用名称。

| 检查 | 当前结果 |
|---|---|
| Ruff / mypy | 通过；mypy 检查 50 个源文件 |
| Python 单元/契约测试 | 364 通过 |
| C++ 单元测试 | 21 通过 |
| 真实 Clang 21.1.8 集成测试 | 29 通过，无跳过 |
| OpenSpec 严格校验 | 通过 |
| 历史 fixed observed 对比 | 通过；不能等同当前十规则扫描准确率 |

基线镜像的 332 项单元/契约测试通过，Python 整体行覆盖率 97.13%、分支覆盖率 93.27%。
当前结果如下（独立报告行/分支，不使用 coverage.py 混合百分比）：

| 范围 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| Python 整体 | 97.45% | 93.94% |
| facts | 95.81% | 91.30% |
| rules | 97.46% | 93.06% |
| reduction_candidates | 100% | 100% |
| evidence | 100% | 100% |
| application | 93.77% | 90.63% |
| `__init__` 版本常量 | 100% | 不适用：无分支 |
| C++ 整体 | 98.94% | 92.19% |

Python 统计 `src/floating_point_precision_scanner` 全部自有可执行源码（30 文件、3884 条可执行行、
1336 个分支），包含未加载模块，`omit=[]`。仅排除 3 行 `TYPE_CHECKING` 静态导入分支。
JSON schema 通过协议测试验收，不计入可执行源码分母。保留原有所有 affected gates，并增加新候选模块。
C++ 覆盖 `src/cpp/ir_facts.cpp`、`src/cpp/ir_worker.cpp`；头文件仅声明，无独立可执行逻辑。
LLVM/GTest 第三方代码、构建生成文件和测试本身不计入自有业务代码范围。

完整 JSON/XML/HTML 与原始日志位于根目录 `.migration-reports/fix-reduction-finding-granularity/`：
`final-artifacts/coverage/coverage.json`、`coverage.xml`、`htmlcov/index.html`、`cpp-coverage.json`、
`final-validation.log`。该目录未纳入公开源码。

## 当前归约观察与历史语料缺口

独立编写的 `reduction-granularity-oracle-v1.json` 与真实 C fixture 明确预期第 4、7、16、17 行
为 4 条结果；单点抑制后保留第 7、16、17 行。冷暖缓存结果及语义摘要相同；匹配的 IR 仅进入
自身候选，其他函数/文件的 IR 不进入任何候选。实际 observed 保存在 `final-artifacts/validation/`
下的 `reduction-granularity-observed.json` 和 `reduction-ir-True/False-observed.json`。
oracle 预期不是由 observed 自动回填，仍需按仓库规定接受代码审查。

额外通过当前镜像 CLI 验证 C++17 的 range-for lanes 累加和后续尾部点积（与问题截图结构一致）：
第 4、7 行产生两条 heuristic Finding，`affectedCount` 各为 1、扫描 complete。
输入保存在私有报告目录 `runtime-case/`，实际结果为 `result-cpp.json`。运行时把只读输入复制到
容器可写临时目录，因为 frontend 需要在项目目录暂存 AST；该操作不写宿主机源码。

历史 `reviewed-corpus-v1.json` 的十规则 case 只有描述、摘要与抽象 finding key；对应可执行
输入和完整 observed 生成器未提供。`make validation` 仍读取 `reviewed-observed-v1.json`。
因此虽然历史对比通过，不能声称当前源码十规则 precision/recall、exact/lifecycle 门禁通过。
补齐整个历史语料涉及其他九条规则及其执行输入，超出本次归约修复范围，5.5 保持未完成。

## 仓库验收

性能门禁命令（同一当前源码镜像，禁网，4 CPU/4 GiB）：

```powershell
docker run --name rvport-fp-granularity-benchmark --cpus=4 --cpuset-cpus=8-11 --memory=4g --network=none rvport-fp-granularity:local make benchmark
```

S/M/L 三档均通过 absolute、hot_ratio、regression 门禁，冷暖及换目录语义一致。
冷 wall 中位数分别为 1.006、4.283、20.740 秒；热 wall 为 0.080、0.367、1.111 秒。
报告为私有目录 `benchmark/benchmark-result.json`，没有修改 accepted baseline。

隔离 Compose 项目名为 `rvport-fp-granularity`，使用独立网络、命名卷、测试凭据和 localhost
28xxx 端口；后端/worker 各限制 2 CPU、4 GiB，其余服务限制 1 CPU、512 MiB 或 1 GiB。
配置保存在上述私有报告目录的 `compose.env`、`compose.override.yml`，不包含真实部署凭据。
配置解析检查通过。

首次构建遇到其他任务的 `ReportDocumentOrganizerTests.java:25` 泛型编译错误；该任务随后已修复
工作区文件。本变更没有修改它。第二次构建发生 Docker 构建连接 EOF，恢复后已继续验证。
最终全部默认服务镜像构建成功，后端镜像为
`sha256:b152d04690fa621d4155858449183a944a3006fda3149345aa0126e444a339e9`。

运行时 LLVM 下载曾长时间停滞。终止本次构建进程树后，在私有 `Dockerfile.validation` 副本的
运行时 LLVM 安装命令加入 `Acquire::http::Timeout=45`、`Acquire::https::Timeout=45`、
`Acquire::Retries=2`，通过私有 Compose override 指向该副本；依赖版本、源代码及构建步骤
保持一致，未修改仓库后端 Dockerfile。受限重试已完成全部构建。

在仓库根执行的最终 Compose 命令：

```powershell
docker compose --env-file .migration-reports/fix-reduction-finding-granularity/compose.env -f docker-compose.yml -f .migration-reports/fix-reduction-finding-granularity/compose.override.yml --parallel 1 build
docker compose --env-file .migration-reports/fix-reduction-finding-granularity/compose.env -f docker-compose.yml -f .migration-reports/fix-reduction-finding-granularity/compose.override.yml up -d --wait --wait-timeout 300
```

`up -d --wait` 一次成功。7 个服务均 running，6 个有 healthcheck 的服务均 healthy；worker
本身没有独立 healthcheck。后端 `/actuator/health` 为 UP，前端 HTTP 200。检查所有服务最近
160 行日志，无 ERROR、FATAL 或异常堆栈；RabbitMQ 的 `0 servers failed` 是正常启动信息。

在实际 worker 容器的安装版本执行扫描入口：

```powershell
docker cp .migration-reports/fix-reduction-finding-granularity/runtime-case rvport-fp-granularity-backend-worker-1:/tmp/fp-granularity
docker exec rvport-fp-granularity-backend-worker-1 /opt/specialized-analysis-venv/bin/fp-precision-scanner scan --request /tmp/fp-granularity/request.json --output /tmp/fp-granularity/result.json --clang /usr/bin/clang-21 --ir-worker /opt/rvport/analysis-tools/bin/fp-ir-worker
```

扫描 complete，产生两条独立 Finding，主位置第 4、7 行，每条只有一处 occurrence，
`affectedCount` 各为 1。此处验证的是部署 worker 的正式扫描 CLI 及服务健康，不涉及真实 SSH
构建或浏览器端完整工作流。worker 安装的 facts/rules/evidence/reduction_candidates/application
五个文件 SHA-256 均与当前工作区源码一致。

证据：私有报告目录的 `compose-build-bounded.log`、`compose-up.log`、`compose-ps.json`、
`compose-logs.log`、`compose-health.json`、`compose-source-hashes.json`、`compose-runtime-result.json`。
检查完成后通过同一隔离配置执行 `docker compose down`，保留测试卷与报告，未操作原部署。

## 阶段状态

实现、单元/集成/覆盖率/性能及隔离部署验证完成。文档 11 份、10 个相对链接检查通过；
OpenSpec 严格校验与 `git diff --check` 通过。5.5 的完整历史语料验收尚未完成，已请求确认
是否扩大范围；6.4 的全部通过后交接条件尚未满足，暂不归档，不自动进入其他规则实现。
