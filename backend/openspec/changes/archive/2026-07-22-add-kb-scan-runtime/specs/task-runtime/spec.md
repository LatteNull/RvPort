## ADDED Requirements

### Requirement: 任务运行时必须支持 KB_SCAN 任务类型
任务运行时 SHALL 支持 `KB_SCAN` 长任务类型，并通过既有 worker handler 机制执行 KB 扫描。

#### Scenario: 创建 KB_SCAN 任务
- **WHEN** KB 扫描 API 请求创建扫描
- **THEN** 任务运行时 SHALL 创建任务类型为 `KB_SCAN` 的 `tasks` 记录
- **AND** 任务输入快照 SHALL 包含 project id、scan run id、source revision id、规则版本、语言、扫描范围、排除路径和目标架构摘要
- **AND** 任务输入快照 MUST NOT 包含源码工作副本路径、scanner 输出目录、完整 scanner 输入、明文凭据或服务器真实路径

#### Scenario: Worker 执行 KB_SCAN handler
- **WHEN** worker 认领 `KB_SCAN` 任务
- **THEN** worker SHALL 分发到 KB_SCAN handler
- **AND** handler SHALL 通过任务执行上下文读取输入、更新进度、写入日志、登记本地 scanner 进程并完成任务

#### Scenario: 缺少 KB_SCAN handler
- **WHEN** worker 认领 `KB_SCAN` 任务但未注册 handler
- **THEN** 任务 SHALL 按既有缺少 handler 规则失败
- **AND** 错误码 SHALL 表示任务 handler 不存在

### Requirement: KB_SCAN 必须通过 SSE 推送状态和日志
KB_SCAN 任务 SHALL 复用项目级 SSE 推送进度和终态事件，并 SHALL 复用任务级日志 SSE 展示 scanner 日志。

#### Scenario: 推送 KB 扫描进度
- **WHEN** KB_SCAN handler 完成输入校验、输出目录准备、scanner 执行、结果解析和 findings 入库阶段
- **THEN** handler SHALL 通过任务执行上下文写入进度事件
- **AND** 项目级 SSE SHALL 能向有权限用户推送这些事件

#### Scenario: 推送 KB 扫描日志
- **WHEN** KB Scanner 产生 stdout、stderr 或 scan.log 内容
- **THEN** 任务运行时 SHALL 写入任务日志事件
- **AND** 任务级日志 SSE SHALL 能补发历史日志并继续推送新增日志
- **AND** 日志事件 MUST NOT 包含服务器真实路径、源码工作副本路径、明文凭据或完整任务输入快照

#### Scenario: 推送 KB 扫描终态
- **WHEN** KB_SCAN 任务成功、失败、取消或超时
- **THEN** worker SHALL 写入对应终态事件
- **AND** 前端 SHALL 能通过项目级 SSE、任务详情或 KB 扫描详情获得最终状态

### Requirement: KB_SCAN 取消必须终止本地 scanner 进程
任务运行时 SHALL 允许取消正在运行的 KB_SCAN 任务，并 SHALL 通过已登记的 runtime handle 尝试终止本地 scanner 进程。

#### Scenario: 取消运行中 KB_SCAN
- **WHEN** 用户调用 `POST /api/tasks/{taskId}/cancel` 且任务类型为 `KB_SCAN`
- **THEN** 后端 SHALL 按既有运行中任务取消规则将任务状态更新为 `CANCELLED`
- **AND** 后端 SHALL 投递取消清理消息
- **AND** 取消处理 SHALL 根据 active runtime handle 尝试终止 scanner 本地进程
- **AND** 后端 SHALL 将关联 `kb_scan_runs` 标记为 `CANCELLED`

#### Scenario: 取消后不写成功结果
- **WHEN** KB_SCAN 在 scanner 执行或结果导入期间被取消
- **THEN** worker MUST NOT 将任务或 `kb_scan_runs` 标记为 `SUCCEEDED`
- **AND** worker MUST NOT 写入成功态 artifact 或误报完整 findings 导入成功
