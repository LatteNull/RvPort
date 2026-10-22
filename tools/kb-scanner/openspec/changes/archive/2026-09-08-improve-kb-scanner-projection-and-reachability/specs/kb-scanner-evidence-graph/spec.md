## ADDED Requirements

### Requirement: Evidence Graph 必须向下游提供可闭合的引用子图
Evidence Graph SHALL 确保每个供 Detection/Classification/Projection 使用的 Relation 和 ProofPath 均可解析到其 source、target 及中间 Evidence/Entity，并 SHALL 以稳定 reason 标记缺失、冲突和预算截断。完整引用对象 MUST 可由 snapshot reference index 获得，而不能只暴露悬空 ID。

#### Scenario: 宏替换链完整
- **WHEN** 调用点经宏定义到终端 x86 intrinsic 的所有对象和关系均已恢复
- **THEN** Graph SHALL 提供包含调用 Evidence、macro definition Evidence、terminal symbol Evidence 和全部 relation ID 的 complete proof
- **AND** 下游 SHALL 能在不读取源码的情况下投影全部位置

#### Scenario: 关系引用对象缺失
- **WHEN** Relation 或 ProofPath 引用不存在的 Evidence/Entity
- **THEN** Graph SHALL 将该路径标记为 partial/failed 并提供稳定 reason 和断裂 ID
- **AND** 下游 MUST NOT 将其视为 complete reachability

### Requirement: 重复宏定义必须按可见性和配置保守消歧
Graph Analyzer SHALL 使用 translation unit/include 可见性、configuration identity、定义位置和结构化 macro identity 对重复宏定义候选消歧。只有唯一可见定义或多个语义等价定义时 SHALL 形成 complete definition relation；非等价候选仍然存在时 MUST 保持 ambiguous/unknown。

#### Scenario: 同名宏在当前配置只有一个可见定义
- **WHEN** configuration 和 include/definition 顺序证明唯一候选对调用点可见
- **THEN** Analyzer SHALL 建立 complete call-to-definition Relation 和 ProofPath
- **AND** Classification MAY 使用该 proof 判断调用可达性

#### Scenario: 多个非等价定义仍可见
- **WHEN** 过滤后仍有两个或以上非等价定义且无法证明实际选择
- **THEN** Analyzer SHALL 保留全部候选引用并标记 ambiguous/unknown
- **AND** 它 MUST NOT 通过输入顺序选择第一个定义

### Requirement: 图闭包和宏消歧必须通过修正后的 AVX 基线与单元门禁
人工 AVX baseline SHALL 以真实 token 起点和完整 span 为准，并 SHALL 覆盖 12 个函数式宏定义、18 个 replacement 终端引用及其调用关系。本 change 修改的 reference closure、macro resolver 和 relation diagnostic producer SHALL 各自映射隔离单元测试，在 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。

#### Scenario: 人工基线含错误列号
- **WHEN** 基线列号与源码中 token 的真实起点不一致
- **THEN** 基线 SHALL 被人工修正并记录为 baseline correction
- **AND** scanner MUST NOT 为迁就错误基线而改变正确 span

#### Scenario: 运行图模块门禁
- **WHEN** 独立容器运行 graph unit inventory 和 AVX component test
- **THEN** 隔离 unit SHALL 先满足逐模块覆盖门槛，AVX 对照 SHALL 再验证所有 definition/replacement 引用
- **AND** 真实 parser 集成结果 MUST NOT 被计入隔离单元覆盖率
