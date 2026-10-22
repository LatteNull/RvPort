## ADDED Requirements

### Requirement: KB finding API 必须返回 schema v2 优先结构

KB finding 列表和详情 API MUST 以 schema v2 的领域结构作为主要返回合同，不再以 v1 扁平字段作为默认合同。

#### Scenario: 分页查询 finding 列表

- **WHEN** 前端分页查询某个项目的 KB finding 列表
- **THEN** 后端 MUST 返回可分页、可排序、可过滤的记录
- **AND** 每条记录 MUST 包含用于列表展示的标题、风险等级、类型、来源、位置摘要和报告纳入状态
- **AND** 每条记录 SHOULD 包含 v2 `fact` 和 `conclusion` 的摘要字段
- **AND** 后端 MUST NOT 要求前端依赖 v1 的 `reason`、`suggestion`、`trace` 扁平结构

#### Scenario: 查询 finding 详情

- **WHEN** 前端查询特定 KB finding 详情
- **THEN** 后端 MUST 返回完整 v2 finding payload
- **AND** 返回内容 MUST 包含 `fact`、`conclusion`、`occurrences` 和 `evidenceChain`
- **AND** 返回内容 MUST 包含当前人工确认状态、报告纳入状态和 AI 扩展建议

#### Scenario: 查询 finding 代码上下文

- **WHEN** 前端查询特定 finding 的代码上下文
- **THEN** 后端 MUST 使用 v2 primary location 或导入投影位置定位源码
- **AND** 后端 MUST 返回目标代码行上下各 20 行以内的上下文
- **AND** 返回内容 MUST 包含每行行号、代码文本和是否高亮
- **AND** 当源码文件不存在或路径越界时 MUST 返回明确错误

### Requirement: KB artifact 下载 API 必须支持 schema v2 结果

KB 扫描 artifact 下载 API MUST 能返回 schema v2 的 JSON 和 HTML 报告。

#### Scenario: 下载 schema v2 JSON

- **WHEN** 用户请求下载 KB 扫描 JSON artifact
- **THEN** 后端 MUST 返回 scanner 产生的 schema v2 `scan-result.json`
- **AND** Content-Type SHOULD 与 JSON 内容匹配

#### Scenario: 下载 schema v2 HTML

- **WHEN** 用户请求下载 KB 扫描 HTML artifact
- **THEN** 后端 MUST 返回 scanner 产生的 HTML 报告
- **AND** 下载内容 MUST 与当前任务 artifact 绑定
