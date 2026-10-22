## Purpose

定义 RvPort 后端模型 profile 管理、模型可用性测试和阶段模型绑定的配置边界，使测试结果比较等阶段只能从受控模型配置中解析运行参数。
## Requirements
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
后端 SHALL 提供阶段模型绑定能力，使 `TEST_LOG_COMPARE` 测试结果比较阶段和 `KB_AI_EXTENSION` 知识库 AI 扩展阶段可以选择一个已启用模型 profile 和一个已启用 agent runtime。

#### Scenario: 查询阶段模型绑定
- **WHEN** 超级管理员调用阶段模型绑定查询 API
- **THEN** 后端 SHALL 返回 `TEST_LOG_COMPARE` 和 `KB_AI_EXTENSION` 阶段及其当前绑定的模型 profile 摘要和 agent runtime 摘要
- **AND** 未绑定时 SHALL 明确返回空绑定状态

#### Scenario: 保存阶段模型绑定
- **WHEN** 超级管理员保存阶段模型绑定
- **THEN** 后端 SHALL 校验阶段名称属于后端白名单，当前允许 `TEST_LOG_COMPARE` 和 `KB_AI_EXTENSION`
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

#### Scenario: 测试 KB AI 扩展输出 schema
- **WHEN** 超级管理员测试用于 `KB_AI_EXTENSION` 的模型 profile 和 agent runtime
- **THEN** 后端 SHALL 使用接近 KB AI 扩展场景的最小输入验证指定 agent 能返回可解析的 AI 扩展 JSONL 或等效结构化结果
- **AND** 结果 SHALL 包含 `KB_AI_EXTENSION_SCHEMA` 或等效分项状态

#### Scenario: 返回聚合兼容性状态
- **WHEN** 模型 profile 测试完成
- **THEN** API 响应 SHALL 返回 agent 类型、agent runtime ID、基础可用状态、agent 兼容状态、测试比较兼容状态和 KB AI 扩展兼容状态
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

### Requirement: 模型 Profile 连通性测试必须独立于 Agent Probe
模型 profile 管理 SHALL 提供独立连通性测试能力，用于验证模型 provider 配置是否可用，且 SHALL NOT 在连通性测试中启动 agent runtime。

#### Scenario: 测试模型连通性
- **WHEN** 超级管理员对模型 profile 发起连通性测试
- **THEN** 后端 SHALL 使用 profile 的 provider 类型、base URL、模型名、wire API、timeout 和 API key 执行最小模型调用
- **AND** 后端 SHALL 返回连通性状态、脱敏消息、测试时间和耗时
- **AND** 后端 SHALL 保存最近一次连通性测试摘要
- **AND** 响应和数据库 MUST NOT 保存 API key、授权头、完整 prompt 或服务器真实敏感路径

#### Scenario: 临时覆盖配置测试连通性
- **WHEN** 超级管理员提交临时覆盖配置执行连通性测试
- **THEN** 后端 SHALL 使用覆盖后的配置执行测试
- **AND** 临时覆盖中的 API key MUST NOT 被持久化，除非调用保存 API
- **AND** 测试结果中的错误信息 MUST 脱敏

#### Scenario: 连通性测试不启动 Agent
- **WHEN** 后端执行模型连通性测试
- **THEN** 后端 SHALL NOT 创建 agent workspace
- **AND** 后端 SHALL NOT 调用 Codex、DeepSeek Harness、OpenCode 或其他 agent runtime adapter

### Requirement: 模型 Profile Agent Probe 必须支持多 Runtime 选择
模型 profile 管理 SHALL 支持超级管理员选择一个或多个 agent runtime 对模型 profile 执行阶段无关的通用兼容性 probe，并 SHALL 独立保存每个模型 Profile 与 agent runtime 组合的分项结果。

#### Scenario: 创建多 Agent Probe Run
- **WHEN** 超级管理员提交 `agentRuntimeIds` 列表测试模型 profile
- **THEN** 后端 SHALL 校验列表非空、runtime 存在且启用
- **AND** 后端 SHALL 创建一次 agent probe run
- **AND** 响应 SHALL 返回 `runId`、聚合状态、所选 runtime 摘要和创建时间
- **AND** 后端 SHALL 在后台执行所选 agent runtime 的通用兼容性 probe
- **AND** 后端 MUST NOT 查询或依赖该组合是否绑定到任何业务阶段

#### Scenario: 查询 Agent Probe Run
- **WHEN** 超级管理员查询 agent probe run
- **THEN** 后端 SHALL 返回 run 的聚合状态、profile 摘要、所选 runtime 摘要、每个 runtime 的通用分项 probe 结果、脱敏消息、开始时间和结束时间
- **AND** 单个 runtime 失败 SHALL 只影响该 runtime 的结果和 run 聚合状态
- **AND** 响应 MUST NOT 返回 API key、授权头、完整 agent 命令、完整 prompt 或服务器真实敏感路径

#### Scenario: 查询 Profile Agent 兼容性矩阵
- **WHEN** 超级管理员查询模型 profile 详情或 agent probe 结果列表
- **THEN** 后端 SHALL 返回该 profile 对各 agent runtime 的最近通用兼容性状态
- **AND** 每个结果 SHALL 包含 agent runtime ID、agent 类型、Agent 响应状态、workspace 读取状态、workspace 写入状态、聚合兼容状态、最近测试时间和脱敏消息
- **AND** 每个结果 MUST NOT 包含测试比较、KB AI 扩展或其他业务阶段的兼容性字段

#### Scenario: 后续新增 Agent Runtime 或业务阶段
- **WHEN** 后端新增新的 agent runtime 类型或新的 Agent 业务阶段
- **THEN** 模型 profile agent probe SHALL 能为新 runtime 记录独立通用结果
- **AND** 新业务阶段 MUST NOT 要求改变模型 Agent 兼容性结果结构
- **AND** 后端 SHALL NOT 要求改变 `model_profiles` 的基础配置结构

### Requirement: 阶段输出契约不得改写通用 Agent 兼容性
模型管理 SHALL 将阶段任务输出验证与模型 Profile 和 Agent Runtime 的通用兼容性状态分离。

#### Scenario: 阶段任务输出合法
- **WHEN** 已绑定的模型与 Agent Runtime 成功生成某业务阶段要求的输出
- **THEN** 该阶段任务 SHALL 按自身契约完成
- **AND** 后端 MUST NOT 因该业务成功额外创建或修改通用兼容性结果

#### Scenario: 阶段任务输出不合法
- **WHEN** 已绑定的模型与 Agent Runtime 生成不符合业务阶段 schema 的输出
- **THEN** 该阶段任务 SHALL 按自身错误语义失败
- **AND** 后端 MUST NOT 将该失败写成模型与 Agent Runtime 的通用不兼容结果

### Requirement: 模型 Profile 测试旧接口必须作为兼容入口
模型 profile 管理 SHALL 保留旧模型 profile 测试接口的兼容语义，但新功能 SHALL 使用独立连通性测试和多 agent probe run API。

#### Scenario: 旧接口兼容调用
- **WHEN** 旧前端调用 `POST /api/admin/model-profiles/{profileId}:test`
- **THEN** 后端 SHALL 返回兼容格式的单 agent 测试结果或明确迁移提示
- **AND** 后端 SHALL 使用指定 `agentRuntimeId`、阶段绑定 runtime 或默认 runtime 之一进行兼容处理
- **AND** 响应 MUST NOT 泄漏 provider secret、完整 agent 命令或服务器真实敏感路径

#### Scenario: 新前端使用新接口
- **WHEN** 前端需要测试模型 profile
- **THEN** 前端 SHALL 优先调用连通性测试 API 验证模型配置
- **AND** 前端 SHALL 调用多 agent probe run API 验证用户选择的 agent runtime 列表

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

### Requirement: Agent Probe 必须从稳定的结构化输出边界解析结果
模型 Profile Agent Probe SHALL 优先从 Agent Runtime 的 stdout 提取结构化结果，并仅在 stdout 不包含满足当前检查契约的 JSON 时，才从移除传输包装后的 merged output 回退提取。诊断日志中的通道标签、ANSI 控制字符和输出缓冲分块 MUST NOT 导致有效 Agent 结果被误判为不兼容。

#### Scenario: stdout 直接返回预期 JSON
- **WHEN** Agent Runtime 以零退出码结束且 stdout 包含满足当前 probe 预期字段的 JSON 对象
- **THEN** 后端 SHALL 将该 probe 判定为成功
- **AND** merged output 中是否存在 `[STDOUT]` 标签 MUST NOT 改变结果

#### Scenario: stdout 包含普通日志和多行 JSON
- **WHEN** stdout 在最终结果前后包含普通日志、Markdown 代码块或多行格式化 JSON
- **THEN** 后端 SHALL 提取完整 JSON 对象并按当前 probe 预期字段验证

#### Scenario: merged output 包含 ANSI 和通道标签
- **WHEN** stdout 中没有可用结果，但 merged output 包含 ANSI 控制字符、`[STDOUT]`、`[STDERR]` 和满足契约的 JSON
- **THEN** 后端 SHALL 清除传输包装并成功提取该 JSON
- **AND** 清洗 MUST NOT 改写 JSON 字符串内部的普通内容

#### Scenario: 输出包含多个 JSON 候选
- **WHEN** Agent 输出包含多个合法 JSON 对象，其中只有部分对象满足当前 probe 的预期字段
- **THEN** 后端 SHALL 从后向前选择最后一个满足全部预期字段的对象
- **AND** 不匹配的 CLI 状态 JSON MUST NOT 导致有效结果被忽略或误判成功

#### Scenario: 进程失败但输出包含有效 JSON
- **WHEN** Agent Runtime 超时或以非零退出码结束，同时输出中存在满足字段要求的 JSON
- **THEN** 后端 SHALL 保持超时或执行失败状态
- **AND** MUST NOT 仅因存在 JSON 而将 probe 判定为成功

#### Scenario: 输出不存在匹配对象
- **WHEN** Agent Runtime 零退出但 stdout 与清洗后的 merged output 均不存在满足预期字段的 JSON 对象
- **THEN** 后端 SHALL 返回 `AGENT_PROBE_OUTPUT_INVALID`
- **AND** 失败消息 SHALL 使用脱敏且限制长度的诊断输出

#### Scenario: workspace 写入检查
- **WHEN** Agent 返回 workspace write 成功 JSON
- **THEN** 后端 SHALL 继续验证约定输出文件存在、文件内容为 JSON 对象且 marker 匹配
- **AND** 只有响应与文件检查全部通过时 SHALL 将 workspace write probe 判定为成功

### Requirement: Agent Probe 结构化解析必须具备独立单元测试
后端 SHALL 为结构化输出提取和兼容性判定提供不依赖外部模型、数据库、Redis、RabbitMQ、MinIO、SSH 或 Docker 的单元测试，覆盖正常行为、异常路径和 edge case。项目整体与受影响模块的行覆盖率及可用的分支覆盖率 SHALL 均不低于 90%。

#### Scenario: 独立运行解析测试
- **WHEN** 开发者在无外部服务环境运行 Maven 单元测试
- **THEN** 测试 SHALL 使用 mock 或 fixture 输出覆盖 Codex、DeepSeek Harness 和 OpenCode 的结构化输出形态
- **AND** 测试 SHALL 覆盖 ANSI、通道标签、日志前后缀、多行 JSON、Markdown fence、多个对象、字符串内花括号、截断 JSON、字段不匹配、超时、非零退出和凭据脱敏

#### Scenario: 验收覆盖率
- **WHEN** 本 change 完成实现并执行覆盖率检查
- **THEN** JaCoCo SHALL 将未被测试加载的项目自有可执行代码纳入统计
- **AND** 项目整体与受影响模块行覆盖率、分支覆盖率 SHALL 均达到至少 90%
