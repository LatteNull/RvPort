## 1. 固化阶段基线与迁移边界

- [x] 1.1 记录当前 `cli.py → compile_commands/parse_project/rules/report` 调用链、61 项容器测试、24 个 YAML 规则和三个 artifact 基线。
- [x] 1.2 验证 `archive/2026-09-04-pre-rewrite` 的 154 个历史文件和聚合哈希，并增加测试确保 archive 不进入默认模块、输入或 unittest discovery。
- [x] 1.3 为代表性源码、compile context、RPM、inactive branch、portable alternative 和 comment hint fixture 固化 Finding 语义基线，至少覆盖 rule ID、类型、severity、blocking、文件、行号和关键 trace。
- [x] 1.4 固化当前 CLI 成功、规则加载失败和 compile context 降级的退出码与 diagnostic 行为，作为新入口的兼容合同。

## 2. 建立核心领域对象

- [x] 2.1 创建 `kb_scanner/core` 包及清晰导出边界，确保核心模块只依赖 Python 标准库和 scanner 自有类型。
- [x] 2.2 实现项目相对 SourceLocation/SourceSpan 值对象及路径规范化，拒绝把机器绝对路径写入稳定身份材料。
- [x] 2.3 实现统一稳定 ID factory，使用规范化 tuple 和完整小写 SHA-256，并验证相同输入跨项目绝对路径产生相同 ID。
- [x] 2.4 实现不可变 slots `Entity`、`Evidence`、`Relation`、`Observation` 和最小通用 `Assessment`，限制 metadata 为 JSON-safe 数据。
- [x] 2.5 实现只读 `ScanContext` 及其 CLI 参数规范化构造器，显式包含目标架构、输入/输出、过滤选项、compile context、rule/knowledge identity 和 scanner 版本。
- [x] 2.6 实现结构化 `Diagnostic`、completion status、`StageResult`、artifact identity 和 `PipelineResult`，明确 partial/unknown、fatal 和 `affects_exit_code` 语义。
- [x] 2.7 增加核心对象合同测试，覆盖不可变性、slots、稳定身份、provenance、引用完整性、JSON-safe metadata 和确定性排序。

## 3. 定义 Runner、阶段 Protocol 与 Profile

- [x] 3.1 定义统一 `PipelineRunner` protocol 和 `ScanApplication` 调用边界，使 CLI 不再直接编排具体 parser、rule evaluator 和 reporter。
- [x] 3.2 定义 Workspace Collector、Frontend、Knowledge Provider、Normalizer、Analyzer、Detector、Classifier、Assessor 和 Report Projector protocol，输入输出只引用 core 合同和泛型 StageResult。
- [x] 3.3 实现显式 `PipelineProfile` 组件集合和构造校验，不引入服务定位器、动态 plugin registry 或模块级可变组件状态。
- [x] 3.4 增加 import-boundary 测试，禁止 `core`/`pipeline` 导入 Tree-sitter、Clang、NetworkX、Pydantic、legacy `ProjectFacts` 或 legacy `Finding`。

## 4. 实现 StagedPipelineRunner 编排合同

- [x] 4.1 实现 `StagedPipelineRunner` 的固定阶段顺序和前序值传递，确保只有 Report Projector 可以写入正式 artifact。
- [x] 4.2 实现 diagnostic 稳定聚合、允许降级、依赖阶段跳过、partial/unknown 传播和内部不变量 fatal 处理。
- [x] 4.3 使用 recording/no-op stages 验证调用顺序、统一 ScanContext、显式依赖注入和 PipelineResult 汇总，不调用当前真实 parser。
- [x] 4.4 增加失败矩阵测试，覆盖可选增强失败、必需值缺失、projector 失败和重复/无序 diagnostic，确认不会伪造完整成功结果。

## 5. 接入 LegacyCompatibilityProfile

- [x] 5.1 从当前 CLI 编排中提取无行为变化的 context 构造边界，保持现有参数默认值、路径解释和 compile_commands 发现规则。
- [x] 5.2 实现 adapter-private `LegacyPipelineRunner`/`LegacyRunState`，按当前顺序调用 compile command loader、规则/知识加载、`parse_project()` 和 `evaluate_rules()`。
- [x] 5.3 实现私有 `LegacyReportProjectorAdapter` 调用现有 `write_reports()`，向 PipelineResult 返回三个 artifact 的确定性路径和身份，不重复构造第二份结果 payload。
- [x] 5.4 让 `ScanApplication` 的默认 profile 选择 LegacyPipelineRunner，并让 `kb-scanner scan` 通过新应用入口执行；保留 validate-rules、list-rules 和 version 的现有行为。
- [x] 5.5 将 legacy diagnostic 映射为结构化 Diagnostic，同时保持哪些错误影响 CLI 退出码、哪些情况只降级提示的现有语义。
- [x] 5.6 验证 legacy `ProjectFacts`、legacy `Finding` 和私有 adapter state 未出现在 core/staged protocol 的公开类型注解、返回值或报告结构中。

## 6. 验证行为与数据兼容

- [x] 6.1 在独立 `kb-scanner-test` 容器中运行全部现有测试及本 change 新增测试，所有失败均产生非零容器退出码。
- [x] 6.2 对阶段 1.3 的语义基线运行新 CLI 入口，确认关键 rule ID、Finding 分类、blocking、位置、reason/suggestion 和 trace 无非预期差异。
- [x] 6.3 验证 `schemaVersion: "1.0"`、六个现有顶层字段及 `scan-result.json`、`scan-report.html`、`scan.log` 三个 artifact 保持兼容，且没有第二个主结果文件。
- [x] 6.4 验证 Clang/GCC 两份生成事实文件的 SHA-256、六类计数、来源和 `generatedSet` 行为均未改变。
- [x] 6.5 验证缺少或无效 `compile_commands.json` 时仍继续静态扫描并产生原有降级 diagnostic，不能把缺失证据解释为 RISC-V ready。
- [x] 6.6 验证新应用入口没有执行 Make、Autoconf、RPM、CMake、编译器插件、真实编译或项目测试，也没有扩大到 OS/内核/驱动迁移分析。

## 7. 文档、容器与 OpenSpec 收尾

- [x] 7.1 更新 KB Scanner 开发文档，说明 core/pipeline/adapters 边界、默认 legacy profile、后续 staged profile 替换方式和禁止直接修改历史快照的规则。
- [x] 7.2 将 `docs/kb-scanner-rewrite-development-plan.md` 的阶段 1 状态、实际偏差和后续阶段入口更新为实施结果。
- [x] 7.3 仅通过 `tools/kb-scanner/compose.test.yml` 构建和运行正式验证，确认宿主机未安装扫描依赖，`backend/Dockerfile`、根 Compose 和生产镜像没有变化。
- [x] 7.4 运行 `openspec validate establish-kb-scanner-core-pipeline --strict` 并修复全部规格格式或一致性问题。
