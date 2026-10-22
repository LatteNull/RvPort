## ADDED Requirements

### Requirement: 家族成员关系必须与执行和替代证明隔离

Graph SHALL 支持 architecture_family 实体及 candidate_member_of 结构关系，复用现有 source file 身份并保存路径规则 provenance。候选成员边 MUST NOT 被执行可达性、宏调用、alternative proof 或源码主链查询当作执行关系；名称相似 MUST NOT 生成 alternative_to。没有源码 Evidence 的结构来源 MUST NOT 伪造 Evidence ID 或行号。

#### Scenario: 只有路径相似

- **WHEN** 两个文件形成 x86/generic 路径家族但没有现有选择或 sibling proof
- **THEN** SHALL 仅记录候选成员关系，其选择及替代可用性为 unknown
- **AND** 从 x86 fact 进行执行依赖遍历 MUST NOT 经家族边到达 generic 文件

#### Scenario: 复用已有完整证明

- **WHEN** 现有真实 source/build/sibling proof 与家族成员端点及 configuration 精确对应
- **THEN** SHALL 将有效 proof 绑定到相应成员并保留其既有状态和原始 Evidence
- **AND** MUST NOT 因家族标签补齐缺失端点、跨配置借用 proof 或扩大证明范围

#### Scenario: 两个实现共同编译

- **WHEN** 两个成员都属于同一 target 但没有互斥选择证据
- **THEN** SHALL 保留各自选择状态，不因同 target 或同名函数建立替代证明

#### Scenario: 悬空或歧义绑定

- **WHEN** 候选 proof 引用不存在的实体或不能唯一对应成员
- **THEN** SHALL 拒绝无效绑定并输出诊断/unknown，保留原有有效图和路径观察
