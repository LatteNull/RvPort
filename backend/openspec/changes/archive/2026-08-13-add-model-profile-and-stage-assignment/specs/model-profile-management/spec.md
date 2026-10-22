## ADDED Requirements

### Requirement: 模型 Profile 管理必须支持多个模型配置
后端 SHALL 提供超级管理员模型 profile 管理能力，用于维护多个可供阶段绑定使用的 OpenAI-compatible 模型配置。

#### Scenario: 创建模型 profile
- **WHEN** 超级管理员调用模型 profile 创建 API 并提交名称、provider 类型、base URL、模型名、wire API、超时配置和 API key
- **THEN** 后端 SHALL 创建模型 profile
- **AND** 后端 SHALL 校验 profile 名称唯一
- **AND** 后端 SHALL 校验 provider 类型只允许 `OPENAI_COMPATIBLE`
- **AND** 后端 SHALL 校验 wire API 只允许 `RESPONSES` 或 `CHAT`
- **AND** 后端 SHALL 加密保存 API key
- **AND** API 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 查询模型 profile 列表
- **WHEN** 超级管理员调用模型 profile 列表 API
- **THEN** 后端 SHALL 返回分页列表
- **AND** 列表项 SHALL 包含 profile ID、名称、启用状态、provider 类型、base URL、模型名、wire API、API key 配置状态、最近测试状态、最近测试时间、创建时间和更新时间
- **AND** 列表接口 SHALL 支持按启用状态、provider 类型、测试状态和关键字过滤
- **AND** 列表接口 SHALL 支持按名称、创建时间、更新时间和最近测试时间排序

#### Scenario: 更新模型 profile
- **WHEN** 超级管理员更新模型 profile
- **THEN** 后端 SHALL 只允许更新名称、启用状态、连接参数、模型名、wire API、超时配置和 API key
- **AND** 如果请求未提交 API key 字段，后端 SHALL 保留已有 API key
- **AND** 如果请求提交空 API key，后端 SHALL 清空已有 API key
- **AND** API 响应 MUST NOT 返回 API key 明文或密文

#### Scenario: 删除模型 profile
- **WHEN** 超级管理员删除模型 profile
- **THEN** 后端 SHALL 在该 profile 未被任何阶段绑定时允许删除或软删除
- **AND** 如果 profile 已被阶段绑定，后端 SHALL 拒绝删除并返回明确业务错误

#### Scenario: 普通用户不能管理模型 profile
- **WHEN** 非超级管理员调用模型 profile 创建、更新、删除、测试或列表 API
- **THEN** 后端 SHALL 返回无权限错误
- **AND** 响应 MUST NOT 泄漏 API key、密文或内部执行细节

### Requirement: 模型 Profile 必须支持可用性测试
后端 SHALL 允许超级管理员对已保存或临时覆盖的模型 profile 执行最小可用性测试。

#### Scenario: 测试已保存模型 profile
- **WHEN** 超级管理员调用模型 profile 测试 API
- **THEN** 后端 SHALL 使用该 profile 的已保存配置运行 Codex provider 探测
- **AND** 后端 SHALL 保存最近一次测试状态、脱敏消息和测试时间
- **AND** API 响应 SHALL 返回成功或失败状态、脱敏消息和测试时间

#### Scenario: 使用临时覆盖测试模型 profile
- **WHEN** 超级管理员调用模型 profile 测试 API 并提交临时覆盖配置
- **THEN** 后端 SHALL 使用覆盖后的配置执行测试
- **AND** 临时覆盖中的 API key MUST NOT 被持久化，除非调用保存 API
- **AND** 测试结果中的错误信息 MUST 脱敏

#### Scenario: 测试配置不完整
- **WHEN** 模型 profile 未启用、缺少 API key、缺少 base URL 或缺少模型名
- **THEN** 后端 SHALL 返回明确测试失败或参数错误
- **AND** 响应 MUST NOT 泄漏 API key、授权头或服务器真实路径

### Requirement: 阶段模型绑定必须从已配置 Profile 中选择
后端 SHALL 提供阶段模型绑定能力，使 `TEST_LOG_COMPARE` 测试结果比较阶段可以选择一个已启用模型 profile。

#### Scenario: 查询阶段模型绑定
- **WHEN** 超级管理员调用阶段模型绑定查询 API
- **THEN** 后端 SHALL 返回 `TEST_LOG_COMPARE` 阶段及其当前绑定的模型 profile 摘要
- **AND** 未绑定时 SHALL 明确返回空绑定状态

#### Scenario: 保存阶段模型绑定
- **WHEN** 超级管理员保存阶段模型绑定
- **THEN** 后端 SHALL 校验阶段名称属于后端白名单，且本 change 只允许 `TEST_LOG_COMPARE`
- **AND** 后端 SHALL 校验绑定的模型 profile 存在且已启用
- **AND** 后端 SHALL 保存阶段到模型 profile 的唯一绑定

#### Scenario: 阶段绑定非法
- **WHEN** 请求包含未知阶段、已禁用 profile、不存在 profile 或重复阶段绑定
- **THEN** 后端 SHALL 返回统一参数或业务错误
- **AND** 后端 MUST NOT 保存部分非法绑定

#### Scenario: 运行时解析阶段模型
- **WHEN** 后续测试结果比较 agent runtime 需要执行模型任务
- **THEN** 后端 SHALL 通过阶段绑定解析模型 profile
- **AND** 如果阶段未绑定或绑定 profile 已禁用，后端 SHALL 返回明确业务错误
- **AND** 业务任务请求 MUST NOT 直接提交 base URL、API key 或任意模型参数
