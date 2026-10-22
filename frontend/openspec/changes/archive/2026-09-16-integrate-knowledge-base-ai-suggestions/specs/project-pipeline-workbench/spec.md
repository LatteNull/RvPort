## ADDED Requirements

### Requirement: 知识库扫描结果支持生成 AI 补充建议

知识库扫描 Drawer SHALL 在当前扫描成功且满足服务端 readiness 时允许用户启动 AI 扩展任务，并 SHALL 以服务端运行记录为任务状态事实来源。

#### Scenario: 可以生成 AI 建议

- **WHEN** 当前知识库扫描成功、存在 Finding 且 AI 模型配置可用
- **THEN** 扫描结果概览 SHALL 提供“生成 AI 建议”操作
- **AND** 用户确认后 SHALL 为当前扫描创建 AI 扩展任务

#### Scenario: AI 建议暂不可生成

- **WHEN** 服务端 readiness 返回扫描未成功、没有 Finding 或模型未配置
- **THEN** 页面 SHALL 禁用生成操作并展示对应的可理解原因
- **AND** 页面 SHALL NOT 根据客户端推测绕过服务端 readiness

#### Scenario: AI 扩展正在执行

- **WHEN** 当前扫描已有 `PENDING`、`QUEUED` 或 `RUNNING` 的 AI 扩展记录
- **THEN** 页面 SHALL 展示排队或运行状态并禁止重复启动
- **AND** 页面 SHALL 继续允许用户浏览扫描结果和 Finding 详情

#### Scenario: AI 扩展任务进入终态

- **WHEN** 当前扫描的 AI 扩展任务成功、部分成功或失败
- **THEN** 页面 SHALL 刷新该扫描的 AI 运行记录和 Finding 结果
- **AND** 成功或部分成功时 SHALL 允许用户重新生成建议
- **AND** 失败时 SHALL 展示失败状态和重新生成入口

### Requirement: AI 建议保持为扫描内附加能力

系统 SHALL 将知识库 AI 扩展集成在知识库扫描 Drawer 内，并 SHALL 保持当前精简工作流拓扑。

#### Scenario: 渲染项目流程

- **WHEN** 项目工作台渲染流程节点和连线
- **THEN** 系统 SHALL NOT 增加独立的知识库 AI 扩展节点
- **AND** 用户 SHALL 从当前知识库扫描结果进入 AI 建议能力
