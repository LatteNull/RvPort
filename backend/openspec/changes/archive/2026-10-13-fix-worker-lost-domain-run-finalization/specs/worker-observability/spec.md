## ADDED Requirements

### Requirement: Worker 失联收尾必须同步关联领域记录
系统 SHALL 在确认当前执行 Worker 失联时，同一数据库事务内结束 Task 和关联的非终态领域运行记录，并保留错误码 WORKER_LOST、安全原因和结束时间。系统 MUST NOT 依赖失联 Worker 的 handler 回调。

#### Scenario: 依赖分析运行中失联
- **WHEN** 当前执行句柄所属 Worker 确认失联且 Task 为 RUNNING
- **THEN** Task 和关联的非终态依赖分析记录 SHALL 变为 FAILED，overview 与 latest 的活动状态 SHALL 收敛，失败原因 SHALL 表明执行结果未知

#### Scenario: 其他任务和多运行记录
- **WHEN** 失联 Task 关联分析、构建、测试、报告或其他领域运行记录
- **THEN** 注册适配器 SHALL 按 taskId 收尾所有关联非终态记录，MUST NOT 更新其他 Task 的运行记录或覆盖已有终态

#### Scenario: 并发清理或领域写入失败
- **WHEN** 多个清理器处理同一 Task，或领域更新抛出数据库异常
- **THEN** 系统 SHALL 保证成功迁移仅发生一次，异常事务整体回滚并可重试，MUST NOT 提交一半状态或重复终态事件

#### Scenario: 心跳恢复或已失去执行归属
- **WHEN** 清理提交前 Worker 已恢复有效心跳，或候选句柄不属于 Task 当前执行尝试
- **THEN** 清理 SHALL 跳过不适用的 Task 终态迁移，MUST NOT 结束其他有效执行

### Requirement: 历史非终态领域记录必须能够幂等收敛
系统 SHALL 提供独立于 Worker 注册记录是否存在的有界周期对账，修复 FAILED、CANCELLED 或 TIMEOUT Task 关联的非终态领域记录，使用原终态原因及可用结束时间，保留历史结果。

#### Scenario: Worker 已经被删除
- **WHEN** Worker 不存在或所有句柄已为终态，但 Task 失败且领域记录仍运行中
- **THEN** 对账 SHALL 找到并修复该记录，不依赖重新触发失联判定

#### Scenario: 重复执行和已成功结果
- **WHEN** 对账重复执行，或关联领域记录已经成功或部分成功
- **THEN** 系统 MUST NOT 改写终态结果、删除制品、重复追加 task.failed 或将成功 Task 的非终态结果伪造成成功

#### Scenario: 分批失败和禁用
- **WHEN** 候选超过批量限制、单项修复失败或 cleanup 被禁用
- **THEN** 系统 SHALL 分批处理并隔离单项失败、记录审计计数，禁用时 MUST NOT 自动修改记录

#### Scenario: 修复后的查询和通知
- **WHEN** 非终态领域记录修复提交成功
- **THEN** 系统 SHALL 发布既有节点变化通知，使 latest、overview 和 readiness 使用修复后的事实；通知失败 MUST NOT 改回数据库状态
