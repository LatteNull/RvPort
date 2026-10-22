# task-log-viewer Specification

## Purpose

定义构建、测试、测试比较及环境脚本共用的实时日志、终态分页、错误恢复、资源边界与阅读体验，确保任务执行期间输出连续可追踪，完成后能读取权威日志正文。

## Requirements

### Requirement: 运行中任务日志实时展示

项目流水线工作台 SHALL 对支持日志的运行中任务使用后端日志通知与增量读取接口实时展示输出，并以成功读取的日志事件游标作为恢复依据。

#### Scenario: 首次打开运行中日志

- **WHEN** 用户打开状态为 `PENDING`、`QUEUED` 或 `RUNNING` 的任务日志
- **THEN** 系统 SHALL 建立 `GET /api/tasks/{taskId}/log-notifications` 通知连接
- **AND** 系统 SHALL 立即从已成功消费的事件游标调用 `GET /api/tasks/{taskId}/log-increments`
- **AND** 系统 SHALL 将返回的 `merged`、`stdout` 和 `stderr` 按事件顺序追加至对应日志视图

#### Scenario: 连续消费多批增量

- **WHEN** 增量日志响应返回 `hasMore=true`
- **THEN** 系统 SHALL 使用本次成功响应的 `latestEventId` 继续读取
- **AND** 系统 SHALL 串行完成读取，避免同一游标产生并发重复请求

#### Scenario: 收到日志更新通知

- **WHEN** 通知连接收到 `task.log.updated`
- **THEN** 系统 SHALL 拉取尚未成功消费的增量日志
- **AND** 系统 SHALL NOT 仅因收到通知而推进本地消费游标

#### Scenario: 切换运行日志类型

- **WHEN** 用户在运行中日志的合并输出、标准输出和标准错误之间切换
- **THEN** 系统 SHALL 使用同一批增量响应在本地维护的对应内容
- **AND** 系统 SHALL NOT 因切换类型重新建立通知连接或重复读取已消费事件

### Requirement: 实时日志连接恢复

项目流水线工作台 SHALL 在日志通知连接或增量请求异常时保留已成功展示的内容，并提供自动恢复和用户可见的重试路径。

#### Scenario: 通知连接中断

- **WHEN** 运行中日志通知连接异常关闭
- **THEN** 系统 SHALL 保留当前日志内容和最后成功消费的事件游标
- **AND** 系统 SHALL 以退避策略携带该游标重新建立连接
- **AND** 重连建立后 SHALL 主动读取一次增量日志

#### Scenario: 增量读取失败

- **WHEN** 增量日志请求失败
- **THEN** 系统 SHALL NOT 推进消费游标或清空已展示内容
- **AND** 系统 SHALL 展示可恢复的错误状态并自动重试
- **AND** 用户 SHALL 能够主动重新读取

#### Scenario: 页面重新可见

- **WHEN** 用户返回此前隐藏的运行日志页面
- **THEN** 系统 SHALL 从最后成功消费的事件游标主动检查增量日志

### Requirement: 运行日志终态收尾

项目流水线工作台 SHALL 在任务进入终态时完整消费最终增量，并切换至完成态权威日志读取方式。

#### Scenario: 收到任务完成通知

- **WHEN** 通知连接收到 `task.log.completed`
- **THEN** 系统 SHALL 继续读取增量日志，直至本地消费游标达到通知中的 `latestEventId` 且响应不再包含后续批次
- **AND** 系统 SHALL 在收尾完成后关闭通知连接
- **AND** 系统 SHALL 刷新任务及对应业务结果状态

#### Scenario: 切换完成态日志

- **WHEN** 最终增量读取完成且任务状态为 `SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 系统 SHALL 使用 `GET /api/tasks/{taskId}/log-content` 重新获取权威完成态日志
- **AND** 系统 SHALL 以完成态内容替换实时缓存而非重复拼接
- **AND** 系统 SHALL 支持从日志末尾向上加载更早内容及受控下载

#### Scenario: 直接打开已完成任务

- **WHEN** 用户直接打开终态任务的日志
- **THEN** 系统 SHALL 直接读取完成态 `log-content`
- **AND** 系统 SHALL NOT 建立不必要的日志通知连接

### Requirement: 实时日志展示资源边界

项目流水线工作台 SHALL 限制浏览器中持续追加的实时日志规模，同时保持最终完整日志可追溯。

#### Scenario: 实时日志超过展示上限

- **WHEN** 某一运行日志视图累计内容超过前端展示上限
- **THEN** 系统 SHALL 移除最早的已展示内容并继续推进成功消费游标
- **AND** 系统 SHALL 明确提示用户部分较早实时日志已省略
- **AND** 系统 SHALL 在任务完成后允许用户通过完成态历史分页查看更早日志

#### Scenario: 离开日志视图

- **WHEN** 用户关闭日志视图或切换至另一任务
- **THEN** 系统 SHALL 关闭原任务通知连接并取消其重连与重试调度
- **AND** 系统 SHALL NOT 将日志正文或事件游标持久化至浏览器存储

### Requirement: 任务日志体验统一

普通构建、x86 构建、自动化测试、测试结果对比和环境脚本执行记录 SHALL 使用一致的运行态增量、终态历史、日志类型切换和错误恢复语义。

#### Scenario: 不同任务类型查看日志

- **WHEN** 用户在任一受支持任务类型中打开日志
- **THEN** 系统 SHALL 根据任务状态选择运行态或完成态读取策略
- **AND** 相同日志状态 SHALL 提供一致的加载、空数据、错误、重试和连接反馈

### Requirement: 完成态日志保持时间正序

前端 SHALL 保留接口返回的页内行序，将更早分页拼接在最新分页之前。

#### Scenario: 首次加载最新页

- **WHEN** 接口返回最新页的正序日志
- **THEN** 展示顺序与接口正文一致

#### Scenario: 加载更早日志

- **WHEN** 最新页之后加载更早分页
- **THEN** 更早分页在前且各页内部行序不变

### Requirement: 日志阅读与任务摘要

任务日志 SHALL 通过共享 Monaco 日志视图展示，提供合并输出、标准输出和标准错误切换，并保持任务摘要与正文分离。

#### Scenario: 打开完成态日志

- **WHEN** 用户首次打开完成态日志
- **THEN** 页面 SHALL 请求 `offset=0`、`lines=100`，按时间正序展示并定位底部
- **AND** 向上加载更早页 SHALL 在当前内容之前拼接，保留页内行序和阅读位置

#### Scenario: 查看任务上下文

- **WHEN** 用户从构建或测试记录进入日志
- **THEN** 页面 SHALL 展示记录 ID、状态、退出码、执行时间和工作目录，并提供刷新和返回记录入口
- **AND** 有日志资源时 SHALL 提供下载，编辑器 SHALL 使用剩余可用高度内部滚动

### Requirement: 日志异步会话隔离

实时日志 SHALL 将异步读取、消费游标、通知、重试及完成反馈限制在其所属阅读会话；任务切换、停用或重新开启后，旧会话 SHALL NOT 修改新会话。现有增量串行读取、连接恢复和终态收尾规则 SHALL 保持有效。

#### Scenario: 切换任务后旧读取返回

- **WHEN** 任务 A 的增量请求未结束，用户切换至任务 B，随后 A 的响应返回
- **THEN** 系统 SHALL 忽略 A 对 B 的正文、游标、读取状态、错误与完成反馈的影响
- **AND** B 的下一次读取 SHALL 从 B 最后成功消费的游标继续，不能使用 A 的游标

#### Scenario: 同一任务停止并重开日志

- **WHEN** 日志阅读会话停止并重新开启，旧会话仍有请求、重试或完成通知未结束
- **THEN** 旧会话 SHALL NOT 覆盖新会话状态、释放其读取锁或执行其完成回调
- **AND** 关闭后的旧通知、重连和重试 SHALL 不继续消费日志
