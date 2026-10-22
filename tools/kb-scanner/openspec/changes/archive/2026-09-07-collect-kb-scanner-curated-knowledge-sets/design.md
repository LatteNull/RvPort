## Context

阶段 3 已建立严格的 generated-facts-only manifest、Knowledge Provider、Normalizer 和 Local Detector。当前两份 compiler facts 覆盖 headers、intrinsics、builtins、vectorTypes、platformMacros 和 compilerFlags，但行为验收矩阵仍将 x86 inline asm vocabulary、CPU/platform API、target attribute 和 fixed vector width 标记为 `needs-curated-knowledge`。现有采集脚本能从本地 LLVM/GCC 源码目录提取部分事实，但来源使用 `main` 或宿主机绝对路径，仓库中也没有对应 vendor checkout，因此不能直接作为新增数据的可复现生产链路。

本 change 同时涉及上游来源选择、数据生成、人工审校、manifest/schema、Provider 和局部 matcher。扫描器运行时仍只读已提交知识文件；知识生产是独立维护流程，不得在扫描项目时获取网络资源、启动 compiler/assembler/linker 或执行项目代码。所有代码测试与数据验证只在独立 `kb-scanner-test` 容器中运行，不向宿主机或生产镜像安装依赖。

## Goals / Non-Goals

**Goals:**

- 对阶段 3 的四项 `needs-curated-knowledge` 能力及架构别名缺口建立逐项来源审计和候选决策记录。
- 优先从版本固定的 LLVM、GCC、GNU Binutils 等权威结构化源码中确定性生成事实，只对机器无法直接证明的语义进行人工 curated 审校。
- 建立可复核、可版本化、可确定性重建的 generated/curated 数据、严格 schema、manifest 引用和完整 provenance。
- 让 Provider 同时加载既有 generated facts、新 generated facts 和 accepted curated facts；让适用 Local Detector 使用知识引用产生 confirmed 或明确的 candidate Observation。
- 保持两份既有 compiler facts、legacy YAML、默认 CLI、`scan-result.json` 1.0 和三个 artifact 完全兼容。
- 为每个新增或修改业务模块建立 isolated unit 映射，并维持 90% 行、80% 分支覆盖门禁。

**Non-Goals:**

- 不把 RVPT 页面、旧 YAML、搜索结果或未经固定版本的 `main` 分支直接当作权威运行时知识。
- 不把 regex、matcher、operator、severity、blocking、reason、suggestion 或本地化展示文案写入知识数据。
- 不实现 Evidence Graph、宏/调用可达性、构建选择、RPM 求值、最终分类、真实 RISC-V 编译或项目测试。
- 不执行或修改两份既有 `clang-x86-entries.json`、`gcc-x86-entries.json` 的生成流程；本 change 只为新增来源建立可复现生产合同。
- 不承诺所有候选都进入 accepted 数据；无权威依据或语义不明确的候选必须保留 rejected/deferred 决策。

## Decisions

### 1. Generated 与 curated 以“是否需要人工语义判断”划界

满足以下条件的条目进入新增 generated source：来源是版本固定的权威结构化定义，提取规则对同一输入完全确定，条目含义可由来源本身直接证明，且无需逐条人工选择。典型来源包括 LLVM MC/TableGen、Clang/GCC x86 target 定义和 GNU Binutils opcode/register tables。

需要别名归一、跨来源冲突裁决、API 架构归属判断或迁移语义解释的条目进入 curated source。RVPT 对比结果、旧 YAML 和 fixture 只能产生候选，不能单独支持 accepted 状态。

备选方案是把全部缺口手写进一个 curated JSON。该方案难以复现工具链升级、容易遗漏数千条指令和别名，也无法区分机器事实与人工判断，因此拒绝。

### 2. 使用三类互不混淆的制品

- Runtime generated sources：每个上游来源独立 JSON，承载自动提取事实和上游 source descriptor。
- Runtime curated sources：只包含 `accepted` 条目，承载稳定 entry ID、fact kind、canonical value、architecture family/scope、reference IDs 和 review policy/version。
- Non-runtime decision ledger：记录 candidate 的 accepted/rejected/deferred 状态、理由和证据缺口，用于审计但不由 Provider 加载。

这样 rejected/deferred 的理由不会污染运行时 KnowledgeEntry，也不会因为未出现在 accepted 集合中而丢失。数据文件不保存 detector recipe；匹配算法继续由 Python registry 管理。

### 3. 来源采用固定修订和独立 reference registry

每个 source/reference 必须记录稳定 source ID、官方仓库或文档 URL、精确 release/commit、逻辑路径或章节、许可证标识、采集日期和内容摘要。禁止用滚动 `main`、宿主机绝对路径或仅指向搜索结果的 URL 作为稳定 provenance。

首批来源优先级为：

1. LLVM MC/TableGen 与 GNU Binutils opcode/register tables：x86 指令和寄存器。
2. Clang/GCC x86 target/option definitions：target features、CPU/architecture names 和 compiler spellings。
3. Clang/GCC intrinsic headers、builtin definitions及对应官方文档：CPUID、RDTSC、XGETBV 等 compiler-facing CPU API。
4. 语言扩展官方文档：`target`、`target_clones`、`vector_size` 等语法和语义。
5. 链接器只用于其真正拥有的 ELF machine、relocation 或 emulation 事实；不得把链接器当作源码 API 或汇编词表来源。

精确上游修订在 apply 的来源审计中选择并写入数据，不在 proposal 阶段猜测未来版本。

### 4. Manifest 升级但保留 v1 输入兼容

现有 v1 manifest 和两份 generated source 必须继续被 Provider 接受且产生相同 KnowledgeSource/KnowledgeEntry identity。新的生产 manifest 使用版本化扩展声明新增 generated sources 和 curated sources；每项仍使用逻辑相对 JSON 路径和 SHA-256。Provider 依据显式 source kind 选择严格模型，禁止通过文件名猜测或扫描目录自动加载。

如果 v2 任何新增来源无效，Provider 按现有 complete/partial/failed 规则保留其他有效来源并产生去敏 Diagnostic。accepted curated 条目与 generated 条目使用相同的 scanner-owned KnowledgeEntry 合并合同；同 fact kind、architecture family 和 canonical value 合并全部 source provenance。

备选方案是在 v1 中静默加入 `curatedSets`。这会破坏阶段 3 对 v1 generated-only shape 的严格合同，且难以区分来源类型，因此拒绝。

### 5. 首批 fact kind 与检测语义分离

计划新增的知识类别包括 assembly instructions、register names、CPU/platform APIs、target features、architecture aliases 和 vector-width markers。最终名称在 schema 中固定并由 allowlist 验证。

- 指令/寄存器与 inline asm Evidence 有明确 token 命中时可形成 knowledge-backed `confirmed_local`。
- 明确的 x86 compiler/API symbol、target feature 或 architecture alias 命中时可形成 `confirmed_local`。
- `vector_size(16/32/64)` 等宽度表达并非 x86 专属，即使有权威来源也只能形成 knowledge-backed `candidate`，等待关系与分类阶段判断。
- comment 命中仍只能是 hint；缺少 Frontend Evidence、token 边界或权威来源时保持 unknown/deferred。

知识条目只说明“它是什么”，DetectorDefinition 才说明“如何匹配”，后续 Classifier 才判断 blocking/severity/readiness。

### 6. 数据生产不依赖扫描运行时，也不隐式联网

采集器接收显式、只读的上游 source root 或 source archive 作为输入，不自行 clone、下载或执行工具链。实际刷新流程先取得并校验固定修订的来源，再在 `kb-scanner-test` 镜像环境中运行 extractor/linter；测试使用最小、带许可证说明的上游结构 fixture 验证解析、异常、确定性和边界。

扫描运行时只加载提交到规则包中的 JSON，不导入 production tooling，也不启动 compiler、assembler 或 linker。现有无网络、只读 workspace 测试边界保持不变。

### 7. 模块与测试责任显式映射

新增知识生产业务模块按职责拆分为 source descriptor/schema、结构化 extractor、curation decision/validation 和 deterministic renderer；命令行 wrapper 只负责参数适配。每个模块必须有独立 unit test，文件系统、上游源码、时钟和网络边界使用临时目录或 fake，不依赖本机工具链。

现有 `knowledge/schema.py`、`identity.py`、`provider.py` 以及实际修改的 `detectors/definitions.py`、`matchers.py`、`local.py` 分别扩展原 isolated unit。component tests 验证真实提交数据、manifest hash 和 Provider 加载；integration tests 验证 qualification；contract tests冻结旧 facts、legacy 输出和执行边界。高层测试不能替代单元覆盖门禁。

## Risks / Trade-offs

- [上游结构变化导致 extractor 失效] → 固定修订、每来源独立 adapter、最小真实结构 fixture 和明确 unsupported Diagnostic；升级来源必须显式更新版本与基线。
- [把工具链支持项误当成 x86-only 迁移风险] → generated 数据记录事实类别，Detector 按类别设 confirmed/candidate 语义；固定向量宽度等非专属信号禁止升级为 confirmed。
- [两个权威来源命名冲突或语义不同] → 保留全部来源，只有 canonical identity 相同才合并；需要判断的映射进入 curated review，不能在 extractor 中静默裁决。
- [数据规模增加导致加载或匹配退化] → 保持排序去重、按 fact kind 建索引，并增加数据规模和 qualification 性能基线；不把 regex 放入数据。
- [许可证或引用不完整] → 缺少许可证、固定修订、逻辑位置或摘要的来源不得进入 accepted runtime 数据。
- [现有旧脚本来源不可复现] → 冻结两份旧输出，不借本 change 重生成；新增 production pipeline 使用新的固定来源合同并在文档中明确两代边界。
- [维护成本增加] → 自动提取覆盖高基数机械事实，人工审校仅处理剩余语义；decision ledger 避免重复评审已拒绝候选。

## Migration Plan

1. 冻结现有 manifest、两份 compiler facts、行为矩阵、legacy 输出和当前测试数字作为迁移基线。
2. 完成来源可提取性审计，为每类候选标记 generated、curated、rejected 或 deferred，并选择精确上游修订。
3. 建立 production schema、reference registry、decision ledger 和 extractor；先用最小 fixture 通过 isolated unit，再生成并审校真实数据。
4. 引入兼容的 manifest 新版本和 Provider 支持；验证旧 v1 输入产生完全相同 identity，新 manifest 才加载新增来源。
5. 接入知识类别与 Local Detector，按 confirmed/candidate/hint 边界更新行为矩阵和 qualification。
6. 在独立测试容器运行 unit coverage、数据 lint、component/integration/contract 和完整回归，记录最终条目数、来源版本、接受/拒绝/延后数量及真实 x86-only 项目效果。

回滚时恢复 v1 manifest 即可让默认新 Provider 只加载两份旧 generated facts；新增数据与 matcher binding 可整体撤回，不需要修改旧事实、legacy YAML 或现有报告消费者。

## Open Questions

- 精确 LLVM/GCC/Binutils release/commit 由 apply 阶段的来源审计决定；选择标准是官方发布、可访问源码、许可证明确和结构可稳定解析，而不是“最新 main”。
- 若同一 API 同时作为 compiler intrinsic 和架构 API 出现，审计时决定复用既有 `intrinsics`/`builtins` 条目还是进入新的 API fact kind；不得仅为分类整齐而复制事实。
- 链接器来源只有在能补充当前 C/C++ 静态检测所需且其他权威来源缺失的事实时接入，否则在 decision ledger 中记录为已评估但不采用。
