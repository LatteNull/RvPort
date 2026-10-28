# 扩大语料范围后的当前源码验收

用户于 2026-10-28 明确同意补齐十条规则的可执行语料及当前源码 observed。修改范围仍限于本扫描器，未修改前端、Java 后端或其他工具；工作区其他任务的改动予以保留。

## 实现与预期依据

- 新增 `corpus_runner.py`，从固定输入生成真实 C/C++ 临时文件，调用当前 Scanner；IR case 由锁定 Clang 现场编译，共享 manifest 的身份及摘要来自实际编译上下文和 bitcode 字节。运行器完全不读取 oracle。
- `make validation` 改为先运行再评分。182 个可执行 case 覆盖十条规则，每条至少 6 正例、6 反例、3 unknown，并包括 C11/C17/C++17/C++20、AST-only、共享 IR、固定 libm overlay、抑制和预算生命周期。
- 评分比较完整 assessment 状态多重集、主位置重数、affectedCount、诊断、scan 状态及抑制数量；重复结果计 FP，matched 与 unknown 并存不被首条 assessment 遮蔽。源码/协议资源摘要、输入摘要及 case 集合不一致会拒绝评分。
- 保留历史 `reviewed-corpus-v1.json` 和 `reviewed-observed-v1.json` 作为评分器历史回归输入，不用于证明当前质量。新 oracle 为独立编写的预期，未声称已完成维护者人工批准；正常代码审查要求仍然适用。
- 部署包核验发现内部 build-context schema 被根 Docker 构建输出过滤规则排除。已在扫描器内部移动到 `schemas/contexts/v1/context.schema.json`，保留公开 `$id` 和合同，新增所有 schema 资源的打包路径回归测试；未修改根 Docker 规则或前后端源码。

首轮语料设计审查修正了这些输入假设，未从 observed 自动回填真值：

- 复杂 FMA 在同行存在多个可绑定算术候选，属于保守 unknown，作为额外边界用例保留；float/double 的简单乘加分别作为正例。
- 一个隐式转换仅有一条直接证据，引用预算 1 不能制造 unknown。转换 unknown 改用尚未建模的 `__float128` 端点；比较/API 引用预算用两个直接事实触发。
- libm 使用公开请求的 `build_contexts.source/target` 字段和真实 `<math.h>` 声明；正例选择当前明确定义的数学函数族。overlay 是固定测试契约，不是平台库行为测量。
- 唯一可解析的宏 intrinsic 仍是架构迁移风险，保留三个宏正例；宏本身不等于归属歧义。
- scan 状态按公开契约：全部必需 assessment 都 unknown、无可用判断时为 failed；局部 unknown 为 partial；非阻断映射警告可为 complete。

## 工具级验证

最终工具镜像：`rvport-fp-granularity:20261028-packaged`，镜像 ID：
`sha256:0a116d16f54e347802bf6f7f2d3c6946de58eb2d1e61e174d783ca9cdb359bab`。

以下命令均从 `D:/projects/RvPort` 执行；测试、编译、代码生成和覆盖率在 Docker 内运行，CPU/内存有上限，测试禁网：

```powershell
docker build -f tools/floating-point-precision-scanner/Dockerfile.dev -t rvport-fp-granularity:20261028-packaged tools/floating-point-precision-scanner
docker run --name rvport-fp-granularity-packaged-final --memory 8g --cpus 2 --network none -e CMAKE_BUILD_PARALLEL_LEVEL=2 rvport-fp-granularity:20261028-packaged make lint typecheck coverage cpp-coverage integration validation
```

已确认：Ruff 通过，mypy 检查 51 文件；380 项 Python 单元/契约测试、21 项 C++ 测试和 29 项真实 Clang 集成测试通过，无跳过。

Python 整体行覆盖率 97.5244%、分支 94.0703%。本 change 受影响模块如下；原 Makefile 中更广的逐模块门禁也全部通过。

| 模块 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| `__init__` | 100% | 无可执行分支 |
| `facts` | 95.8115% | 91.3043% |
| `rules` | 97.4619% | 93.0556% |
| `reduction_candidates` | 100% | 100% |
| `evidence` | 100% | 100% |
| `application` | 93.7685% | 90.6250% |
| `corpus_runner` | 100% | 100% |
| `validation` | 99.3711% | 98.0769% |
| `protocol` | 98.4615% | 92.8571% |

统计包含整个 `src/floating_point_precision_scanner` 的 31 个源码文件（含未被加载源码），共 3999 个语句、1366 个分支，`omit=[]`；仅排除 3 行 `TYPE_CHECKING` 静态导入。C++ 统计全部 `src/cpp` 自有可执行源码，行 656/663（98.9442%）、分支 236/256（92.1875%）；第三方 LLVM/GTest、生成构建文件及纯头文件声明不计入。

## 当前源码语料结果

182/182 精确匹配，全部门禁通过。所有规则 strict/supported precision、recall 与 exact match 均为 100%；全部规则 FP=0、FN=0、应命中却 abstain=0。生命周期 case 全部精确匹配。TP 按 Finding 计数，抑制 case 保留 matched assessment 但没有公开 Finding，因此不增加 TP。

| 规则 | case 数 | TP |
|---|---:|---:|
| architecture-specific-fp-api | 20 | 10 |
| floating-environment | 17 | 7 |
| fma-contraction | 20 | 7 |
| fragile-fp-comparison | 17 | 7 |
| long-double-abi | 17 | 7 |
| math-library-variance | 17 | 7 |
| mixed-precision-conversion | 17 | 7 |
| reduction-reassociation | 23 | 18 |
| unsafe-fp-optimization | 17 | 7 |
| x87-excess-precision | 17 | 7 |

摘要核对：observed 中 53 个 Python/协议资源摘要与宿主工作区一致。输入摘要为
`b8a8b78f3bc79b0ca76088fc843f56a3b2e13fe2bdeb64be78cf36c64382dc18`；oracle 摘要为
`a1484e3d6fdd99f933e432e74edf9b829aa2f1649f1d5b7644be81a75ab23a94`。

```powershell
docker cp rvport-fp-granularity-packaged-final:/workspace/artifacts .migration-reports/fix-reduction-finding-granularity/2026-10-28/packaged-artifacts
```

原始报告位于仓库私有目录 `.migration-reports/fix-reduction-finding-granularity/2026-10-28/`：
`packaged-validation.log`、`packaged-artifacts/coverage/{coverage.json,coverage.xml,htmlcov,cpp-coverage.json}`、
`packaged-artifacts/validation/{validation-result.json,current-observed.json,cases/}` 和 `packaged-source-attestation.json`。

## 性能与确定性

```powershell
docker run --name rvport-fp-granularity-packaged-benchmark --memory 4g --cpus 4 --cpuset-cpus 8-11 --network none rvport-fp-granularity:20261028-packaged make benchmark
docker cp rvport-fp-granularity-packaged-benchmark:/workspace/artifacts/benchmark .migration-reports/fix-reduction-finding-granularity/2026-10-28/packaged-benchmark
```

Linux/amd64、Clang/LLVM 21.1.8、4 CPU、4 GiB、禁网，三档绝对资源上限、相对历史基线回退与热缓存比例门禁全部通过；冷/热缓存及不同绝对目录下的语义摘要完全相同。未修改 workload、基线或门槛。

| 档位 | 冷 wall 秒 | 热 wall 秒 | 冷 CPU 秒 | 冷峰值 RSS 字节 | 冷结果字节 |
|---|---:|---:|---:|---:|---:|
| S | 1.0211 | 0.0767 | 0.9793 | 87990272 | 6136 |
| M | 3.9758 | 0.1853 | 3.7420 | 87990272 | 12388 |
| L | 19.5160 | 0.8661 | 18.2072 | 87990272 | 43590 |

报告：私有目录下的 `packaged-benchmark.log`、`packaged-benchmark/benchmark-result.json`。

## 最终隔离部署验收

从仓库根使用 `rvport-fp-granularity` 专用 Compose 项目、网络、数据卷和测试凭据。端口仅绑定本机测试端口；没有连接既有部署数据库或真实 SSH。后端/worker 设为 2 CPU、4 GiB，其余服务 1 CPU、512 MiB 或 1 GiB。

沿用私有 `Dockerfile.validation`，已核对它与仓库 `backend/Dockerfile` 仅有 LLVM apt 下载超时/重试参数差异。未改变依赖版本或安装步骤，也未修改仓库后端 Dockerfile。构建期间一次命令跟踪中断、一次 Docker daemon 连接 EOF 均记录为失败，恢复后完整重跑，未使用中断前的镜像冒充成功。最终命令如下：

```powershell
$env:COMPOSE_BAKE = 'false'
docker compose --env-file .migration-reports/fix-reduction-finding-granularity/compose.env -f docker-compose.yml -f .migration-reports/fix-reduction-finding-granularity/compose.override.yml --parallel 1 build
docker compose --env-file .migration-reports/fix-reduction-finding-granularity/compose.env -f docker-compose.yml -f .migration-reports/fix-reduction-finding-granularity/compose.override.yml up -d --wait --wait-timeout 300
```

最终全量构建退出码 0，最终验收轮次的 `up -d --wait` 一次成功。后端镜像为
`sha256:15558c5f72820f29fa0fd4d28b412b264652035fa101c6ed775e7148587df491`。
7 服务 running，6 个有 healthcheck 的服务均 healthy，worker 无独立 healthcheck；后端 `/actuator/health` 为 UP，前端 HTTP 200。各服务最近 160 行日志没有 ERROR/FATAL/异常堆栈。

部署 worker 的正式 CLI 扫描 C++ range-for 与尾部循环样例，结果为 complete，恰好两条 Finding，主位置 4、7 行，每条 occurrence 数量和 affectedCount 均为 1。安装包 53 个 Python/协议资源与最终工具测试源码完全一致，包括已修复的 context schema。

```powershell
docker exec rvport-fp-granularity-backend-worker-1 mkdir -p /tmp/fp-granularity
docker cp .migration-reports/fix-reduction-finding-granularity/runtime-case/main.cpp rvport-fp-granularity-backend-worker-1:/tmp/fp-granularity/main.cpp
docker cp .migration-reports/fix-reduction-finding-granularity/runtime-case/request.json rvport-fp-granularity-backend-worker-1:/tmp/fp-granularity/request.json
docker exec rvport-fp-granularity-backend-worker-1 /opt/specialized-analysis-venv/bin/fp-precision-scanner scan --request /tmp/fp-granularity/request.json --output /tmp/fp-granularity/result.json --clang /usr/bin/clang-21 --ir-worker /opt/rvport/analysis-tools/bin/fp-ir-worker
```

另在实际安装包中重跑全部 182 个语料用例及评分，仍全部精确匹配、全部门禁通过，验证 libm build context、共享 IR 和其他规则的安装路径：

```powershell
docker exec rvport-fp-granularity-backend-worker-1 mkdir -p /tmp/fp-validation
docker cp tools/floating-point-precision-scanner/tests/fixtures/validation/executable-inputs-v1.json rvport-fp-granularity-backend-worker-1:/tmp/fp-validation/inputs.json
docker cp tools/floating-point-precision-scanner/tests/fixtures/validation/executable-corpus-v1.json rvport-fp-granularity-backend-worker-1:/tmp/fp-validation/oracle.json
docker exec -e FP_SCANNER_CLANG=/usr/bin/clang-21 -e FP_SCANNER_IR_WORKER=/opt/rvport/analysis-tools/bin/fp-ir-worker rvport-fp-granularity-backend-worker-1 /opt/specialized-analysis-venv/bin/python -m floating_point_precision_scanner.corpus_runner --inputs /tmp/fp-validation/inputs.json --output /tmp/fp-validation/current-observed.json
docker exec rvport-fp-granularity-backend-worker-1 /opt/specialized-analysis-venv/bin/python -m floating_point_precision_scanner.validation --corpus /tmp/fp-validation/oracle.json --observed /tmp/fp-validation/current-observed.json --output /tmp/fp-validation/validation-result.json
docker cp rvport-fp-granularity-backend-worker-1:/tmp/fp-validation .migration-reports/fix-reduction-finding-granularity/2026-10-28/installed-corpus
docker compose --env-file .migration-reports/fix-reduction-finding-granularity/compose.env -f docker-compose.yml -f .migration-reports/fix-reduction-finding-granularity/compose.override.yml down
```

验收后关闭专用服务和网络，保留测试卷及报告。部署检查覆盖正式 CLI、完整语料和服务健康；没有新增浏览器 E2E 或连接真实 SSH。既有业务部署未由本任务更新，历史扫描结果不重写。

报告：同一私有目录下的 `compose-build-packaged-retry.log`、`compose-up-packaged.log`、
`compose-packaged-{ps.json,health.json,logs.log,source-hashes.json,runtime-result.json,acceptance.json,down.log}`、
`installed-corpus.log` 与 `installed-corpus/{validation-result.json,current-observed.json,cases/}`。

## 阶段交接

实现及全部适用验证完成，25/25 任务完成。OpenSpec 严格校验、差异空白检查与文档链接检查通过；普通代码审查与合并流程仍按仓库约定进行。尚未归档，也未提交或推送。

下一阶段为归档。可在聊天中执行：

```text
$openspec-archive-change 在 D:\projects\RvPort\tools\floating-point-precision-scanner 归档 fix-reduction-finding-granularity
```
