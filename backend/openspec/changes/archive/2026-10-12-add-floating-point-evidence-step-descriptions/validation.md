# 验证记录

## 范围与实现

按用户授权修改 `tools/floating-point-precision-scanner`，后端仅同步浮点工具版本常量和补充测试/接口文档；不修改前端、不新增 API、不迁移数据库、不回填历史扫描。

工具 0.5.1 为 evidenceChain 每个步骤输出 `title/titleEn/reason/reasonEn`。一次性类型化索引解析真实事实；缺失/歧义和位置预算限制会明确传播到步骤及链级状态。身份、规则风险等级和引用拓扑保持不变。Python/IR worker 版本同时升级，工具 spec/docs 已同步。

## 独立单元测试

仓库根目录执行工具覆盖率：

```powershell
docker run --rm -v D:/projects/RvPort/tools/floating-point-precision-scanner:/workspace -w /workspace rvport-fp-scanner-dev:latest bash -lc 'PYTHONPATH=src python3 -m coverage run --branch --source=src/floating_point_precision_scanner -m pytest -q tests/unit tests/contract && python3 -m coverage json -o artifacts/coverage/coverage.json && python3 -m coverage html -d artifacts/coverage/htmlcov && PYTHONPATH=src python3 -m floating_point_precision_scanner.coverage_gate artifacts/coverage/coverage.json --affected step_descriptions --affected result_v2 --affected application --affected facts'
```

320 项通过。正常、异常、边界覆盖全部引用类型、缺事实、歧义、Unicode、文本长度、路径/凭据脱敏、预算、稳定身份与严格 Schema，并逐项断言现有风险原因的双语解释。统计全部自有 Python 源码，包含未加载模块；无模块排除，只排除静态 `TYPE_CHECKING` 导入。测试本身和第三方依赖不属于业务源码分母。

| 范围 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| Python 整体 | 97.30% | 93.25% |
| 受影响模块合计 | 96.33% | 92.72% |
| step_descriptions | 100% | 100% |
| result_v2 | 98.02% | 93.59% |
| application | 93.77% | 90.63% |
| facts（仅类型标注修正） | 96.11% | 91.67% |

报告：`tools/floating-point-precision-scanner/artifacts/coverage/coverage.json` 和 `htmlcov/index.html`。Ruff 定向检查通过，mypy 检查全部 48 个源码文件通过。

IR worker 用 `rvport-fp-scanner:step-descriptions` 验证镜像重新编译，执行 `make cpp-coverage`：21 项通过，自有 `ir_facts.cpp/ir_worker.cpp` 行 98.94%、分支 92.19%。LLVM/GTest 等第三方实现不进入分母。报告保存于 `backend/runtime/fp-step-description-validation/cpp-coverage/cpp-coverage.json`。

后端在一次性 Linux 容器运行：

```powershell
docker run --rm -v D:/projects/RvPort:/workspace -v 'rvport-maven-cache:/root/.m2' -w /workspace/backend --entrypoint sh rvport-backend-quality:local -lc 'ln -s /usr/bin/python3 /usr/local/bin/python && mvn -B -o verify'
```

先执行 clean verify；首轮新增 mock 重复导致 5 个 Mockito 严格检查错误，去掉重复设置后全量 1720 项，0 失败、0 错误、2 个既有可选外部测试跳过。外部连接均模拟返回值，不依赖实际数据库/SSH/对象存储。整体行 96.76%、分支 91.01%；analysis 包行 96.75%、分支 90.52%，JaCoCo 整体及包级门禁通过。纳入未加载自有生产代码，只排除生成的 jOOQ 源码。报告：`backend/target/site/jacoco/index.html` 与 `jacoco.xml`。

后端版本常量同步后的最终验证结果见下方追加记录。

## 真实编译器验证

```powershell
docker run --rm -v D:/projects/RvPort/tools/floating-point-precision-scanner:/repo -w /repo rvport-fp-scanner:step-descriptions bash -lc 'PYTHONPATH=src:. FP_SCANNER_IR_WORKER=/workspace/build/fp-ir-worker pytest -q tests/integration'
```

26 项通过。真实 Clang 21.1.8 的 AST-only 测试确认 sourceObservation 描述实际比较和行号，且不声称迁移必然失败；AST+BC 测试确认 IR 步骤包含实际 fast_math_flags，未记录属性不被假定启用。该验证不能替代上面的独立单测。

## 真实 API 验证

项目 `demo-test1`：`9915a12c-9338-419e-b589-9a3984d56c62`，源码版本 `a019391f-89e6-4d8e-8eed-1b7871055541`。使用已有 ApiClient 从测试配置读取凭据（未写入审计文件），通过正式 POST API 创建扫描，不直接插库。

首轮 runId `04d37f66-6414-4160-b723-230f4979f926`，taskId `b388ff20-bc06-473b-8429-87a837427503`。任务成功，分析为 AST_ONLY/PARTIAL，现存 BC 仍因 `BITCODE_WORKER_VALIDATION_FAILED` 降级；不能声称该项目完整 BC 分析成功。

1 条 reduction-reassociation Finding，`src/vectorcalc.cpp:62`；3 步均有双语字段。源码观测包含实际 float、函数符号、`+=`、ForStmt；assessment 说明尚无 IR 重排证明；conclusion 复用原有风险说明。原始下载 JSON 与详情 evidenceChain 深比较一致，详情仍返回代码上下文。数据库查询确认 3 步全部有非空字段。

历史 Finding `40546c30-01a9-4c22-be32-1329d520b222` 的原始 detail 与 codeContext 未变化。重扫按原有规则改变动态 reportInclusion，不能把该动态字段变化误认为历史扫描被改写。

首轮实际原始结果版本 0.5.1，但后端 toolVersion 常量仍为 0.5.0，已同步修正并增加断言，后续验证见追加记录。审计文件位于 `backend/runtime/fp-step-description-validation/`。

## 构建与范围限制

运行镜像采用已运行 backend 镜像作为基础，更新浮点 Python 包及重新编译的无覆盖率插桩 IR worker，复用现有依赖层，不等同于完整 Dockerfile 冷构建。原有两个本地 RISC-V 容器处于重启状态，与本次 worker 本地扫描无关，未擅自修复或删除。

无关 ReadMe、分享文档、runtime 和 `default.profraw` 不纳入本 change。最终 OpenSpec 和差异检查结果见追加记录。

## 最终验证追加

同步后端 0.5.1 常量后再次执行完整 `mvn -B -o verify`，1720 项，0 失败、0 错误、2 跳过，构建成功。整体行 24204/25015（96.76%）、分支 9001/9890（91.01%）；analysis 包行 1100/1137（96.75%）、分支 487/538（90.52%）。日志保留 `maven-final.log`。工具最终 320 项独立测试、26 项真实 Clang 测试、Ruff 与全量 mypy 均通过，覆盖率同前表。

最终增量运行镜像为 `sha256:dad9e2f1a464794938d39edbc9c6b0c51428aa5473e7406731c65a968f07d5cb`，包含本次完整验证生成的 JAR 和 0.5.1 工具/IR worker。通过 Compose 更新 API 和 worker；首轮审计 JSON 已保留到 `first-run/` 子目录。

最终正式 API 新建 runId `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a`，taskId `a7653736-9b55-4b0c-89f1-12fb67c4b0c2`，任务成功结束，分析仍为 AST_ONLY/PARTIAL（既有 BC 校验降级）。运行记录与原始制品均为 0.5.1。1 条 Finding、3 个步骤，JSON/详情深比较及数据库非空检查通过，代码上下文随详情返回，历史 detail 未回填。最终结果、详情和 `verification.json` 位于审计根目录。没有修改规则等级或把分析 partial 宣称为 complete。

backend 当前 change 严格校验通过，工具 13 份规范严格校验全部通过，`git diff --check -- backend tools/floating-point-precision-scanner` 通过。所有 13 项任务完成；未自动 sync/archive/commit/push。
