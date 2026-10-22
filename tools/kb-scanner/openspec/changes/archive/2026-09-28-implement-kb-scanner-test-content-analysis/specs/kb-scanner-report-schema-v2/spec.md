## ADDED Requirements

### Requirement: 测试内容必须在既有 Finding 合同中自包含展示

V2 SHALL 通过 org.rvport.kb-scanner.test-content 可选 namespace 展示测试身份、编译/注册/内容各自状态、来源、用途、proof 完整性与 unknown 原因。相关 Finding SHALL 自包含，不依赖另读内部快照或顶层目录；核心 schemaVersion、required 字段及 fact/step/edge enum MUST 保持。新 namespace SHALL 与既有扩展合并。

#### Scenario: 打开一个测试相关 intrinsic Finding

- **WHEN** 该 intrinsic 经受支持的注册、构建、入口及断言关联
- **THEN** 单 Finding SHALL 展示真实构建/注册位置、源码条件/调用/断言与命中位置，引用闭合
- **AND** 编译依赖与测试内容关联 SHALL 分别说明，不伪造测试执行结果

#### Scenario: 只有部分链或没有新增迁移问题

- **WHEN** 证据缺注册、调用唯一性、宏环境或达到预算
- **THEN** SHALL 显示具体断点、裁剪及可用来源，不拼接不同配置为完整路径
- **AND** 仅需展示测试摘要时 MUST NOT 为此制造 low Finding 或重复原问题

### Requirement: 测试源码链必须双语有界并兼容旧消费者

源码 evidenceChain SHALL 只包含真实 source/build 位置及可验证连接；抽象测试角色、classification、assessment MUST NOT 伪装成代码步骤。各代码锚点 SHALL 保留上下各 20 行、命中高亮与既有裁剪规则。新增展示说明 SHALL 中英文成对，保持 suggestion/suggestion_en、默认中文和安全转义；默认 V2、显式 V1 及三个工件 SHALL 保持。

#### Scenario: 注册行与断言行跨文件

- **WHEN** add_test、target source、架构条件和断言位于不同文件
- **THEN** SHALL 分别保留真实 span/context，并只连接有真实来源的上游
- **AND** 不同来源 MUST NOT 复用同一伪造位置或强行串成一条 primaryPath

#### Scenario: 兼容、转义与配置差异

- **WHEN** 老消费者忽略 extension、用户选择 V1，或名称包含 HTML 特殊字符
- **THEN** 原有必需结构 SHALL 可消费，HTML SHALL 安全转义并保持默认中文
- **AND** 新旧输出差异 SHALL 有逐项事实/关系/分类/展示审校，变化不得通过自动覆盖 oracle 获得批准
