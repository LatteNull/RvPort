## 1. 固定结果 v2 合同

- [x] 1.1 新增唯一的浮点扫描结果 v2 JSON Schema、浮点专属 vocabulary/reference rules 和 registered extension schemas，固定 `scan/project/summary/findings/diagnostics/extensions` 顶层结构及 camelCase 命名。
- [x] 1.2 增加正常、facts-only、聚合 finding、heuristic、suppressed、partial、invalid request、failed 和 internal error 的最小 contract fixtures，并确保每个 fixture 都能独立通过 Schema 与跨引用校验。
- [x] 1.3 明确并测试 analysis、profiles、artifacts、suppressions、runtime 五类 `org.rvport.floating-point-scanner.*` 扩展的必填字段、大小边界、排序和未知 namespace 拒绝语义。

## 2. 实现 v2 投影与引用模型

- [x] 2.1 建立内部 scan/project/summary/finding/diagnostic 到结果 v2 的单一 projector/serializer，不让 CLI、规则或调用方分别拼接公开 JSON。
- [x] 2.2 将每条 finding 投影为稳定 `fact/conclusion/occurrences/primaryOccurrenceId/evidenceChain`，保留规则版本、定性 confidence、evidence origin、人工确认、双语内容和 validation plan。
- [x] 2.3 将 canonical AST facts、LLVM facts、AST↔IR binding、profiles、build contexts、compile options 和 assessments 投影为稳定 typed refs、steps、edges、primary path、breaks、impact refs 与 producer/digest 外部引用。
- [x] 2.4 将全部 assessments、规则 registry/依赖、layer 分母、bundle 摘要、profiles/artifacts、suppression 审计、预算 frontiers 和 cache 计数投影到受约束扩展，并保持没有 finding 的 notMatched/unknown/skipped/failed assessment 可审计。
- [x] 2.5 实现 v2 跨字段 contract validator，拒绝重复 ID、悬空 occurrence/step/edge/path/impact/diagnostic refs、complete chain 含 break、partial/unknown chain 无 break、计数不一致、非法路径、缺失双语字段和非法扩展。
- [x] 2.6 固定 v2 集合排序、ID/semantic digest 输入和结果大小截断算法，保证不同并发顺序、绝对工作区、artifact root、locale、缓存冷热和展示文本变化不改变语义身份。

## 3. 切换 CLI 与运行时输出

- [x] 3.1 让 application 正常、partial 和 failed 路径统一构建结果 v2，并保持十类规则、facts-only、unknown 分母、suppression 和退出码语义不变。
- [x] 3.2 让 CLI usage、JSON/Schema 错误、invalid request 和 internal error 路径也通过同一 v2 projector 输出可校验最小结果，禁止输出临时旧形状或堆栈。
- [x] 3.3 更新协议注册、`validate` 命令、原子写出和 response/result size budgets，使最终文档必须先通过 Schema、引用规则及不变量校验再发布。
- [x] 3.4 删除旧 scan-result 1.4 Schema、旧结果构建/serializer、结果版本选择或 fallback，并增加负向校验证明旧结果只会以稳定 unsupported-result-version 诊断被拒绝。

## 4. 原子迁移项目内消费者

- [x] 4.1 将 validation corpus、oracle、结果解析和逐规则 TP/FP/FN/exact-match 计算切换到 v2 finding、assessment extension 和 evidence-chain 语义。
- [x] 4.2 将 benchmark runner、冷/热缓存语义投影、不同工作区确定性比较和结果大小统计切换到 v2，排除 telemetry/展示文本但保留全部风险与失败语义。
- [x] 4.3 更新全部测试 helpers、golden fixtures、examples、README 和协议/benchmark 文档，说明 v2 是唯一结果协议且没有迁移或兼容路径。
- [x] 4.4 全仓检查非归档代码和测试辅助代码中的旧结果字段、`schema_version: "1.4"` 结果断言和兼容 fallback；除明确负向 fixture/变更说明外全部移除。

## 5. 单元与合同测试

- [x] 5.1 为 projector、summary、finding、occurrence、evidence chain、extensions、diagnostics 和 serializer 增加正常行为、空集合、聚合及边界单元测试。
- [x] 5.2 为悬空引用、重复 ID、错误 primary occurrence、循环/断裂 path、非法 namespace、缺失双语字段、计数冲突、越界路径和输出大小耗尽增加异常与 partial/unknown 单元测试。
- [x] 5.3 为十类规则分别验证 deterministic/heuristic finding 的 v2 投影、稳定 ID、人工确认、validation plan、AST-only、共享 BC 和 AST↔IR evidence chain，不改变规则检测结论。
- [x] 5.4 为 suppression applied/expired/unmatched/budgetUnrecorded、policyAsOf、cache hit/miss/corrupt/write、预算 frontier、原子写失败和旧文件保留增加 v2 断言。
- [x] 5.5 增加 CLI 五种终态及退出码、重复运行、不同绝对根、不同并发顺序、冷/热缓存、仅展示文本变化和旧 v1.4 结果拒绝的合同测试。

## 6. 完整质量验收

- [x] 6.1 运行 `python -m ruff check src tests`、`python -m mypy`、全部 Python 单元/contract 测试及 C++ 单元测试，修复所有失败且不得以集成测试替代单元测试。
- [x] 6.2 使用覆盖率配置统计 `src/floating_point_precision_scanner` 和 `src/cpp` 全部项目自有可执行源码（包含未被测试加载的文件），确认项目整体及受影响模块的行覆盖率和分支覆盖率分别至少 90%，并生成 JSON/HTML/XML 报告。
- [x] 6.3 运行完整 reviewed validation corpus，确认逐规则 strict precision/recall 均至少 90%、整体 exact match 至少 95%、失败/预算/cache/suppression 生命周期 case 100% exact match，并验证结论与旧实现语义一致而非验证旧 JSON 形状。
- [x] 6.4 在固定容器环境运行 S/M/L 冷/热缓存 benchmark 和不同工作区确定性检查，确认资源/回退门禁、结果大小预算、stable IDs、排序及 semantic digest 全部通过。
- [x] 6.5 运行严格 OpenSpec 校验并生成 verification 报告，列出全部命令、测试数量、逐规则质量指标、benchmark、Python/C++ 整体及受影响模块行/分支覆盖率、统计范围、排除项和报告位置；任一未执行或未达标项保持未完成。
