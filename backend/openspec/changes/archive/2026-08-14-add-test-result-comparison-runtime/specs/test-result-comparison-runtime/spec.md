## ADDED Requirements

### Requirement: 测试结果比较运行时必须作为自动化测试节点的自动后续步骤
后端 SHALL 在自动化测试节点完成两侧测试运行后自动创建测试结果比较运行，并在模型可用时自动投递 `TEST_LOG_COMPARE` 长任务。

#### Scenario: 自动化测试完成后自动创建比较
- **WHEN** 同一自动化测试节点下 source 和 target 两侧测试记录均进入可比较终态
- **THEN** 后端 SHALL 自动创建测试比较运行记录
- **AND** 后端 SHALL 使用两侧测试记录作为 `sourceTestRunId` 和 `targetTestRunId`
- **AND** 后端 SHALL 在模型配置可用时自动创建 `TEST_LOG_COMPARE` 任务
- **AND** 前端 MUST NOT 需要额外点击“创建比较”才能获得比较报告

#### Scenario: 等待另一侧测试完成
- **WHEN** 自动化测试节点只有一侧测试记录进入终态
- **THEN** 后端 SHALL 保存该侧测试结果
- **AND** 后端 MUST NOT 立即创建最终比较报告
- **AND** 后端 SHALL 在另一侧测试记录完成后再尝试创建比较运行

#### Scenario: 不可比较的测试记录
- **WHEN** 自动化测试节点缺少 source 或 target 测试记录，或某侧测试记录被取消
- **THEN** 后端 SHALL 记录比较不可用或不可比较摘要
- **AND** 后端 MUST NOT 重新执行远程测试命令

#### Scenario: 比较任务不重新执行测试
- **WHEN** worker 执行测试结果比较任务
- **THEN** worker SHALL 只读取已有 `test_runs`、任务日志和测试报告 artifact
- **AND** worker MUST NOT 重新连接远程环境运行测试命令

### Requirement: 测试结果比较必须在模型未配置时明确不可用
测试结果比较 SHALL 依赖 `TEST_LOG_COMPARE` 阶段绑定的可用模型 profile；未配置或不可用时，自动化测试 SHALL 保持正常完成，比较摘要 SHALL 标记为不可用。

#### Scenario: 未配置模型时自动比较
- **WHEN** 自动化测试两侧运行完成，但 `TEST_LOG_COMPARE` 阶段未绑定模型 profile
- **THEN** 后端 SHALL 创建或更新比较运行摘要为 `UNAVAILABLE`
- **AND** 比较运行 SHALL 记录 `TEST_COMPARE_MODEL_NOT_CONFIGURED` 或等效原因
- **AND** 前端 SHALL 能在自动化测试节点中展示测试结果和“比较功能未配置模型，当前不可用”的提示
- **AND** 后端 MUST NOT 将自动化测试记录标记为失败

#### Scenario: 模型配置不可用时自动比较
- **WHEN** `TEST_LOG_COMPARE` 阶段绑定的模型 profile 已禁用、缺少 API key、缺少 base URL、缺少模型名或 executable path 不可用
- **THEN** 后端 SHALL 将比较运行标记为 `UNAVAILABLE` 或明确失败前置状态
- **AND** 后端 MUST NOT 创建 agent 执行任务
- **AND** 响应、任务事件和日志 MUST NOT 泄漏 API key、密文、授权头或服务器真实路径

#### Scenario: 自动化测试不依赖模型配置
- **WHEN** 系统没有配置 `TEST_LOG_COMPARE` 模型 profile
- **THEN** 自动化测试创建、执行、查询、取消和日志下载 SHALL 继续正常工作
- **AND** 后端 MUST NOT 因模型缺失拒绝 `AUTOMATED_TEST` 任务

### Requirement: 测试结果比较必须聚合日志和报告作为 agent 输入
测试结果比较运行时 SHALL 从两条测试记录聚合状态、退出码、日志和报告 artifact，生成受控 agent 输入。

#### Scenario: 聚合测试输出
- **WHEN** worker 准备比较输入
- **THEN** 输入 SHALL 包含两侧测试状态、退出码、输出摘要、源码版本、环境摘要和任务 ID
- **AND** 输入 SHALL 包含两侧 stdout/stderr 日志内容或受控摘要
- **AND** 输入 SHALL 包含两侧已回收报告 artifact 的内容或受控摘要
- **AND** 输入 MUST NOT 包含明文凭据、环境变量明文、服务器真实路径或对象存储内部 key

#### Scenario: 输入过大时裁剪
- **WHEN** 单个日志、单个报告或总输入超过后端定义的大小上限
- **THEN** 后端 SHALL 使用确定性策略裁剪或摘要化输入
- **AND** 后端 SHALL 在比较运行摘要中记录发生过裁剪
- **AND** 后端 SHALL 保留原始日志和 artifact 的查询或下载引用

### Requirement: 测试结果比较必须调用 Codex agent 并保存结构化结果
测试结果比较运行时 SHALL 通过 `TEST_LOG_COMPARE` 阶段解析的模型 profile 调用 Codex agent，并保存结构化比较结果。

#### Scenario: agent 比较成功
- **WHEN** Codex agent 返回合法比较结果
- **THEN** 后端 SHALL 保存比较运行状态为 `SUCCEEDED`
- **AND** 后端 SHALL 保存总体结论、风险等级、置信度、摘要和建议
- **AND** 后端 SHALL 保存结构化差异项
- **AND** 后端 SHALL 保存原始 agent 输出 artifact

#### Scenario: agent 输出不可解析
- **WHEN** Codex agent 返回非 JSON、字段缺失或结构不合法的输出
- **THEN** 后端 SHALL 保存原始 agent 输出 artifact
- **AND** 后端 SHALL 将比较运行标记为 `FAILED` 或等效受控失败状态
- **AND** 后端 SHALL 返回脱敏错误摘要

#### Scenario: agent 执行失败
- **WHEN** Codex agent 超时、进程退出码非 0 或 provider 调用失败
- **THEN** 后端 SHALL 将比较运行标记为 `FAILED` 或 `TIMEOUT`
- **AND** 后端 SHALL 保存脱敏失败摘要
- **AND** 任务状态 SHALL 与比较运行状态一致

### Requirement: 测试结果比较必须支持查询、分页、过滤和排序
后端 SHALL 提供测试比较运行和差异项查询能力，并 SHALL 支持分页、过滤和排序。

#### Scenario: 查询项目比较列表
- **WHEN** 用户查询项目测试结果比较列表
- **THEN** 后端 SHALL 返回分页比较运行列表
- **AND** 列表接口 SHALL 支持按状态、源码版本、测试运行 ID、环境、风险等级和时间范围过滤
- **AND** 列表接口 SHALL 支持按创建时间、完成时间、状态和风险等级排序

#### Scenario: 查询比较详情
- **WHEN** 用户查询单个测试比较运行详情
- **THEN** 后端 SHALL 校验用户有权访问所属项目
- **AND** 响应 SHALL 返回比较运行摘要、两侧测试记录摘要、状态、总体结论、风险等级、置信度、建议和 artifact 摘要
- **AND** 响应 MUST NOT 返回完整日志、完整 agent 输入、API key、对象存储内部 key 或服务器真实路径

#### Scenario: 查询比较差异项
- **WHEN** 用户查询测试比较差异项列表
- **THEN** 后端 SHALL 返回分页差异项列表
- **AND** 列表接口 SHALL 支持按严重程度、差异类型、置信度和关键字过滤
- **AND** 列表接口 SHALL 支持按严重程度、置信度、创建时间和序号排序

### Requirement: 测试结果比较必须通过任务事件暴露运行状态
测试结果比较运行时 SHALL 复用项目级 SSE 和任务日志机制暴露运行状态。

#### Scenario: 比较任务状态推送
- **WHEN** 比较任务进入 `RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED`、`TIMEOUT` 或 `UNAVAILABLE`
- **THEN** 后端 SHALL 通过项目级 SSE 推送任务状态或比较摘要事件
- **AND** 前端 SHALL 能通过比较详情接口查询历史结果

#### Scenario: 取消比较任务
- **WHEN** 用户取消运行中的测试结果比较任务
- **THEN** 后端 SHALL 复用任务取消机制取消 Codex agent 进程
- **AND** 已保存的比较运行、日志和 artifact SHALL 保留为取消前的事实记录
