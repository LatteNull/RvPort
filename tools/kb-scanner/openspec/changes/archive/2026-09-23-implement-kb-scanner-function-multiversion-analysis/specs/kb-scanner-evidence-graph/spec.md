## ADDED Requirements

### Requirement: 函数版本成员必须与执行及替代证明隔离

Graph SHALL 保存函数版本组、属性 owner、真实函数体和非执行成员关系及 provenance。版本共存、相同签名或 default 标签 MUST NOT 自行生成 alternative_to、selected 或 inactive proof；已有精确 source/build 证明 SHALL 按 occurrence/configuration 绑定且不扩大范围。

#### Scenario: Default 与 AVX 版本共存
- **WHEN** 组中有两个真实版本定义但缺少目标选择证明
- **THEN** SHALL 保留成员和源码关系并将目标选择保持 unknown
- **AND** 执行可达性遍历 MUST NOT 通过成员边到达另一版本或据此排除 AVX

#### Scenario: 自动 clone 与真实来源
- **WHEN** 单个 target_clones 属性描述多个 compiler 生成版本
- **THEN** SHALL 关联同一真实 source body 与属性来源
- **AND** MUST NOT 伪造 clone/resolver 的源码 Evidence、调用点或行号

#### Scenario: 绑定缺失或跨配置
- **WHEN** proof 端点缺失、body 归属不唯一或属于不同 configuration
- **THEN** SHALL 拒绝该绑定，保留有效局部结构及 unknown 原因
- **AND** 既有无关完整 proof SHALL 不被改写或清除
