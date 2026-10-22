## MODIFIED Requirements

### Requirement: 可追溯自动化测试批次历史

系统 SHALL 在默认页将当前条件和配置与项目跨源码版本的批次记录并列展示。记录 SHALL 按批次关联两侧运行与比较状态，支持单侧日志与比较详情，并遵循 project-stage-runtime 的独立读取和聚合分页规则。

#### Scenario: 查看已完成的测试批次

- **WHEN** 用户浏览自动化测试 Drawer 的历史记录
- **THEN** 系统 SHALL 按服务端创建时间倒序展示批次及源码版本、两侧运行状态和比较状态，并可进入只读详情；接口未提供创建时间字段时不得伪造时间

### Requirement: 自动化测试必须以 latest 锚定当前批次

自动化测试 SHALL 使用 `test` readiness 的 `BUILD_VALIDATION` prerequisite 作为唯一门禁，`automated-tests/latest` 的 `CURRENT` 结果 SHALL 用于当前配置参考与记录补齐，不替代默认跨版本批次列表。

#### Scenario: latest 仅返回批次单侧结果

- **WHEN** backend latest 只包含当前批次的一侧运行
- **THEN** frontend SHALL 从项目测试记录聚合同一批次两侧结果
- **AND** List SHALL NOT 改变当前执行门禁

#### Scenario: 展示结果比较

- **WHEN** 当前或历史批次存在比较结果
- **THEN** 页面 SHALL 分层展示一致性状态、风险、摘要和处理建议
- **AND** 失败时 SHALL 提供按需日志入口，不得将 Agent 原始输出直接铺成业务摘要
