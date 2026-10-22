## ADDED Requirements

### Requirement: Revalidate direct-call eligibility in a separate derived layer

P2 SHALL 在不改变 ScopeIndex v1 原始绑定/unknown/capabilities 语义的独立派生层，复用显式 scope 校验并复核直接调用的函数/参数/返回类型、calling convention、ABI 支持、精确 linkage、可替换性和边界证据。SHALL 拒绝配置/target/layout/lineage 冲突及跨 profile 混合；符号名唯一或 opaque pointer 类型相同不得替代接口证明。

#### Scenario: A raw unique binding has an incompatible interface

- **WHEN** P1 根据符号唯一建立绑定，但调用点和定义的 calling convention、参数/返回或 ABI 规则不匹配
- **THEN** 保留原始 index，在 P2 记录不合格采用边及 unknown 效果，不执行确定实参替换

#### Scenario: The scope mixes profiles or repeated lineage

- **WHEN** 请求混入互斥 source-preserving/build-faithful 配置，或 linked 产物及其 object 祖先
- **THEN** 拒绝联合效果分析并列明冲突，不混合路径或重复计数；不通过改 triple/layout 绕过检查

### Requirement: Adopt restricted ODR bodies without claiming linker resolution

P2 SHALL 只在版本化规则允许时生成 odr-body-under-contract 边：调用直接指向本 TU 可见 linkonce_odr 定义，非 interposable 且有 dso_local 依据，scope 已声明封闭，COMDAT selection 属于已支持的 any 子集，接口/局部语义可解释，无冲突强定义且可见同名副本经保守规范化结构/接口指纹检查兼容。SHALL 记录采用体、LLVM 查询、检查结果及 ODR 契约假设；该边不得声明最终链接选择已知或修改原始 COMDAT unknown。一般 linkonce、weak/weak_odr、ifunc、动态边界及不可证明兼容的副本 SHALL 保持 unknown。

#### Scenario: A standard-library helper meets restricted ODR rules

- **WHEN** 固定 atomic 样例的直接辅助调用满足全部 ODR 采用条件
- **THEN** 允许使用该本地函数体推导效果/返回关系，证据标明 ODR 语义代表及假设，而原始索引仍保留其保守 COMDAT 状态

#### Scenario: A possible ODR body conflicts or can be replaced

- **WHEN** 可见副本不兼容、存在冲突强定义、interposable、非封闭边界或未支持 selection
- **THEN** 不任选一个定义，输出候选/unknown 和原因；即使各候选同名也不宣称函数体已确定

#### Scenario: A plain linkonce body resembles an ODR helper

- **WHEN** 精确 linkage 是 linkonce 而不是 linkonce_odr，其他外观信息相似
- **THEN** 不套用 ODR 采用通道，证明补充事实不能继续沿用 P1 折叠后的 linkage 值作判断

#### Scenario: Similar ODR bodies reference distinct private globals

- **WHEN** 两份看似相同的函数体引用不同 TU 的同名私有全局
- **THEN** 指纹保留被引用存储身份差异，不因剥离模块前缀或文本同名而认定副本兼容
