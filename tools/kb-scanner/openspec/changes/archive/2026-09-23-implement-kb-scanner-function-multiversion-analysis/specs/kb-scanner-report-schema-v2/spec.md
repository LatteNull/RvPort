## ADDED Requirements

### Requirement: 函数多版本必须在既有 extension 内自包含展示

V2 SHALL 通过 `org.rvport.kb-scanner.function-multiversion` 输出有界 catalog 和单 Finding 内的版本上下文，分别展示机制、身份/来源、default 声明/定义状态、局部依赖、选择及适用性。新检查 SHALL 使用已有 architecture_probe 等合法 fact/step/edge kind，不增加核心 schema 必填字段或枚举；原 intrinsic fact SHALL 保持。合法 extension SHALL 与现有 namespace 合并。

#### Scenario: 离线查看一个 Finding
- **WHEN** 用户仅打开一个关联多版本的 intrinsic 或属性检查 Finding
- **THEN** SHALL 无需读取 catalog/内部 snapshot 即可看到相关版本、各自来源及状态原因
- **AND** 引用 SHALL 在本 Finding 内闭合；不能闭合时以真实路径/span 描述和 unknown 表达，不输出悬空 ID

#### Scenario: 没有新增问题但有 default 组
- **WHEN** 组具有可定位结构，但不存在应新增的迁移问题
- **THEN** SHALL 可在顶层有界 extension/HTML 摘要中展示
- **AND** MUST NOT 仅为了展示组而制造 blocker 或复制代码 Finding

### Requirement: 多版本源码链和双语展示必须保持兼容与真实位置

多版本相关链 SHALL 只使用真实属性、声明、定义及有来源的关系，保留每节点 span、高亮和上下各 20 行；生成的 clone/resolver MUST NOT 拥有伪造源码位置。新增用户解释/标题/建议 SHALL 成对提供中文/英文，遵循既有 suggestion/suggestion_en 合同；无核心配对字段的展示数据 SHALL 放入 namespace，不改变核心 schema。默认 V2、显式 V1 与 JSON/HTML/log artifact SHALL 保持。

#### Scenario: Clone 共享源函数体
- **WHEN** 多个版本描述对应一个真实 body
- **THEN** SHALL 以结构描述引用该 body，源码 occurrence 不按版本数倍增
- **AND** classification/assessment SHALL 留在结论及摘要，不能进入 evidenceChain

#### Scenario: 裁剪或恶意源码文本
- **WHEN** 版本/来源超预算或函数名、属性参数含 HTML 特殊字符
- **THEN** SHALL 有界裁剪并标记原因/计数，HTML SHALL 安全转义且默认中文展示
- **AND** MUST NOT 将未显示 default 解释为缺失，或通过新增后端输入才能解释当前 Finding

#### Scenario: 无相关构造的既有报告
- **WHEN** 固定输入没有受支持多版本构造
- **THEN** 除允许的空/缺省 extension 表达外，V1/V2 原始事实、结论、计数和源码链 SHALL 保持
- **AND** 有多版本输入的真实变化 SHALL 有逐字段人工差异记录，不自动改写 oracle
