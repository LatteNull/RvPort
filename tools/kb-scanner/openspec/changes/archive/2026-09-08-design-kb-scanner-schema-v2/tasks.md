## 1. 冻结设计输入与词汇

- [x] 1.1 盘点 schema 1.0 的顶层字段、Finding/summary/Diagnostic 语义、三个 artifact、默认 CLI 与后端消费者，形成不可误删的 v1 compatibility baseline。
- [x] 1.2 冻结 schema v2 的 Finding/fact/conclusion/occurrence/evidenceChain 词汇、内部引用、完成状态、reason code、step kind、selection status、静态范围声明和稳定排序规则。
- [x] 1.3 明确 Finding 自包含详情、项目 summary 与顶层 Diagnostic 的职责边界，确认不重新引入自由形态 `trace`，也不要求消费者通过顶层 Explanation/Catalog 拼装详情。

## 2. 生成 schema v2 合同资产

- [x] 2.1 创建 JSON Schema 2020-12，定义 `schemaVersion: "2.0"`、scan/project/summary、Finding fact/conclusion/occurrences/evidenceChain、结构化 Diagnostic 和命名空间化 extensions 的封闭字段合同。
- [x] 2.2 编写独立的 Finding 内引用完整性规则，覆盖 step/occurrence ID 唯一性、primaryPath 和 edge 端点、break candidate、primary occurrence、Assessment impact、底层 provenance 和无悬空引用。
- [x] 2.3 创建 complete、partial、ambiguous、inactive、unknown 的最小正例及定向无效反例，确保每个状态均能明确表达断点而不伪造安全结论。
- [x] 2.4 创建人工审计的 AVX Finding 详情示例，至少覆盖 selected build/source → intrinsic/宏 replacement → compiler knowledge → Classification → Assessment 的主链、分支、occurrence 和每个代码型 step 的逐行上下文/命中高亮。
- [x] 2.5 在 schema 资产中声明每个 Finding 只序列化实际引用的紧凑 KnowledgeEntry projection，并以合同检查冻结两份 Clang/GCC compiler facts 的 bytes/SHA-256、分类和 provenance 不变。

## 3. 固化消费者与迁移设计

- [x] 3.1 编写 v1/v2 合同差异与消费者迁移清单，区分同源内部事实、消费者字段变化、v2-only 字段和不可无损表达项，并明确 v2 直接从 staged snapshots 生成而不转换 v1。
- [x] 3.2 编写 Finding 摘要/详情消费示例，验证详情消费者可一次取得完整 Finding，先沿 `evidenceChain.primaryPath` 渲染带行号和代码上下文的主链，再展开同一对象中的其他 step、edge、候选、occurrence、break 和 Diagnostic。
- [x] 3.3 固化单次扫描单版本输出规则、显式版本选择、v1 默认保持、v2 失败不回退、三个 artifact 同步和回滚到 v1 的合同。
- [x] 3.4 将后续工作拆分为独立 implementation、backend-consumer、frontend-explainability 和 default-cutover change，禁止在本设计 change 中修改 scanner runtime 或前端。

## 4. 设计资产验证与文档

- [x] 4.1 创建 schema-v2 机器可读测试 inventory，并为 JSON Schema 校验、Finding 内引用完整性、代码上下文/高亮、确定性排序、v1/v2 合同差异和 facts 冻结分别登记测试入口与边界。
- [x] 4.2 在 tests 范围实现纯合同验证 helper/test，使用内存对象与 fixture 覆盖全部正反例；不得接线生产 serializer、mapper、CLI 或 renderer。
- [x] 4.3 只在独立 `kb-scanner-test` 容器中运行新增合同测试和完整回归，确认未修改生产镜像、根 Compose、默认 schema 1.0 输出或外部状态，并清理测试容器。
- [x] 4.4 更新 schema v2 设计文档，记录 Finding 自包含结构、点击后的主链/分支展开、逐步代码上下文、partial/ambiguous 展示义务、静态分析边界、迁移阶段和未决问题。
- [x] 4.5 运行 `openspec validate design-kb-scanner-schema-v2 --strict`，确认 proposal/design/spec/tasks 一致且本 change 仅交付设计与合同资产。
