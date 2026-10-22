# knowledge-base-scan Specification

## Purpose

定义 kb 节点对当前源码的扫描、结果筛选、历史和扫描内 AI 补充建议。单条 Finding 详情由 knowledge-base-finding-detail 定义。

## Requirements

### Requirement: 当前知识库扫描

扫描 SHALL 使用 `kb` readiness 的 `ACTIVE_SOURCE`、`X86_BUILD` 条件及扫描 latest；页面状态遵循 project-stage-runtime。

#### Scenario: 开始扫描

- **WHEN** 当前源码和 x86 构建条件满足且用户确认扫描配置
- **THEN** 页面 SHALL 创建扫描任务，返回当前结果视图并提示已启动
- **AND** 页面 SHALL 不因源码导入或进入节点而自动创建扫描

#### Scenario: 浏览结果与历史

- **WHEN** 用户查看成功扫描
- **THEN** 页面 SHALL 提供结果统计、分页筛选、Finding 详情、分析信息和制品入口
- **AND** 历史扫描 SHALL 使用选中记录的上下文，不能修改当前报告输入

#### Scenario: 历史按可用时间排序

- **WHEN** 用户打开扫描历史
- **THEN** frontend SHALL 显式查询跨源码版本记录并按接口支持的 `startedAt desc` 分页
- **AND** SHALL NOT 请求接口不支持的 `createdAt` 排序或伪造尚未开始任务的时间

### Requirement: 知识库扫描结果展示

知识库扫描结果列表 SHALL 将严重等级统一展示为“风险”，并提供与依赖分析一致的迁移输入入口。

#### Scenario: 固定结果列

- **WHEN** 用户横向滚动知识库扫描结果表
- **THEN** 文件和风险列 SHALL 固定在左侧
- **AND** 行号列 SHALL 随表格横向滚动

#### Scenario: 纳入迁移输入

- **WHEN** 用户查看知识库扫描结果行
- **THEN** 系统 SHALL 在右侧固定操作列提供该结果的纳入报告或排除操作

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
