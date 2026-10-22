## ADDED Requirements

### Requirement: 规则证据缺失和冲突必须逐 assessment 保守传播
每条启用规则 SHALL 在执行前验证其 scope 所需的 AST facts、IR facts、evidence bindings、profile 字段和有效编译选项。缺失、unsupported、ambiguous、摘要不一致或相互冲突的决定性证据 MUST 产生 `unknown` 或 `failed` assessment 及稳定双语诊断，不得降级为 `not_matched`。若至少一个 assessment 可用但任一必需 assessment 被阻断，整体状态 SHALL 至少为 `partial`；若所有启用规则均没有可用 assessment，整体状态 SHALL 为 `failed`。

#### Scenario: FMA binding ambiguous
- **WHEN** 乘加候选对应多个无法唯一验证的 IR facts，且没有有效显式 sidecar
- **THEN** `fma-contraction` assessment 为 `unknown`，诊断记录候选数和 frontier，不任选一个 IR fact 生成或排除 finding

#### Scenario: 一个规则缺少 profile 字段
- **WHEN** `long-double-abi` 因目标 profile ABI class unknown 无法判断，但其他启用规则完整完成
- **THEN** 保留其他规则 findings，整体结果为 `partial`，summary 将该 scope 计入 unknown 而非 not_matched

#### Scenario: 所有启用规则都不可评估
- **WHEN** 每个启用规则都因必需 facts/evidence/profile 缺失或失败而没有 matched/not_matched assessment
- **THEN** 整体结果为 `failed`，退出码为 3，且摘要不得声明未发现核心迁移风险

### Requirement: 规则异常必须按可隔离范围处理
规则实现抛出的已分类输入/证据异常 SHALL 只使对应 rule/scope assessment 为 `failed`，其他规则和 scope MUST 继续；registry 损坏、身份算法不一致、结果 schema 无法满足或其他无法安全隔离的错误 SHALL 升级为 `internal_error`。默认诊断 MUST 移除堆栈、环境变量值、凭据和根外绝对路径。

#### Scenario: 单条规则对一个翻译单元失败
- **WHEN** `x87-excess-precision` 在一个 TU 的规范化事实上遇到可隔离的非法组合，而其他 TU 和规则输入有效
- **THEN** 仅该 rule/TU assessment 计入 failed，其他结果被保留，整体状态按部分完成语义聚合

#### Scenario: registry identity 不一致
- **WHEN** 同一 rule code/version 在一次运行中解析出两个不同实现摘要或依赖声明
- **THEN** 扫描器停止规则执行并返回 `internal_error`，不发布可能由错误 registry 生成的 finding

### Requirement: 规则预算耗尽必须记录稳定 frontier
扫描器 SHALL 对总 assessment 数、单规则候选数、证据引用数、聚合相关位置数、诊断数和规则 wall/CPU 预算设置显式上限。候选 MUST 在截断前按稳定键排序；预算耗尽时 SHALL 停止受影响范围，记录预算名称、限制、已用值、rule/scope 和最后完成的稳定 frontier。已有可用 assessments 被保留，未处理范围 MUST 计入 unknown/failed，且不得因不同并发完成顺序改变结果。

#### Scenario: FMA 候选数达到预算
- **WHEN** `fma-contraction` 在处理完稳定排序的部分候选后达到单规则候选上限
- **THEN** 已完成 assessment 保留，剩余 scope 记录 `budget_exceeded` 和 frontier，整体结果至少为 `partial`

#### Scenario: 聚合位置超过输出上限
- **WHEN** 一个 `unsafe-fp-optimization` aggregation key 关联的位置数量超过配置上限
- **THEN** finding 保存确定性选择的有界位置、总受影响数和截断标记，不因输入或线程顺序选择不同代表位置
