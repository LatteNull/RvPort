# 验证记录

## 2026-10-10 独立测试

工作目录为仓库根目录，在 Linux Docker 中执行：

```powershell
docker run --rm -v D:/projects/RvPort/tools/floating-point-precision-scanner:/workspace -w /workspace rvport-fp-scanner-dev:latest bash -lc 'PYTHONPATH=src python3 -m coverage run --branch --source=src/floating_point_precision_scanner -m pytest -q tests/unit tests/contract && python3 -m coverage json -o artifacts/coverage/coverage.json && PYTHONPATH=src python3 -m floating_point_precision_scanner.coverage_gate artifacts/coverage/coverage.json --affected source_locations --affected facts --affected rules --affected result_v2 --affected evidence --affected application'
```

251 项单元/契约测试通过。统计整个 `src/floating_point_precision_scanner`，包括未加载的生产模块；不统计测试、fixture、第三方依赖与生成文件，它们不属于该生产源码目录。未修改 Java 业务代码，因此没有以本次 Python 指标声称后端 Java 整体覆盖率。

| 范围 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| 工具整体 | 97.12% | 93.01% |
| 受影响模块合计 | 96.66% | 92.51% |
| application | 93.77% | 90.63% |
| evidence | 98.20% | 96.00% |
| facts | 96.03% | 91.51% |
| result_v2 | 97.99% | 93.59% |
| rules | 97.35% | 91.05% |
| source_locations | 100.00% | 100.00% |

覆盖率报告：`tools/floating-point-precision-scanner/artifacts/coverage/coverage.json`。

## 真实 Clang 集成测试

```powershell
docker run --rm -v D:/projects/RvPort/tools/floating-point-precision-scanner:/repo -w /repo rvport-fp-scanner:validate bash -lc 'PYTHONPATH=src:. FP_SCANNER_IR_WORKER=/workspace/build/fp-ir-worker pytest -q tests/integration'
```

25 项通过，包含 c89/c99/gnu17、真实主文件/头文件/宏、UTF-8/CRLF/制表符、外部头文件和 `#line` 的物理坐标验证。Ruff 检查通过；当前 change 与工具侧 13 份规范严格校验通过。

## 运行镜像

完整 `docker compose build backend` 在上游系统包与 LLVM 工具链下载阶段持续缓慢，未完成；已中止，不能声称完整冷构建成功。本次没有 Java/原生二进制/依赖变更，使用现有镜像依赖构建增量验证镜像，仅替换浮点扫描器 Python 包，并验证模块可加载。

- 基础镜像：`sha256:1b2ad97c00a82f441186a51c818a0a60590a1043003474073528eadcfdd7dce3`
- 验证镜像：`sha256:261404dfef191576f4c59dac4d20c63fe15cc2d20f27bae735d8209a1efa583b`
- 临时 Dockerfile：`backend/runtime/fp-location-validation/Dockerfile`。
- 通过 `docker compose up -d --no-deps --force-recreate backend backend-worker` 启用验证镜像。

## 真实 API 验证

- 项目：`demo-test1`，`9915a12c-9338-419e-b589-9a3984d56c62`。
- 源码版本：`a019391f-89e6-4d8e-8eed-1b7871055541`。
- 历史 runId：`d1130a1e-0d38-4d07-b83e-26181a89313f`，两条 Finding 原始位置为空，历史记录不改写。
- 新 runId：`8b199c9e-cdae-42aa-af4c-a6abef2f264a`。
- 新 taskId：`80449faa-f6b5-4ac6-9fe0-aa775ba1fa2b`。
- 通过容器内 ApiClient 登录、刷新 CSRF 后调用 `POST /api/projects/{projectId}/floating-point-analyses`，未直接插入任务。
- 任务于 `2026-10-10T08:10:25Z` 成功结束，耗时约 114 秒。
- 分析为 `AST_ONLY / PARTIAL`：历史 BC 在当前 worker 校验失败（`BITCODE_WORKER_VALIDATION_FAILED`），按既有降级流程执行；并有类型/来源证据不足诊断。不能将任务成功描述为所有规则完整分析成功。本次位置修复在该真实 AST-only 路径验证通过，AST+BC 由真实 Clang 集成套件覆盖。
- 原始 JSON、数据库、列表索引、详情及下载 HTML 的路径行列一致；按文件过滤、按行号正/倒序排序及不存在文件返回空列表均通过；历史两条空位置保持不变。

| Finding | 文件 | 主位置 | 关联行 |
|---|---|---|---|
| fragile-fp-comparison | src/vectorcalc.cpp | 16:9 | 19、22、34、37 |
| reduction-reassociation | src/vectorcalc.cpp | 62:9 | 无 |

数据库两条记录 `af6d02e9-3eb5-4847-b873-6617332a17c2`、`e055cb7a-f1ff-401e-8ff6-a96078d4001d` 的 `file_path/start_line/end_line` 与 `detail.fact.primaryLocation` 一致。v2 目前输出点坐标，故 start/end 行相同，不表示整个表达式的范围。

审计文件均来自 API 下载/查询，保留在 `backend/runtime/fp-location-validation/`：`result.json`、`report.html`、`run.json`、`findings.json`、`detail-*.json`、`old-findings.json`、`verification.json`。

## 另行记录的既有问题

恢复位置后可见，`fragile-fp-comparison` 的 5 个位置都是 `float* == nullptr` 检查，不是真正的浮点数比较。点积归约的第 62 行确实为 `result += left[index] * right[index];`。用户随后授权在本 change 修复空指针误报，追加验证见下文；原始报告仍保留用于前后对照。

## 验收边界

源码位置链路验收完成；无 Java、前端、内存序分析器变更，无历史数据回填。增量镜像已运行，完整 Dockerfile 冷构建未完成，不把其标为成功。Git 差异空白检查通过；不处理工作区原有 ReadMe、分享文档和其他无关文件。

## 追加：空指针比较误报

用户授权后，为比较操作加入浮点标量类型判断，使用真实操作数类型及 typedef 展开，不调整声明/ABI 类型规则。旧模拟 AST 中 `==` 被错误设为 double 返回值且无操作数，已改为 C 语言的 int 返回值及两个 double 操作数，保留全部原断言。

沿用上文相同命令，追加后独立单元/契约测试 **276 项通过**，真实 Clang 集成测试 **26 项通过**，Ruff 通过。整体行/分支 **97.13% / 93.03%**；受影响模块合计 **96.68% / 92.55%**；facts **96.11% / 91.67%**，其余模块与前表一致。统计范围和报告路径不变。

真实 C++ 正反例覆盖 nullptr、零空指针常量、__null、指针相等/大小比较、数组地址退化，及解引用、数组元素、typedef 标量、引用变量数值比较。测试断言只有数值比较所在行产生结果；不把已有零值比较风险规则的过滤行为当作本次回归。

追加镜像：`sha256:5d66210d5685ea5cc66870cf1f4629cca84a3e7bdd101cd1ab56770e2f009c83`，仍采用上文增量构建方式。新 API 扫描 runId `8f6a9c4f-8c85-4c72-9685-f632493343ca`，taskId `b1b8f6ed-a70f-4b02-9e01-cbc0ea46af45`，任务成功完成。

新结果仅 1 条 `reduction-reassociation`，位置 `src/vectorcalc.cpp:62:9`；`fragile-fp-comparison` 空指针误报已消失。API 列表、详情、原始 JSON、下载 HTML 和数据库核对通过。分析仍为 AST_ONLY/PARTIAL，原因同前次 BC/证据降级，未借此声称完整 BC 分析成功。

新报告保留于 `backend/runtime/fp-location-validation/pointer-fix/report.html`，同目录还有 `result.json`、`findings.json`、`detail.json` 和 `run.json`。此前两次扫描和审计文件均保留，不回填历史数据。追加后的当前 change、工具 13 份规范严格校验及差异空白检查通过。

## 追加：后端源码上下文接口

本阶段根据用户新授权修改 Java Service、Controller 和新增响应 DTO，未修改前端。接口说明见 `backend/docs/specialized-finding-code-context.md`；此前“无 Java 变更”结论仅对应位置/指针修复阶段。

定向命令（仓库根目录）通过 15 项测试：

```powershell
docker run --rm -v D:/projects/RvPort/backend:/workspace/backend -v 'rvport-maven-cache:/root/.m2' -w /workspace/backend --entrypoint mvn rvport-backend-maven-test:latest -B -o '-Dtest=SpecializedAnalysisServiceTests,SpecializedAnalysisControllerTests' test
```

初次全量验证因该 Maven 镜像没有 Python，导致既有 KB/SBOM 本地 fixture 进程测试失败；不是上下文接口回归。改用带 Python 的质量验证镜像，并在一次性容器中补充 `python` 命令别名，不改业务代码或放松断言：

```powershell
docker run --rm -v D:/projects/RvPort:/workspace -v 'rvport-maven-cache:/root/.m2' -w /workspace/backend --entrypoint sh rvport-backend-quality:local -lc 'ln -s /usr/bin/python3 /usr/local/bin/python && mvn -B -o clean verify'
```

全量 `clean verify` 成功：1705 项测试，0 失败、0 错误、2 项既有可选真实外部测试跳过。整体行覆盖率 96.76%（24205/25016），分支覆盖率 91.01%（9005/9894）；受影响 analysis 包行覆盖率 96.75%（1101/1138），分支覆盖率 90.59%（491/542）。JaCoCo 整体及包级 90% 门禁通过；统计包含未加载的生产源码，仅排除自动生成的 jOOQ 代码。报告位于 `backend/target/site/jacoco/index.html` 和 `jacoco.xml`。

使用本次完整验证后生成的 JAR 更新增量运行镜像，镜像为 `sha256:901151a9d33ee1ef5988bec1b64bda7e44dd5d22e743d0c1a3d3eeb917f8451c`。通过 Compose 重建 backend 和 backend-worker 容器，API 健康检查通过。该方式复用已有工具和依赖层，不代表完整 Dockerfile 冷构建已通过。

通过真实 API 查询现有 Finding，无需重跑扫描：

```text
GET /api/projects/9915a12c-9338-419e-b589-9a3984d56c62/floating-point-findings/40546c30-01a9-4c22-be32-1329d520b222/code-context
```

响应绑定源码版本 `a019391f-89e6-4d8e-8eed-1b7871055541`，文件为 `src/vectorcalc.cpp`，上下文第 42–72 行共 31 行，保留空行。唯一高亮为第 62 行 `result += left[index] * right[index];`，其 `highlighted=true`；文件结尾不足 20 行时按实际长度截断。未登录返回 401，同一 Finding 通过内存序接口查询返回 404。实际响应保存于 `backend/runtime/fp-location-validation/pointer-fix/code-context.json`。

后端接口及实际响应已提供，前端仍需由其负责同事接入；本 change 不修改前端。

## 最终调整：详情一次返回源码

用户要求撤销独立上下文接口，已改为现有浮点/内存序 Finding 详情直接附带 `codeContext` 和 `codeContextUnavailableReason`。源码不可读时保留 Finding 详情，使用原因码说明，不把源码清理等情况变成详情请求失败；权限和归属仍严格校验。列表不读取源码，前端未改动。上述独立接口响应仅作为先前方案的验证记录保留，不是最终 API。

再次执行上文 Docker `mvn -B -o clean verify`：1705 项测试，0 失败、0 错误、2 跳过。整体行覆盖率 96.76%（24204/25015）、分支 91.01%（9001/9890）；analysis 包行 96.75%、分支 90.52%，所有 JaCoCo 门禁通过。统计范围、排除项和报告位置不变。

更新后的增量运行镜像为 `sha256:d1c30650a7fce5d5bc800fae9846853b94d998950934ae7a95537cbdb4603c5f`，Compose backend 与 backend-worker 均已重新创建。真实请求现有详情 `GET /api/projects/9915a12c-9338-419e-b589-9a3984d56c62/floating-point-findings/40546c30-01a9-4c22-be32-1329d520b222` 一次获得 Finding 与上下文，第 42–72 行、第 62 行高亮，原因码为 null。未认证请求 401，跨分析类型请求 404。

最终完整响应保留于 `backend/runtime/fp-location-validation/pointer-fix/detail-with-code-context.json`。单独路径已移除；验证时访问该不存在路径触发既有全局异常处理问题：`NoResourceFoundException` 被返回为 500 而非 404。此项单独记录，不属于上下文接口实现，不修改无关全局异常策略。
