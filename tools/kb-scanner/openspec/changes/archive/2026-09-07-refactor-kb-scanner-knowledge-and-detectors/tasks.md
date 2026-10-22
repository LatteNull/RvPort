## 1. 固化阶段起点与能力矩阵

- [x] 1.1 记录当前 41 项 frontend isolated unit、97.84% 行覆盖、95.38% 分支覆盖及 126 项 full regression 基线，保留 unit/component/integration/contract 分层。
- [x] 1.2 固化默认 CLI 成功/规则失败/compile-context 降级、`schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和三个 artifact。
- [x] 1.3 固化 legacy 五文件字节，以及 Clang/GCC 事实 JSON 的 SHA-256、六类计数、完整 `source`；另以默认 legacy CLI 回归保护 24 个 YAML 和 `generatedSet` 行为，但不把它们作为新 Provider 输入。
- [x] 1.4 建立需求/fixture 驱动的机器可读 behavior acceptance matrix，将 C/C++ 迁移能力标记为 generated-fact-local、structural-candidate、needs-curated-knowledge、needs-graph、needs-build、needs-packaging 或 needs-classification，不建立逐 YAML rule migration inventory。
- [x] 1.5 建立机器可读 knowledge/detection test inventory，将全部新增或修改业务模块双向映射到 isolated unit 与适用高层测试。

## 2. 扩展 scanner 自有 Core 合同

- [x] 2.1 新建 `core/knowledge.py`，定义不可变、slotted、JSON-safe 的 KnowledgeSource 和 KnowledgeEntry，并实现不含机器根路径的稳定 ID 规则；DetectorDefinition 不进入 KnowledgeSnapshot。
- [x] 2.2 为 `core/knowledge.py` 增加 isolated unit tests，覆盖有效/无效字段、来源冻结、重复顺序、identity version 和跨 checkout 稳定性。
- [x] 2.3 新建 `core/facts.py`，定义 NormalizedFact 的 subject、canonical value、Evidence/context provenance、semantic scope 和稳定身份合同。
- [x] 2.4 为 `core/facts.py` 增加 isolated unit tests，覆盖源码 span、compile-context scope、重复引用去重、非法引用和 JSON-safe metadata。
- [x] 2.5 以默认空 tuple 扩展 KnowledgeSnapshot、NormalizedSnapshot 和 Observation 的 sources/entries、facts 与 knowledge IDs，并更新相关 protocol/type export。
- [x] 2.6 为 `core/results.py`、`core/observations.py`、`core/protocols.py` 和 public exports 增加/扩展 isolated unit tests，证明旧构造兼容、引用校验与实现技术隔离。
- [x] 2.7 增加 core 合同测试，禁止 YAML/Pydantic/parser/legacy Rule 类型进入 pipeline protocol 或 Snapshot 公共字段。

## 3. 建立 Generated-facts-only JSON Manifest、Schema 与 Identity

- [x] 3.1 定义带 `schemaVersion` 的严格 JSON manifest，只允许 catalog identity/version 与 generatedSources 的 sourceId/path/sha256，不复制两份生成 JSON 的条目。
- [x] 3.2 新建 `knowledge/schema.py`，以 `extra=forbid` 的 JSON 边界模型严格验证 manifest 与生成事实 shape，并显式拒绝 `curatedSets`、detectors、operator、regex、severity/blocking/message 等字段。
- [x] 3.3 为 `knowledge/schema.py` 增加 isolated unit tests，覆盖有效最小/完整 manifest、root 类型、缺失 schema/identity/version、错误哈希、非标量生成条目、`curatedSets` 和额外字段。
- [x] 3.4 新建 generated-facts manifest，只声明 Clang/GCC 两份现有 JSON 的逻辑来源与固定 SHA-256；不得创建空 curated 数组、示例条目或 detector recipe。
- [x] 3.5 增加 behavior acceptance matrix 合同测试，确保当前支持项具有有效 generated fact/structural basis，延后项有明确 reason，且矩阵不依赖 YAML rule ID。
- [x] 3.6 新建 `knowledge/identity.py`，实现 fact kind/value canonicalization、逻辑 source identity、内容摘要及 KnowledgeSource/Entry/Snapshot 稳定身份。
- [x] 3.7 为 `knowledge/identity.py` 增加 isolated unit tests，覆盖大小写敏感符号、路径分隔符、空白、来源排序、Windows/POSIX checkout 和 JSON `source` 主机路径去身份化。
- [x] 3.8 确认 manifest schema 与 identity 只使用现有锁定依赖和标准库 JSON，不修改 runtime lock、生产镜像或宿主机环境，并且新路径不使用 PyYAML。

## 4. 实现正式 Knowledge Provider

- [x] 4.1 新建 `knowledge/provider.py`，按 manifest 声明和逻辑 POSIX 路径确定性安全读取 JSON manifest 与生成 JSON，不读取现有 legacy YAML、不调用 legacy loader/evaluator。
- [x] 4.2 实现六类 generated facts 加载与同 category/canonical value 合并，保留 Clang/GCC 两个逻辑来源及原 `source` provenance。
- [x] 4.3 实现 manifest source/path/hash 校验、六类 category 到 KnowledgeEntry 的转换和 source provenance 聚合，并拒绝未声明 source/category。
- [x] 4.4 实现不存在/不可读文件、invalid JSON、source shape/hash 无效、manifest 失败和部分有效输入的 complete/partial/failed Diagnostic。
- [x] 4.5 为 `knowledge/provider.py` 增加 isolated unit tests，使用临时目录/fake payload 覆盖发现顺序、合并来源、引用完整性、异常降级、Diagnostic 去敏与重复执行稳定性。
- [x] 4.6 增加真实 manifest component test，验证 schema/identity/version、固定哈希、两类逻辑 source 与六类生成事实可加载，且 `curatedSets` 不存在。
- [x] 4.7 验证 Provider 不修改 manifest、legacy YAML 或生成 JSON，不执行 include、command、plugin、response file 或任何项目代码。

## 5. 补齐 Frontend Attribute Evidence

- [x] 5.1 在正式 C/C++ vocabulary 中增加 `declaration_attribute` kind，保持现有 Evidence identity、排序和 public API 合同。
- [x] 5.2 扩展 Tree-sitter adapter，只对可稳定定位的 GNU/MSVC/C++ declaration、target、target_clones 和 vector_size attribute 产生有界文本 Evidence。
- [x] 5.3 扩展现有 vocabulary/Tree-sitter isolated unit tests，覆盖 C/C++ fake node、字段/回退值、source span、截断、ERROR/MISSING confidence、去重与非 attribute 排除。
- [x] 5.4 增加真实 grammar component fixtures，验证 target attribute、固定 vector width、不完整 attribute 和普通 declaration 的行为。
- [x] 5.5 更新 frontend test inventory，并确认不新增所有 identifier/整文件文本 Evidence、不在 Frontend 内判断 x86 或 blocking。

## 6. 实现 C/C++ Evidence Normalizer

- [x] 6.1 新建 `normalization/cpp.py`，将 include、call/symbol、type、macro/preprocessor、inline asm、comment 和 declaration attribute Evidence 转换为 kind-specific canonical facts。
- [x] 6.2 实现从只读 CompilationUnitContext tokens 产生 compiler-argument 派生 Evidence/Fact，记录 context identity 与 token index，不重新 tokenization raw command。
- [x] 6.3 实现等价事实的 Evidence/producer/context provenance 稳定聚合，保留原 Entity/Evidence，并避免宽泛文本或不同 semantic scope 的错误合并。
- [x] 6.4 实现未知 Evidence kind、无匹配 subject、无效 span/context 和单项 canonicalization 失败的 partial/failed Diagnostic 边界。
- [x] 6.5 为 `normalization/cpp.py` 增加 isolated unit tests，覆盖全部 kind、路径/包围符号/空白规范化、大小写语义、有界文本、跨 producer 聚合和稳定排序。
- [x] 6.6 增加 compiler argument isolated unit matrix，覆盖 flag/define/include/target、重复 token、多 context、危险参数仅作为文本、response/plugin 不读取及跨机器 identity。
- [x] 6.7 增加 FrontendSnapshot 到 NormalizedSnapshot component test，确认可选 Clang 缺失不改变 baseline fact identity且缺失证据保持 unknown。

## 7. 实现 Local Matcher 与 Detector

- [x] 7.1 新建 `detectors/definitions.py`，以只读 Python registry 定义稳定 detector ID、输入 fact kind、Observation kind 和 matcher binding，不从 manifest/YAML 加载 recipe。
- [x] 7.2 为 `detectors/definitions.py` 增加 isolated unit tests，覆盖重复 ID/binding、未知 fact kind、确定顺序和 registry 不可变性。
- [x] 7.3 新建 `detectors/matchers.py`，建立 category index，并实现 headers、intrinsics、builtins、vectorTypes、platformMacros 和 compilerFlags 的事实支持 exact/token local matchers。
- [x] 7.4 实现 comment 中已知事实的 `hint`，以及 inline asm/declaration attribute/模糊标识的 structural `candidate`/unknown；禁止用未经审校的 CPU API、指令/寄存器、target 或架构别名词表产生 confirmed 命中。
- [x] 7.5 为 `detectors/matchers.py` 增加 isolated table-driven unit tests，覆盖六类正例、近似反例、边界文本、大小写、token boundary、结构候选、重复来源和确定顺序。
- [x] 7.6 新建 `detectors/local.py`，只消费 core Snapshot，通过 matcher registry 生成带有效 Evidence/Knowledge 引用的 confirmed_local/candidate/hint Observation。
- [x] 7.7 实现 Observation 稳定 ID/排序/去重、跨 producer/knowledge source 聚合，以及未知 subject/evidence/knowledge 引用的 failed Diagnostic。
- [x] 7.8 根据 behavior acceptance matrix 对缺少 curated knowledge、关系、构建选择、打包、测试选择和目标可达性的能力产生带 reason 的 deferred/unknown Diagnostic，保留已确认局部 Observation。
- [x] 7.9 为 `detectors/local.py` 增加 isolated unit tests，覆盖空输入、精确命中、结构候选、混合状态、引用失败、重复输入、deferred capability 和输入排列稳定性。
- [x] 7.10 增加职责边界合同测试，确认 Detector 不导入 legacy `rules.py`/DTO、不产生 Finding/Relation/Assessment、不应用 legacy severity/blocking。

## 8. 接入 Staged Qualification

- [x] 8.1 建立 qualification profile，注入真实 Workspace、Frontend、Knowledge Provider、Normalizer 和 Local Detector，并为 Analyzer/Classifier/Assessor/Projector 使用 recording/no-op 实现。
- [x] 8.2 增加 staged integration test，验证同一个只读 ScanContext、固定调用顺序、真实 Snapshot 传值及 Observation 的 Evidence/Knowledge 引用。
- [x] 8.3 覆盖 Provider/Normalizer/Detector partial 与 required-value failed 的状态传播，确认局部结果保留、dependent stages 正确停止且缺口不表示 ready。
- [x] 8.4 验证 qualification Projector 返回空 artifact 且不写文件，默认 ScanApplication/CLI 仍选择 legacy compatibility profile。
- [x] 8.5 使用代表性 header/intrinsic/builtin/vector/macro/flag/asm/API/attribute/comment fixture 验证 behavior acceptance matrix：六类 generated facts 精确命中，缺少 curated knowledge 的项只产生 candidate/unknown/deferred。
- [x] 8.6 明确普通变量/枚举缺少正式 Frontend Evidence 时保持 unknown，不允许 Detector 通过 regex 重扫源码补齐。

## 9. 单元覆盖率与容器回归

- [x] 9.1 扩展测试 runner，先独立运行 knowledge/detection unit gate，再运行 frontend unit gate和 top-level full regression，任一步失败均非零退出。
- [x] 9.2 使新增/修改 knowledge、normalization、detector、core 和 frontend 业务模块分别满足行覆盖率至少 90%、分支覆盖率至少 80%，且每个 inventory 模块有 executed lines。
- [x] 9.3 增加 inventory 悬空、模块缺失、行门槛不足、分支门槛不足和模块零执行时 runner 失败的测试。
- [x] 9.4 将所有 coverage data/JSON 限定在容器 `/tmp`，保持唯一 `kb-scanner-test` 服务、只读 workspace、无网络和无业务凭据。
- [x] 9.5 在独立测试容器运行全部 isolated/component/integration/contract tests，确认阶段起点 41 项 frontend unit 和126 项 full regression 不减少。
- [x] 9.6 回归默认 CLI、结果 schema/字段/Finding/三个 artifact、legacy 五文件、现有 24 个 YAML/`generatedSet` 以及两份事实数据哈希/计数/source 全部不变，并证明新 Provider 对 YAML 零读取。
- [x] 9.7 更新开发计划、knowledge/detection baseline、测试分层和容器文档，记录 `curatedSets` 当前不存在及后续独立 change `collect-kb-scanner-curated-knowledge-sets`，并分别记录各 unit gate 数量、逐模块覆盖率、高层测试数和 full regression 总数。
- [x] 9.8 确认未安装宿主机依赖，未修改/构建生产镜像或根 Compose，未执行 compiler、构建、配置、plugin、response file、项目测试或真实 RISC-V 编译。
- [x] 9.9 运行 `openspec validate refactor-kb-scanner-knowledge-and-detectors --strict` 并修复全部格式和一致性问题。

## 10. 真实 x86-only 项目长行回归修复

- [x] 10.1 为 `_node_span()` 增加 isolated unit regression，模拟重复读取会变化的原生 Point，证明 start/end Point 各只读取一次并复制为稳定整数。
- [x] 10.2 最小修复 Tree-sitter adapter 的 SourceSpan 构造，不修改 core、legacy parser、规则或知识数据。
- [x] 10.3 增加 365 列级单行调用的真实 grammar component regression，并在独立测试容器中复扫 `AVX-AVX2-Example-Code` qualification，确认 Frontend、Normalizer 和 Local Detector 可完成。
- [x] 10.4 重跑全部容器门禁，更新测试数字和真实项目验证记录，并再次通过 `openspec validate refactor-kb-scanner-knowledge-and-detectors --strict`。
