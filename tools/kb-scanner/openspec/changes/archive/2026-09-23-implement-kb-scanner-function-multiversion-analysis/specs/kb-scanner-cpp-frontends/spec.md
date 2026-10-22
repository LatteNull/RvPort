## ADDED Requirements

### Requirement: 前端必须提供有界函数身份和属性归属而不破坏原始事实

C/C++ Frontend SHALL 在现有授权输入和解析生命周期内恢复相关非模板自由函数的声明/定义描述、限定作用域、签名形状、linkage、属性 owner、真实 body 范围及配置来源。完整 declaration_attribute Evidence 的值、位置和原有身份 SHALL 保留；新增结构 MUST NOT 将普通 identifier 或所有普通函数转为迁移问题。

#### Scenario: 属性位于不同合法语法位置
- **WHEN** target/target_clones 属性在返回类型前、声明符后或标准属性列表中且 grammar 能准确识别
- **THEN** SHALL 按语法结构绑定实际函数并保留名称、属性、声明及定义各自位置
- **AND** MUST NOT 按最近文本、相同行号或裸函数名猜测归属

#### Scenario: 可选 Clang 增强冲突
- **WHEN** Clang 在安全 compilation context 中提供语义声明关联，或该关联与基线冲突/解析失败
- **THEN** SHALL 保留来源及配置；成功时补充唯一绑定，失败或冲突时保留 baseline 与 partial/ambiguous
- **AND** MUST NOT 强制 compilation database、静默覆盖其他版本，或将绝对路径 USR 写入稳定身份

#### Scenario: 原生节点错误恢复
- **WHEN** 函数或属性区域出现 ERROR/MISSING、UTF-8、CRLF 或多语言候选解析
- **THEN** SHALL 在 Tree 存活时仅提取受控标量并由 byte index 构造位置，保留可定位事实及错误范围
- **AND** MUST NOT 使用 start/end Point、跨生命周期缓存 Node/Cursor 或伪造完整函数体

### Requirement: 函数结构归一化必须校验引用并隔离版本配置

Normalizer SHALL 校验函数 owner、属性、声明/定义/body 关联的有效性，合并相同语义事实的 producer provenance，并保持不同作用域、版本属性及 compilation configuration 独立。没有多版本构造的已有事实身份 SHALL 保持。

#### Scenario: 重复 producer 和非法 owner
- **WHEN** 两个 producer 提供同一有效结构，或输入引用不存在的 owner
- **THEN** 前者 SHALL 确定性合并且保留来源，后者 SHALL 产生明确合同 Diagnostic 并拒绝无效引用
- **AND** MUST NOT 因值相同跨配置/版本吞并或丢弃原始属性事实
