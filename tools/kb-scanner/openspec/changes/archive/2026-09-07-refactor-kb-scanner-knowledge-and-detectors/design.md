## Context

前两个实现阶段已经建立 scanner 自有 core/pipeline 合同和正式 C/C++ Frontend。Frontend 当前返回 source file Entity、带 producer/context/span 的 Evidence 和结构化 Diagnostic；默认 CLI 仍通过整体 legacy runner 调用冻结的 `rules.py`。现有 `rules.py` 同时承担 YAML/生成事实加载、局部文本匹配、构建上下文、替代实现、目标可达性、严重程度和 Finding 去重，不能作为后续关系图和分类阶段的稳定边界。

本阶段要把“知道哪些 x86 事实”和“在局部输入中看到了什么”拆开。它不负责回答该命中在 RISC-V 目标上是否可达、有无替代实现、是否阻断或项目是否 ready。现有 24 个规则及 fixture 仍由默认 legacy CLI 提供兼容行为；新的 staged qualification 只验证 Knowledge、Normalization 和 Local Detection 的真实数据流。

固定约束包括：只做 C/C++ 软件静态分析；忽略 OS/内核/系统调用/驱动/板级迁移；不把 `uname` 的交叉编译误选分支纳入问题模型；不执行 compiler、构建、配置、plugin、response file 或项目测试；不改变现有结果结构和三项 artifact；不修改五个冻结 legacy 文件；两份编译器事实 JSON 必须保持原字节、六类计数、source 和哈希。

## Goals / Non-Goals

**Goals:**

- 建立 scanner 自有且不可变的 KnowledgeSource、KnowledgeEntry、NormalizedFact 及其 Snapshot 表达。
- 从 generated-facts-only JSON manifest 和两份生成 JSON 构造确定、可追溯的 KnowledgeSnapshot；重复事实合并但来源不丢失。
- 让新 Provider 和 Detector 对现有 24 个 legacy YAML 保持零依赖；用面向行为的验收矩阵记录支持、缺少 curated knowledge、需要关系分析和需要分类的能力，不建立逐 YAML rule 迁移清单。
- 将 Frontend Evidence 和只读 CompilationUnitContext 归一为稳定事实，保留全部原始 Evidence 和 compilation context provenance。
- 用 code-owned definition 和纯局部 matcher 生成 Observation，对两份事实 JSON 已覆盖的入口提供精确匹配，并明确 confirmed-local、candidate、hint 和 deferred 的差别。
- 让 staged qualification 运行真实 Workspace、Frontend、Knowledge、Normalizer 和 Local Detector，证明后续组件无需读取 YAML、parser 对象或 legacy DTO。
- 为所有新增或修改模块同步建立隔离单元测试映射，以及容器内行覆盖率至少 90%、分支覆盖率至少 80%的门禁。

**Non-Goals:**

- 不实现跨文件宏展开链、include 可达性、替代实现、sibling branch 或 Evidence Graph。
- 不求值 C/C++、Make、Autoconf、RPM 或 CMake 的架构选择关系。
- 不决定 severity、blocking、inactive、portability-gap、最终 Finding 或 readiness。
- 不实现可执行的通用规则 DSL；JSON manifest 只描述事实来源，Detector definition 和 matcher 由 Python 代码维护。
- 不修改现有 legacy YAML；它们继续服务默认 CLI 和兼容回归。
- 不创建、采集或接入 `curatedSets`；该工作由后续独立 change `collect-kb-scanner-curated-knowledge-sets` 完成。
- 不切换默认 CLI，不写正式 artifact，不删除 legacy 路径。
- 不执行真实 RISC-V 编译或被扫描项目测试，也不覆盖操作系统迁移。

## Decisions

### 1. 使用 scanner 自有知识与归一事实类型

新增 `core/knowledge.py` 定义不可变 `KnowledgeSource` 和 `KnowledgeEntry`；新增 `core/facts.py` 定义 `NormalizedFact`。`KnowledgeSnapshot` 增加 sources/entries，`NormalizedSnapshot` 增加 facts，`Observation` 增加显式 `knowledge_ids`，字段均使用默认空 tuple 保持内部构造兼容。所有 ID 使用规范化领域材料生成的完整 SHA-256，不包含机器根路径、mtime、对象地址或随机值。

KnowledgeEntry 的身份由 fact kind、architecture family 与 canonical value 决定，source 列表不进入身份，因此 Clang/GCC 中重复条目可以共享事实身份并合并来源。Detector definition 不属于 KnowledgeSnapshot：稳定 detector ID、接受的 NormalizedFact kind、Observation kind 和匹配函数由 `detectors/definitions.py` 中的只读代码注册表声明。NormalizedFact 的身份使用事实 kind、subject、canonical value 和语义作用域：源码事实使用项目相对 span，编译参数事实使用 compilation context identity 与 token ordinal。producer 和 evidence 列表不进入事实身份，避免可选 Clang 可用性改变同一局部事实的 ID。

选择新增 core 类型而不是把 dict、Pydantic model、catalog recipe 或 legacy Rule 放入 Snapshot，是为了保持 pipeline protocol 与具体文件格式/验证技术解耦。替代方案是只传路径并让 Detector 重读文件；这会让 Detector 同时承担 I/O、验证和匹配，故拒绝。

### 2. 使用 generated-facts-only JSON manifest，不预设尚不存在的 curatedSets

模块划分如下：

- `knowledge/schema.py`：Pydantic 边界模型，严格验证 JSON manifest、generated source 和两份生成 JSON；未知字段使用 `extra=forbid`，新路径只使用标准库 JSON 解析。
- `knowledge/provider.py`：确定排序地读取 JSON manifest 和生成 JSON，校验逻辑来源、版本与内容摘要，构造 core Knowledge 类型和 Diagnostic。
- `knowledge/identity.py`：canonical value、稳定知识 ID、逻辑 source identity 和内容摘要；现有 JSON `source` 原值只作为 provenance 保存，不进入稳定 ID。

manifest 不复制现有几千条编译器事实，只声明当前真实存在的两份 generated source。示意结构如下：

```json
{
  "schemaVersion": "1.0",
  "catalogId": "riscv-porting-x86-facts",
  "version": "2026.09",
  "generatedSources": [
    {
      "sourceId": "clang-x86-entries",
      "path": "generated/clang-x86-entries.json",
      "sha256": "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7"
    },
    {
      "sourceId": "gcc-x86-entries",
      "path": "generated/gcc-x86-entries.json",
      "sha256": "89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9"
    }
  ]
}
```

v1 schema 明确没有 `curatedSets`、detectors、operator、regex、severity、blocking、reason、suggestion 或 locale message。缺失字段不通过空数组伪装成已有数据，未知字段直接拒绝。未来 curated 数据必须由 `collect-kb-scanner-curated-knowledge-sets` 定义独立、可溯源的事实 schema 和 source kind，再通过版本化演进接入；不能在本 change 中预埋示例条目或隐藏人工词表。

Provider 首先验证 manifest，再按 manifest 顺序及逻辑 POSIX 路径确定性读取生成 JSON。生成事实仅接受现有六类：`headers`、`intrinsics`、`builtins`、`vectorTypes`、`platformMacros`、`compilerFlags`。同 fact kind/canonical value 的条目按稳定 source identity 合并。单个 generated source 无效时返回 partial 并保留其他已验证 source；manifest 不可读、identity/version 缺失、摘要不匹配或全部 source 不可用时返回 failed，不把空 KnowledgeSnapshot 解释为成功。

现有 24 个 YAML 不进入新 Provider，也不作为新 schema 的迁移输入。它们保持字节不变并继续由默认 legacy CLI 使用。新路径使用面向用户可观察行为的 acceptance matrix：每项能力标记为 generated-fact-local、structural-candidate、needs-curated-knowledge、needs-graph、needs-build、needs-packaging 或 needs-classification。矩阵来自已确认的 C/C++ 迁移需求和代表性 fixture，不要求与每个 YAML 文件一一对应。

继续复用当前 Pydantic 与标准库 JSON 能力，不增加运行时依赖；PyYAML 仅留在 legacy 路径。替代方案一是让 Provider 直接包装 legacy `Rule`，这会继承未类型化语义与分类耦合；替代方案二是修改现有 YAML 原地升级，会影响默认 CLI 和回滚；替代方案三是提前设计空 `curatedSets`，会把未完成的数据工作伪装成现有能力。三者均拒绝。

### 3. Normalizer 产生 canonical fact，但绝不删除原 Evidence

`normalization/cpp.py` 接收同一个 ScanContext 和 FrontendSnapshot，返回包含原 Entity、原 Evidence 及新增 NormalizedFact 的 NormalizedSnapshot。它执行有限且显式的规范化：include 路径分隔符与包围符号、symbol/type/macro 的原大小写精确值、空白稳定化、comment 原文、inline asm/attribute 的有界文本、以及安全的 compiler option name/value 拆分。

编译参数事实由 Normalizer 从已经纯读取的 `CompilationUnitContext.tokens` 产生派生 Evidence 与 NormalizedFact，producer 固定为 compilation-database reader，位置/subject 绑定对应 source Entity，metadata 记录 context ID 与 token index。它不重新解析 raw command、不读取 response file、不加载 plugin，也不启动 compiler。危险参数仍只作为文本事实供知识匹配，绝不执行。

等价事实按 canonical identity 聚合 `evidence_ids`、`context_ids` 和 producer provenance；顺序稳定去重。Normalization 遇到未知 Evidence kind 时保留原 Evidence、产生 info/partial Diagnostic 并跳过对应 NormalizedFact，而不是丢弃整个文件或伪造事实。

### 4. Frontend 只补齐 Detector 必需的 attribute Evidence

Tree-sitter adapter 与 vocabulary 增加 `declaration_attribute` Evidence，用于保存 GNU/MSVC/C++ attribute 或 declaration 中的 target/vector-size 文本和 source span。该扩展仍是语法事实，不判断 x86、严重程度或可达性。Local Detector 因而可以在不重读源码的情况下保留结构 candidate；具体 x86 target/固定向量宽度事实待后续 curated knowledge change 接入后再确认。

不增加“所有 identifier” Evidence，以避免显著扩大内存和误报面。模糊架构宏候选从现有 preprocessor/macro Evidence 中识别；普通变量/枚举若当前 Frontend 没有可靠 Evidence，则保持 unknown，等待后续受证据驱动的 frontend change，不能通过 regex 重扫文件补齐。

Tree-sitter `Node.start_point`/`end_point` 属于原生绑定边界，真实 AVX fixture 证明对同一 Point 属性进行多次链式读取时，超长单行节点可能返回不一致的 column，甚至导致进程退出。`_node_span()` 因此必须各获取一次 start/end Point，立即把 row/column 复制为 Python 整数，再构造 core SourceLocation；测试同时固定“每个 Point property 只访问一次”和 365 列真实调用表达式的行为。

### 5. Local Detector 使用显式 matcher registry，只生成 Observation

`detectors/definitions.py` 维护只读、code-owned 的 DetectorDefinition registry；`detectors/matchers.py` 提供对 NormalizedFact 的纯函数 matcher，并按知识类别建立只读索引。首批事实支持的本地 matcher 只覆盖：

- include ↔ headers；call/symbol ↔ intrinsics、builtins；type ↔ vectorTypes；
- preprocessor/macro ↔ platformMacros；compile_argument ↔ compilerFlags；
- comment 中出现上述已知事实时形成 hint；inline asm、declaration attribute 或模糊架构标识在没有权威事实时最多形成 structural candidate/unknown。

`detectors/local.py` 只遍历 facts 和 code-owned definitions、调用 registry、生成 core Observation 并稳定排序/去重。每个 confirmed Observation 必须引用现存 evidence ID 和适用的 knowledge ID；纯结构 candidate 若没有知识条目则必须明确记录 detector/evidence basis，不能伪造 knowledge ID。直接精确知识命中可标记 `confirmed_local`，comment 只能标记 `hint`，模糊或仅结构信号只能标记 `candidate`。Observation 不含 blocker 或最终 severity，manifest 也不承载这些分类字段。

需要尚未采集的 CPU API、汇编指令/寄存器、target 属性词、架构别名，以及宏链、替代实现、条件 sibling、构建选择或测试可达性的能力，都在 acceptance matrix 标为对应 deferred 原因。Local Detector 汇总结构化 Diagnostic 并保持 qualification partial/unknown，不以“未命中”代表安全。替代方案是复用 `evaluate_rules()`、在 Detector 内调用 legacy helpers 或硬编码未经审校词表；这些都会把旧耦合或不可审计数据带回新阶段，故禁止。

### 6. staged qualification 真实运行到 Detection 后停止

在专用 qualification profile 中使用真实 CppWorkspaceCollector、CppFrontend、KnowledgeProvider、CppNormalizer 和 LocalDetector；Analyzer 暂时提供空 AnalysisSnapshot，Classifier/Assessor/Projector 使用 recording/no-op 组件，Projector 返回空 artifact 且不写文件。测试验证同一个只读 ScanContext 和真实 Snapshot 沿固定顺序传递。

默认 `ScanApplication` 仍选择 LegacyPipelineRunner。只有 Evidence Graph、构建关系、Classifier、Assessment 和 compatible Report Projector 均完成且通过独立 cut-over change 后才允许切换。新的 Observation 暂不直接投影到 `findings`；未来投影时 Evidence/Knowledge provenance 进入既有 Finding `trace`，项目结论只进入可选 `summary.readiness`，不创建第二主结果。

### 7. 每个业务模块都在同一 change 内完成隔离单测

模块到单元测试的固定映射：

| 业务模块 | 隔离单元测试 |
|---|---|
| `core/knowledge.py` | `tests/unit/knowledge_detection/test_core_knowledge.py` |
| `core/facts.py` | `tests/unit/knowledge_detection/test_core_facts.py` |
| `core/results.py`、`core/observations.py`、`core/protocols.py` | `tests/unit/knowledge_detection/test_core_snapshot_extensions.py` |
| `knowledge/schema.py` | `tests/unit/knowledge_detection/test_knowledge_schema.py` |
| `knowledge/identity.py` | `tests/unit/knowledge_detection/test_knowledge_identity.py` |
| `knowledge/provider.py` | `tests/unit/knowledge_detection/test_knowledge_provider.py` |
| `normalization/cpp.py` | `tests/unit/knowledge_detection/test_cpp_normalizer.py` |
| `detectors/definitions.py` | `tests/unit/knowledge_detection/test_detector_definitions.py` |
| `detectors/matchers.py` | `tests/unit/knowledge_detection/test_local_matchers.py` |
| `detectors/local.py` | `tests/unit/knowledge_detection/test_local_detector.py` |
| `frontends/cpp/vocabulary.py`、`tree_sitter_adapter.py` | 现有对应 frontend unit 文件扩展 attribute 场景 |

Knowledge schema/I/O 使用临时目录、mock `Path` 和内存 JSON manifest payload；Normalizer 使用构造的 core Evidence/CompilationUnitContext；Detector 使用构造的 KnowledgeSnapshot/NormalizedFact；不得在 unit suite 中加载真实 parser、libclang、compiler 或 legacy evaluator。真实 manifest/生成 JSON、behavior acceptance matrix、Tree-sitter、libclang 和 staged flow 保持 component/integration/contract 层。

测试 runner 增加机器可读 knowledge-detection inventory，先运行隔离 unit suite并对上述新增/修改业务模块执行行覆盖率至少 90%、分支覆盖率至少 80%的门禁，再运行已有 frontend unit gate 和完整回归。每个清单模块必须有 executed lines。覆盖数据只写容器 `/tmp`。

## Risks / Trade-offs

- [legacy YAML 同时包含局部、关系、分类和文案语义] → 新路径完全不读取或迁移 YAML；保持默认 legacy 行为，并用需求/fixture 驱动的 acceptance matrix 管理能力差距。
- [manifest 演化成另一套通用规则 DSL] → v1 只允许 generated source 元数据；detector definition/matcher 留在 Python 代码和单测中，拒绝 recipe、operator、regex、分类与展示字段。
- [尚不存在的 curatedSets 被当成当前能力] → v1 schema 不包含该字段；开发计划把选源、采集、审校、溯源和接入固化为独立 `collect-kb-scanner-curated-knowledge-sets` change。
- [为 NormalizedSnapshot/Observation 增加字段可能影响现有构造] → 只增加默认空 tuple 的内部字段，维持现有 positional/keyword 用法测试，并禁止直接序列化为新报告。
- [不同 producer 的值表示不一致导致错误合并] → canonicalizer 按 fact kind 独立实现，ID 不基于宽泛文本降级；无法证明等价时保留多个 fact。
- [生成数据中 source 含机器路径] → 原 source 内容保留用于事实合同，但稳定身份只使用逻辑文件名、category/value 和内容摘要，不包含该机器路径。
- [局部命中被误当作最终问题] → Observation status 限制为 confirmed_local/candidate/hint，禁止 blocker/severity/readiness；默认 CLI 不消费新 Observation。
- [新增 attribute Evidence 扩大 frontend 范围] → 只提取明确 attribute/declaration 节点和有界文本，沿用现有 source-span/provenance/去重规则，并继续受 frontend 单元覆盖门禁保护。
- [原生 Tree-sitter Point 在重复读取时返回不一致坐标] → 在 adapter 边界一次性快照 start/end row/column 为普通整数，并用长单行真实 grammar fixture 回归，禁止将原生 Point 延迟传入 core 类型。
- [覆盖率总数掩盖模块空白] → inventory 双向检查模块文件与单测映射，除整体 90%/80% 外要求每个模块存在 executed lines。

## Migration Plan

1. 固化当前 41 项 frontend unit、126 项 full regression、legacy 五文件、输出 artifact 以及两份事实数据的基线。
2. 扩展 core 知识/事实/Observation 合同并完成隔离单测，保持所有新增字段默认兼容。
3. 建立 generated-facts-only JSON manifest、behavior acceptance matrix、schema、identity 和 provider；先通过合成 fixture，再用真实 manifest/生成 JSON 做 component qualification。
4. 扩展 attribute Evidence 并实现 C++ Normalizer，验证原 Evidence 和 context provenance 不丢失。
5. 实现 code-owned definition registry、纯 matcher 与 Local Detector，建立 category/status/deferred matrix。
6. 接入 staged qualification 到 Detection，后续阶段继续 recording/no-op，默认 CLI 不切换。
7. 在唯一 `kb-scanner-test` 容器依次运行 knowledge unit gate、frontend unit gate和完整回归，复核兼容边界并严格校验 OpenSpec。

回滚时可以从 qualification profile 移除新组件并保留代码；默认 CLI 始终走 legacy runner，因此本 change 不需要数据迁移或生产回滚。不得通过修改冻结 legacy 文件解决差异。

## Open Questions

无阻塞实现的问题。普通变量/枚举的模糊架构候选若缺少正式 Frontend Evidence，本阶段明确保持 unknown，不允许 Local Detector 绕过 Frontend 重扫源码；编译器事实之外的人工知识统一进入计划中的 `collect-kb-scanner-curated-knowledge-sets`，不得在本阶段临时硬编码。
