## MODIFIED Requirements

### Requirement: 阶段模型绑定必须从已配置 Profile 中选择
后端 SHALL 提供阶段模型绑定能力，使 `TEST_LOG_COMPARE` 测试结果比较阶段可以选择一个已启用模型 profile 和一个已启用 agent runtime。

#### Scenario: 查询阶段模型绑定
- **WHEN** 超级管理员调用阶段模型绑定查询 API
- **THEN** 后端 SHALL 返回 `TEST_LOG_COMPARE` 阶段及其当前绑定的模型 profile 摘要和 agent runtime 摘要
- **AND** 未绑定时 SHALL 明确返回空绑定状态

#### Scenario: 保存阶段模型绑定
- **WHEN** 超级管理员保存阶段模型绑定
- **THEN** 后端 SHALL 校验阶段名称属于后端白名单，且本 change 只允许 `TEST_LOG_COMPARE`
- **AND** 后端 SHALL 校验绑定的模型 profile 存在且已启用
- **AND** 后端 SHALL 校验绑定的 agent runtime 存在且已启用
- **AND** 后端 SHALL 保存阶段到模型 profile 和 agent runtime 的唯一绑定

#### Scenario: 阶段绑定非法
- **WHEN** 请求包含未知阶段、已禁用 profile、不存在 profile、已禁用 agent runtime、不存在 agent runtime 或重复阶段绑定
- **THEN** 后端 SHALL 返回统一参数或业务错误
- **AND** 后端 MUST NOT 保存部分非法绑定

#### Scenario: 运行时解析阶段模型
- **WHEN** 后续测试结果比较 agent runtime 需要执行模型任务
- **THEN** 后端 SHALL 通过阶段绑定解析模型 profile 和 agent runtime
- **AND** 如果阶段未绑定、绑定 profile 已禁用或绑定 agent runtime 已禁用，后端 SHALL 返回明确业务错误
- **AND** 业务任务请求 MUST NOT 直接提交 base URL、API key、agent 类型、可执行路径或任意模型参数

### Requirement: 测试结果比较必须使用 TEST_LOG_COMPARE 阶段绑定
模型 profile 管理 SHALL 将 `TEST_LOG_COMPARE` 阶段绑定作为测试结果比较 agent runtime 的唯一模型和 agent 来源。

#### Scenario: 比较任务解析模型
- **WHEN** 后端准备自动创建或执行测试结果比较任务
- **THEN** 后端 SHALL 通过 `TEST_LOG_COMPARE` 阶段绑定解析模型 profile 和 agent runtime
- **AND** 后端 MUST NOT 从业务请求体读取 base URL、模型名、API key、provider 参数、agent 类型或 agent 可执行路径

#### Scenario: 比较任务模型不可用
- **WHEN** 阶段未绑定、绑定 profile 被禁用、绑定 agent runtime 被禁用或 profile 缺少必要连接信息
- **THEN** 后端 SHALL 将自动比较摘要标记为不可用或返回测试结果比较功能不可用错误
- **AND** 后端 MUST NOT 泄漏 provider secret、agent 命令或内部执行细节

### Requirement: 模型 Profile 测试必须验证指定 agent 兼容性
模型 profile 管理 SHALL 在可用性测试中验证模型是否支持指定 agent runtime 的工作模式，并 SHALL 返回 agent 类型、agent runtime ID、分项 probe 结果和聚合兼容性状态。

#### Scenario: 测试基础文本能力
- **WHEN** 超级管理员测试模型 profile
- **THEN** 后端 SHALL 验证模型能够完成基础文本 JSON 输出
- **AND** 结果 SHALL 包含 `BASIC_TEXT` 或等效分项状态

#### Scenario: 测试 agent 纯文本能力
- **WHEN** 超级管理员测试模型 profile 并指定 agent runtime
- **THEN** 后端 SHALL 使用该 profile 配置和指定 agent runtime 运行纯文本最小任务
- **AND** 结果 SHALL 包含 `AGENT_TEXT` 或等效分项状态
- **AND** 结果 SHALL 包含当前测试的 `agentType` 和 `agentRuntimeId`

#### Scenario: 测试 agent workspace 工具闭环
- **WHEN** 超级管理员测试模型 profile 并指定 agent runtime
- **THEN** 后端 SHALL 创建临时 workspace 和测试输入文件
- **AND** 后端 SHALL 使用指定 agent runtime 要求读取该文件并返回指定 JSON
- **AND** 测试 SHALL 覆盖模型发起工具调用、agent 执行工具、工具结果回传和最终 JSON 输出的完整闭环
- **AND** 结果 SHALL 包含 `AGENT_WORKSPACE_TOOL` 或等效分项状态
- **AND** 结果 SHALL 包含当前测试的 `agentType` 和 `agentRuntimeId`

#### Scenario: 测试测试比较输出 schema
- **WHEN** 超级管理员测试用于 `TEST_LOG_COMPARE` 的模型 profile 和 agent runtime
- **THEN** 后端 SHALL 使用接近测试结果比较场景的最小输入验证指定 agent 能返回可解析的比较 JSON
- **AND** 结果 SHALL 包含 `TEST_COMPARE_SCHEMA` 或等效分项状态

#### Scenario: 返回聚合兼容性状态
- **WHEN** 模型 profile 测试完成
- **THEN** API 响应 SHALL 返回 agent 类型、agent runtime ID、基础可用状态、agent 兼容状态和测试比较兼容状态
- **AND** 后端 SHALL 保存最近一次测试的脱敏摘要、分项结果和测试时间
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令或服务器真实路径

#### Scenario: 基础可用但 agent 不兼容
- **WHEN** 模型基础文本测试通过但 workspace 工具闭环测试失败
- **THEN** 后端 SHALL 将基础可用状态标记为可用
- **AND** 后端 SHALL 将当前 agent 兼容状态标记为不兼容
- **AND** 脱敏消息 SHALL 明确说明该模型不能用于当前 agent runtime 工作模式

#### Scenario: 后续新增 agent 类型
- **WHEN** 后端新增非 `CODEX`、`DEEPSEEK_HARNESS` 或 `OPENCODE` 的 agent 执行器
- **THEN** 模型 profile 测试结果 SHALL 能记录该 agent 类型对应的分项 probe 结果
- **AND** 阶段绑定 SHALL 能依据该 agent 类型判断模型是否适用于对应阶段
- **AND** 后端 SHALL NOT 要求重建模型 profile 的基础数据结构
