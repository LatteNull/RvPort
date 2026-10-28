# 内存序结果前端交接

交接日期：2026-10-28。此文件是接口说明和建议工作清单，不是 memory-order-analyzer change 的实施规格或任务。请在 D:/projects/RvPort/frontend/ 自己的 OpenSpec root 管理前端修改，文件修改仅限前端 root；接口缺口另行反馈，不从工具 root 修改前后端。

## 已提供的合同

- 新分析输出为 MemoryOrderFindingProjection 3.0，顶层 finding_schema_version=3.0；历史 2.0 继续可读。协议版本与软件/C++ 标准版本无关。
- conclusion.evidenceLevel 为 source-only、incomplete、bounded-model；confidence=null 表示未评估，不能转换成 0%、50% 或 100%。
- API findingKind 区分 FINDING、SOURCE_CANDIDATE、INCONCLUSIVE、DISCHARGED；原始投影保存在 detail。请以结果类型/verdict 判定语义，不按 severity 单独分类。
- API summary 提供 diagnosticCount、frontierCount、primaryDiagnostic、diagnostics、diagnosticsTruncated、diagnosticsAggregated、diagnosticsDownload。历史未汇总时 diagnosticCount 可为 null。原始工具报告的 diagnostics_total/frontier_total 是截断前分母，完整超预算诊断在审计包 diagnostics/full.json。
- Workflow 的 PARTIAL 仍可能对应任务 SUCCEEDED、节点 DONE，同时提供 analysisStatus=PARTIAL、analysisComplete=false、reasonCode=MEMORY_ORDER_PARTIAL、message/messageEn。
- 报告区分 pendingVerification 与正式风险，并提供 memoryOrderAnalysis 的分析局限。以上 API 字段来自本次既有后端修改，联调前请确认所连环境已经部署对应版本；历史记录缺字段需明确显示未知。

## 请前端处理

1. **列表与空态**：区分正式风险、待核实候选、证据不足和受限消解。候选不显示中风险或概率，不进入正式风险统计；旧 medium/0.5 候选也按 kind/verdict 保守展示。读取内存序 conclusion.reason/detail 及双语字段，不依赖浮点专用 impact。零结果且 PARTIAL 显示“暂无可展示结果，分析未完成”及原因。
2. **诊断**：概览展示主要根因和可展开明细，保留完整下载入口。分别表达诊断与 frontier，处理仅 frontier、截断、历史未汇总、加载失败；null/缺字段不能显示为零。
3. **证据链**：用 steps.id 建索引，按 primaryPath 顺序渲染主链，edges 渲染其他分支，breaks 渲染断点/期望证据/建议及预算。steps 数组顺序只是存储顺序。缺引用、环或未知 kind 显示结构异常并保留可验证片段，不能补造完整链。
4. **源码定位**：切换 occurrence/step 时校验对应源码 digest 和位置，不借用其他位置片段。无直接源码的推理/断点明确显示该状态，保留合理代码上下文交互。
5. **状态与报告动作**：任务执行完成不等于分析完整；PARTIAL 显示“部分分析完成”警告。候选默认待确认，人工纳入后仍为待核实，不能升级 severity/verdict 或正式风险计数。新 run 的候选重新待确认，历史确认选择不代表分析已证实；零正式风险不能显示“迁移安全”。
6. **回归验证**：覆盖新旧协议、null confidence、frontier-only、乱序 steps、多分支、缺引用/环、无源码断点、历史 CONFIRMED、新 run、PARTIAL 零结果，以及共用浮点/知识库组件。补组件/适配器单元测试，在前端 Docker 环境执行 lint、类型检查、全量普通单元和生产构建，覆盖率遵循前端 root 的现行约定；保留键盘焦点、桌面布局、对比度和减少动画偏好。

## 可参考的分析器验证边界

工具 884 项 Python 单元、118 项 C++ 单元和 98 项集成通过。离线 API 流程验证了普通循环不导入为候选、原子源码产生 2 个候选/18 条诊断/0 个正式风险、PARTIAL 状态、人工纳入不升级结论，以及重跑后原始制品和旧报告不变。这些结果不替代前端展示和交互验收。

工具合同见 [结果协议](../../../../doc/MEMORY_ORDER_FINDING_SCHEMA.zh-CN.md) 和 [统一入口](../../../../doc/UNIFIED_PROJECT_ANALYSIS.zh-CN.md)。