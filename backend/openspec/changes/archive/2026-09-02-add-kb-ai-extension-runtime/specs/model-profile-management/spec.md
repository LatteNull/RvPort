## ADDED Requirements

### Requirement: 阶段模型绑定必须支持 KB_AI_EXTENSION
模型 profile 管理 SHALL 支持 `KB_AI_EXTENSION` 阶段绑定，使 KB AI 扩展扫描只能使用管理员配置的受控模型 profile 和 agent runtime。

#### Scenario: 查询 KB AI 扩展阶段绑定
- **WHEN** 超级管理员调用阶段模型绑定查询 API
- **THEN** 响应 SHALL 包含 `KB_AI_EXTENSION` 阶段及其当前绑定的模型 profile 摘要和 agent runtime 摘要
- **AND** 未绑定时 SHALL 明确返回空绑定状态

#### Scenario: 保存 KB AI 扩展阶段绑定
- **WHEN** 超级管理员保存 `KB_AI_EXTENSION` 阶段绑定
- **THEN** 后端 SHALL 校验绑定的模型 profile 存在且已启用
- **AND** 后端 SHALL 校验绑定的 agent runtime 存在且已启用
- **AND** 后端 SHALL 保存该阶段到模型 profile 和 agent runtime 的唯一绑定

#### Scenario: KB AI 扩展解析阶段模型
- **WHEN** 后端准备执行 KB AI 扩展扫描
- **THEN** 后端 SHALL 通过 `KB_AI_EXTENSION` 阶段绑定解析模型 profile 和 agent runtime
- **AND** 业务任务请求 MUST NOT 直接提交 base URL、API key、agent 类型、可执行路径或任意模型参数

#### Scenario: KB AI 扩展阶段配置不可用
- **WHEN** 阶段未绑定、绑定 profile 已禁用、绑定 agent runtime 已禁用或 profile 缺少必要连接信息
- **THEN** 后端 SHALL 返回 KB AI 扩展功能不可用错误
- **AND** 响应 MUST NOT 泄漏 provider secret、agent 命令或内部执行细节

### Requirement: 模型 Profile Agent Probe 必须支持 KB AI 扩展 schema
模型 profile 管理 SHALL 能验证指定 agent runtime 是否可用于 KB AI 扩展输出 schema。

#### Scenario: 测试 KB AI 扩展输出 schema
- **WHEN** 超级管理员测试模型 profile 并选择 agent runtime
- **THEN** 后端 SHALL 使用接近 KB AI 扩展场景的最小输入验证指定 agent 能返回可解析的 AI 扩展 JSONL 或等效结构化结果
- **AND** 分项结果 SHALL 能表达该 runtime 是否可用于 `KB_AI_EXTENSION` 阶段

#### Scenario: 兼容性矩阵包含 KB AI 扩展能力
- **WHEN** 超级管理员查询模型 profile 详情或 agent probe 结果列表
- **THEN** 响应 SHALL 返回该 profile 对各 agent runtime 的 KB AI 扩展 schema 兼容状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 prompt 或服务器真实路径
