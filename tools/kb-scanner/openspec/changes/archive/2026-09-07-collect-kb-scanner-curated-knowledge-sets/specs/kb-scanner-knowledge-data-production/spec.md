## ADDED Requirements

### Requirement: 知识候选必须先完成来源可提取性审计
知识生产流程 SHALL 对 x86 汇编指令/寄存器、CPU/平台 API、target feature、架构别名和固定向量宽度候选逐类判断其是否能从权威结构化来源确定性提取，并 SHALL 将每个候选或候选集合标记为 generated、curated、rejected 或 deferred。RVPT 对比结果、legacy YAML 和已有 fixture MUST 只作为候选发现线索，不能单独使条目进入 accepted runtime knowledge。

#### Scenario: 工具链能直接证明事实
- **WHEN** 版本固定的 compiler、assembler 或 linker 结构化定义能直接且无人工选择地产生一个事实
- **THEN** 该事实 SHALL 进入对应 generated source
- **AND** 它 MUST NOT 被重复手写为 curated entry

#### Scenario: 候选需要人工语义判断
- **WHEN** 候选涉及别名归一、API 架构归属、跨来源冲突或迁移语义解释
- **THEN** 候选 SHALL 进入人工审校流程并记录决策状态
- **AND** 在 accepted 之前 MUST NOT 被 Provider 当作权威知识加载

#### Scenario: 候选缺少充分依据
- **WHEN** 候选只有旧规则、二手页面或不确定上下文支持
- **THEN** decision ledger SHALL 将其记录为 rejected 或 deferred 并说明证据缺口
- **AND** 未收录 MUST NOT 被误表示为已经覆盖或安全

### Requirement: Generated facts 必须从版本固定的权威输入确定性产生
新增 generated source SHALL 由无网络、无 subprocess 副作用的 extractor 读取显式只读 source root 或 archive，SHALL 固定上游 release/commit、逻辑源路径、许可证和内容摘要，并 SHALL 对相同输入产生字节一致的排序去重 JSON。Extractor MUST NOT clone、下载、启动 compiler/assembler/linker 或写入上游输入。

#### Scenario: 从 LLVM 或 Binutils 提取汇编词表
- **WHEN** extractor 接收受支持修订的 LLVM MC/TableGen 或 GNU Binutils opcode/register tables
- **THEN** 输出 SHALL 包含来源可追溯的 x86 instruction/register facts
- **AND** 输出顺序和内容 MUST NOT 依赖文件系统遍历顺序或机器绝对路径

#### Scenario: 从 Clang 或 GCC 提取 target 定义
- **WHEN** extractor 接收受支持修订的 x86 target/option definitions
- **THEN** 输出 SHALL 产生可证明的 target feature、CPU/architecture name 或 compiler spelling facts
- **AND** extractor MUST NOT 通过未经审校的名称猜测架构归属

#### Scenario: 上游结构不受支持
- **WHEN** 固定来源缺少必需文件或其结构无法由当前 adapter 识别
- **THEN** extractor SHALL 失败并给出不含宿主机路径的结构化原因
- **AND** 它 MUST NOT 静默生成空的成功数据集

### Requirement: Curated entries 必须逐条溯源并与决策记录分离
Runtime curated source SHALL 只包含 accepted entries；每条 entry SHALL 具有可重算的稳定 ID、fact kind、canonical value、architecture family/scope、一个或多个权威 reference ID 以及 review policy/version。Rejected/deferred 候选及理由 SHALL 保存在不被 Provider 加载的 decision ledger 中。

#### Scenario: 条目通过审校
- **WHEN** 候选的权威来源、规范值、架构范围和冲突处理均已确认
- **THEN** entry SHALL 以 accepted 状态进入 curated runtime source
- **AND** validator SHALL 验证其 ID、reference 和 review policy 一致性

#### Scenario: 条目被拒绝或延后
- **WHEN** 候选不属于 x86、含义依赖未知上下文或来源不足
- **THEN** decision ledger SHALL 保留 rejected/deferred 状态和理由
- **AND** runtime curated source MUST NOT 包含该候选

#### Scenario: Runtime 与审计数据被读取
- **WHEN** Knowledge Provider 加载 curated source
- **THEN** Provider SHALL 只读取 accepted runtime entries
- **AND** Provider MUST NOT 把 decision reason、review comment 或 rejected candidate 转换为 KnowledgeEntry

### Requirement: 每个知识来源必须具有完整且稳定的 Provenance
Source/reference registry SHALL 为每个 generated 或 curated 来源记录稳定 ID、官方 URL、精确 release/commit、逻辑路径或文档章节、许可证标识、采集日期和内容 SHA-256。滚动分支、搜索结果、宿主机绝对路径或无法复核的引用 MUST NOT 支持 accepted runtime knowledge。

#### Scenario: 来源指向滚动 main 分支
- **WHEN** source descriptor 只包含 `main`、`master` 或无版本网页
- **THEN** provenance lint SHALL 拒绝其作为 accepted 条目的唯一依据
- **AND** 维护者 SHALL 固定 release/commit 或将候选保持 deferred

#### Scenario: 多个来源支持同一事实
- **WHEN** LLVM、GCC、Binutils 或官方文档共同支持同一 canonical fact
- **THEN** 知识条目 SHALL 保留全部适用 source/reference identity
- **AND** 合并 MUST NOT 丢失许可证或版本信息

### Requirement: 知识数据必须只承载事实而不承载执行或分类逻辑
Generated/curated runtime schema SHALL 使用明确 fact-kind allowlist 和严格额外字段拒绝策略，并 MUST NOT 包含 regex、operator、matcher binding、severity、blocking、reason、suggestion、本地化 message 或最终 readiness。知识数据 SHALL 说明事实身份与来源，匹配算法 SHALL 继续由代码维护。

#### Scenario: 数据尝试嵌入匹配表达式
- **WHEN** runtime knowledge entry 包含 regex、operator、pattern 或 detector recipe
- **THEN** strict schema/lint SHALL 拒绝整个无效 source 或按来源边界产生失败
- **AND** 该表达式 MUST NOT 被解释或执行

#### Scenario: 固定向量宽度被收录
- **WHEN** 权威来源证明 `vector_size` 或固定宽度写法但不能证明其为 x86 专属
- **THEN** 数据 SHALL 使用迁移敏感而非 x86-only 的事实类别或 scope
- **AND** 数据 MUST NOT 直接声明 blocker、severity 或 ready/not-ready

### Requirement: 知识生产覆盖必须可度量且显式保留缺口
数据基线 SHALL 分别报告每个候选类别的 generated、accepted curated、rejected 和 deferred 数量、来源版本以及与阶段 3 behavior acceptance matrix 的映射。验收 MUST NOT 仅以总条目数衡量完成度；未覆盖能力 SHALL 保留明确 reason 和后续责任阶段。

#### Scenario: 首批数据生产完成
- **WHEN** 本 change 生成最终数据基线
- **THEN** 四项既有 `needs-curated-knowledge` 能力及架构别名 SHALL 分别有覆盖状态和数量
- **AND** 每项 SHALL 要么有可加载知识，要么保留可审计 deferred 原因

#### Scenario: 高数量机械事实掩盖语义缺口
- **WHEN** 指令词表包含大量条目但 CPU API 或向量语义仍未确认
- **THEN** 验收 SHALL 分类别报告缺口而不是宣称 curated knowledge 整体完成

### Requirement: 知识生产模块必须具有隔离单元测试和数据质量门禁
每个新增或实质修改的 source model、extractor、curation validator、renderer 或 lint 业务模块 SHALL 映射到独立 unit test，使用最小固定上游 fixture 和 fake 边界，并 SHALL 在 `kb-scanner-test` 容器中达到至少 90% 行覆盖和 80% 分支覆盖。真实数据 component、Provider integration 和 full regression MUST NOT 替代 unit gate。

#### Scenario: 测试 extractor
- **WHEN** unit suite 验证正常、重复、乱序、缺失、畸形和不受支持的上游结构
- **THEN** 测试 SHALL 直接断言确定输出、Diagnostic 和无副作用边界
- **AND** 测试 MUST NOT 依赖网络、本机 compiler 或完整上游 checkout

#### Scenario: 检查测试 inventory
- **WHEN** 新增、删除或重命名知识生产业务模块
- **THEN** 机器可读 inventory SHALL 同步映射 isolated unit 和适用高层测试
- **AND** 缺失映射、零 executed lines 或覆盖率不足 SHALL 使容器失败
