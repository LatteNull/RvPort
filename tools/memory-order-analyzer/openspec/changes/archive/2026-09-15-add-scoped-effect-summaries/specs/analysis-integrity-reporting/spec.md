## ADDED Requirements

### Requirement: Validate local evaluation snapshots and bound payloads

系统 SHALL 独立协商 LocalEvaluationRequest/Result v1，拒绝旧四 kind 握手；SHALL 校验请求/结果完整快照、函数和当前/祖先实例、参数类型、原始/分析引用角色、所有摘要与补充依赖 digest、scope/profile/预算及表达式结构上限。结果 request_hash SHALL 与调度器实际提交请求一致，不能仅信任结果自述。P1 v2 与模块元数据缓存不迁移。

#### Scenario: A worker substitutes the request or a dependency

- **WHEN** worker 返回不同实参/实例的请求快照或陈旧/缺失补充及 callee 摘要
- **THEN** 拒绝消费及缓存命中，不将该结果当作当前上下文的 complete 或可用空图

#### Scenario: A candidate carries an invalid binding

- **WHEN** 候选含未绑定参数、外来分配/guard、错误参数数目/位宽/地址空间、重复条目或非法 bottom
- **THEN** 明确拒绝；合法祖先实例的对象保留原归属，不套用仅允许外层入口全局对象的限制

### Requirement: Bind local evidence to its supplement generation

摘要和报告 SHALL 通过 local_dependencies 的 artifact_key/canonical digest 引用经过 origin、schema、预算和节点登记校验的 LocalAnalysisFacts。SourceRef 与 AnalysisRef SHALL 使用不同键和角色；SHALL 拒绝重复登记、悬空输入、跨函数证据、IR/分析命名空间混用及与原始节点冲突的 owner/opcode。身份校验 SHALL 不被表述为语义证明。

#### Scenario: A consumer lacks or substitutes the referenced supplement

- **WHEN** 补充产物缺失、digest 陈旧、预算不同或证据不属于对应函数
- **THEN** 拒绝消费，不通过添加 P1 节点、忽略引用或降成空证明来接受摘要

### Requirement: Version P2 products independently from P1 contracts

系统 SHALL 为 EffectAnalysisRequest、LocalAnalysisFacts、LocalEvaluationRequest、LocalEvaluationResult、EffectSummary 和 EffectAnalysisReport 提供独立 v1 schema 及分析协议，初始 analysis_version 为 0.1.0、policy_id 为 scoped-effects-v1；SHALL 保持 ModuleFacts/RunReport v2、其他已有 kind v1 和 P1 extractor 语义不变。SHALL 按 kind 协商支持版本，不以静默附加字段、填默认值或覆盖旧文件迁移。

#### Scenario: New analysis reads existing P1 facts

- **WHEN** 合法的 ModuleFacts v2 和原始 BC 被用于 P2
- **THEN** 新建独立补充/摘要/报告，原始 ID、extraction、capabilities、ArtifactKey 和历史 RunReport 保持不变

#### Scenario: A consumer receives an unsupported derived version

- **WHEN** 输入未知 kind、未来派生 schema 或不兼容分析 worker/policy
- **THEN** 明确拒绝并报告协议错误，不因 LLVM 主版本相同而接受，也不将缺少摘要解释为无效果

### Requirement: Validate derived references and preserve evidence generations

系统 SHALL 在 worker 输出、磁盘和缓存消费处验证派生产物结构/唯一 ID/原始引用/函数和上下文归属，以及 artifact/BC/facts digest、scope/profile、策略和依赖摘要身份。SHALL 将原始诊断的解释结果与对应原始 ID 和证据关联，不删除 raw unknown、不抬高 unknown provenance；无效结构拒绝而不是作为正常 partial 空图。

#### Scenario: A summary references another context or missing event

- **WHEN** 派生效果含悬空原始事件、错误 artifact、跨函数/上下文对象或不一致的依赖 hash
- **THEN** 返回 invalid_reference 或对应身份错误，不消费该摘要、不发布成功分析结果

#### Scenario: A supplement explains a raw diagnostic

- **WHEN** 有限 ABI 解释或路径证明消除了某原始 unknown 对一个上下文的影响
- **THEN** 新产物保存原始诊断 ID、策略及证明，原始文件和其他上下文的诊断不变，来源可信度不自动升级

#### Scenario: An instance table or binding is forged

- **WHEN** 实例 parent 悬空/成环、调用位置不属于父函数、guard 属于其他函数、分配声称比调用更精确的单例性，或实例化结果仍有未绑定局部模板槽
- **THEN** 拒绝 invalid_reference，不把结构有效的错误身份解释为完整摘要，亦不修改 P1 原始 ID

### Requirement: Isolate analysis cache generations from compilation artifacts

P2 SHALL 将局部/上下文/SCC 派生身份与原始编译/extractor 身份分离；版本、策略、预算、scope/边界或依赖摘要变化 SHALL 使相关派生缓存失效，不无故重编译或重键未变原始 BC。缓存失效与迁移 SHALL 保留历史产物，不覆盖旧结果或使用陈旧来源。

#### Scenario: Only the effect-analysis policy changes

- **WHEN** 相同 BC 和 P1 facts 使用新的摘要预算或分析策略
- **THEN** 新生成不同派生身份，不计为旧摘要命中，同时原始 BC/facts 可继续复用且历史输出不被覆盖
