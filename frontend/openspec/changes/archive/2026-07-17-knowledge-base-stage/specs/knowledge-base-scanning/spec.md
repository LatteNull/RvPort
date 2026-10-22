## ADDED Requirements

### Requirement: 知识库扫描阶段 Drawer

系统 SHALL 在用户点击 Workflow 的 `kb` 节点后打开知识库扫描阶段 Drawer，并从服务端加载当前扫描任务状态、扫描概览和 Finding 结果。

#### Scenario: 打开已完成扫描结果

- **WHEN** 用户点击 `kb` 节点且当前扫描任务状态为 `SUCCEEDED`
- **THEN** 系统 SHALL 展示阻塞问题、迁移缺口和已兼容/已隔离三项概览
- **AND** 系统 SHALL 展示 Finding 结果表格

#### Scenario: 展示扫描任务状态

- **WHEN** 当前扫描任务状态为 `PENDING`、`RUNNING` 或 `FAILED`
- **THEN** 系统 SHALL 分别展示未开始、执行中或失败原因状态
- **AND** 系统 SHALL 不展示可加入迁移问题清单的结果操作

#### Scenario: 展示结果表格列

- **WHEN** 当前扫描任务已完成且存在 Finding
- **THEN** 结果表 SHALL 展示选择、文件、行号、规则 ID、风险、原因、建议和状态八列
- **AND** 表格 SHALL 支持横向滚动以保持原因和建议可读

### Requirement: 新建知识库扫描

系统 SHALL 在同一个知识库扫描 Drawer 内提供扫描配置视图，并允许用户创建全局扫描任务。

#### Scenario: 进入扫描配置

- **WHEN** 用户在扫描结果区点击新建扫描
- **THEN** 系统 SHALL 切换至知识库扫描配置视图
- **AND** 系统 SHALL 不在 Drawer 上打开 Modal

#### Scenario: 配置扫描参数

- **WHEN** 用户查看知识库扫描配置视图
- **THEN** 系统 SHALL 提供规则版本、扫描语言、扫描范围、排除目录名和精确排除路径字段
- **AND** 系统 SHALL 在排除目录名和精确排除路径字段旁展示各自的匹配规则说明

#### Scenario: 开始扫描

- **WHEN** 用户在配置视图提交有效配置
- **THEN** 系统 SHALL 创建知识库扫描任务并返回结果视图
- **AND** 系统 SHALL 根据服务端返回状态展示扫描执行中

#### Scenario: 取消扫描配置

- **WHEN** 用户在配置视图点击取消
- **THEN** 系统 SHALL 返回扫描结果视图
- **AND** 系统 SHALL 不创建扫描任务

### Requirement: Finding 选择与迁移问题清单加入

系统 SHALL 支持临时选择 Finding，并将已选 Finding 加入迁移问题清单。

#### Scenario: 选择或全选 Finding

- **WHEN** 用户选择单条 Finding 或操作全选、取消全选
- **THEN** 系统 SHALL 更新当前表格的已选择数量
- **AND** 全选 SHALL 仅作用于当前结果表

#### Scenario: 批量加入迁移问题清单

- **WHEN** 用户选择至少一条未加入 Finding 并确认加入迁移问题清单
- **THEN** 系统 SHALL 提交已选 Finding 并刷新其持久状态
- **AND** 系统 SHALL 将成功加入的 Finding 状态展示为已加入
- **AND** 系统 SHALL NOT 自动推进 `merge` 阶段

#### Scenario: 未选择 Finding 时加入

- **WHEN** 用户未选择任何 Finding 而尝试加入迁移问题清单
- **THEN** 系统 SHALL 阻止提交并提示用户先选择扫描结果

#### Scenario: 区分选择与加入状态

- **WHEN** 用户查看 Finding 结果
- **THEN** 选择列 SHALL 仅表示当前界面的临时勾选
- **AND** 状态列 SHALL 仅展示未加入或已加入

### Requirement: Finding 详情

系统 SHALL 允许用户在知识库扫描 Drawer 内查看单条 Finding 的代码上下文和规则说明。

#### Scenario: 打开 Finding 详情

- **WHEN** 用户点击 Finding 的文件名或规则 ID
- **THEN** 系统 SHALL 在同一个 Drawer 内切换至 Finding 详情视图
- **AND** 系统 SHALL 不增加额外的结果表操作列

#### Scenario: 展示 Finding 详情

- **WHEN** Finding 详情加载成功
- **THEN** 系统 SHALL 展示只读代码上下文、文件路径和行号、命中规则、规则版本、风险等级和来源上下文
- **AND** 系统 SHALL 展示风险原因、修改建议和后续动作

#### Scenario: 单项加入迁移问题清单

- **WHEN** 用户在未加入的 Finding 详情中确认加入迁移问题清单
- **THEN** 系统 SHALL 提交当前 Finding 并将其状态更新为已加入

#### Scenario: 返回扫描结果

- **WHEN** 用户在 Finding 详情中点击返回
- **THEN** 系统 SHALL 返回扫描结果视图
- **AND** 系统 SHALL 保留扫描结果视图的当前状态

### Requirement: 知识库扫描报告导出

系统 SHALL 为当前已完成的知识库扫描提供全局报告导出操作。

#### Scenario: 导出当前扫描报告

- **WHEN** 当前扫描任务已完成且用户点击 Drawer Footer 的导出报告
- **THEN** 系统 SHALL 发起当前扫描结果的报告导出请求
- **AND** 该操作 SHALL 不依赖表格行选择
