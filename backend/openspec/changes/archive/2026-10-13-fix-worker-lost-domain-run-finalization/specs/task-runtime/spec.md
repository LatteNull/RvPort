## ADDED Requirements

### Requirement: 任务执行写入必须校验当前尝试和终态
系统 SHALL 使用持久化执行尝试身份对状态迁移及业务发布实施原子校验。失联、取消、超时或其他最终终态之后，旧执行 MUST NOT 更新任务为成功或排队、发布当前业务结果或触发后续任务。

#### Scenario: 失联 Worker 迟到成功
- **WHEN** Task 已因 WORKER_LOST 失败，原 Worker 返回成功
- **THEN** 系统 SHALL 拒绝其 Task、领域结果、当前引用、迁移输入及归档候选发布，MUST NOT 发送 task.succeeded

#### Scenario: 迟到失败和日志
- **WHEN** 已失效执行尝试请求失败重试、进度更新或日志追加
- **THEN** 系统 MUST NOT 恢复 QUEUED、覆盖终态原因或改变已结束任务的最终日志游标

#### Scenario: 发布与失联并发
- **WHEN** 业务结果提交和失联收尾竞争同一 Task
- **THEN** 数据库 SHALL 串行化归属校验与写入，失联先提交则拒绝旧发布，已提交的终态领域结果 SHALL 保留，MUST NOT 以写入前单次查询替代原子保护

### Requirement: 执行隔离必须保留正常重试语义
系统 SHALL 区分尝试失败与 Task 最终失败，仅允许有效当前尝试按重试策略重新排队，下一尝试具有不同执行身份。

#### Scenario: 可重试异常未达到上限
- **WHEN** 当前 RUNNING 尝试发生可重试异常且未达到次数上限
- **THEN** 系统 SHALL 正常重新排队并允许下一尝试启动，MUST NOT 因本次尝试失败执行最终失联收尾，旧尝试 MUST NOT 写入下一尝试结果

#### Scenario: 已最终失败后重新执行
- **WHEN** 用户重新运行已失联失败的任务对应业务
- **THEN** 系统 SHALL 创建新的 Task 并保留旧任务终态，不复活旧执行身份

### Requirement: 领域终态一致性必须有独立测试与并发验证
实现 SHALL 为全部新增和受影响自有逻辑补充正常、异常、边界独立单测，mock 外部连接返回值，并在 Linux Docker 执行含未加载源码的整体及受影响模块覆盖率门禁，行及支持的分支 SHALL 至少 90%。

#### Scenario: 完整验收
- **WHEN** 提交本次实现验收
- **THEN** 验证 SHALL 包含各领域适配器、正常重试、重复清理、历史修复、事务回滚、迟到完成及并发竞争，并另行验证 API/Worker 分离部署的状态与 SSE 一致性

#### Scenario: 未达标
- **WHEN** 测试失败、覆盖率不足或必要链路未验证
- **THEN** 任务 SHALL 保持未完成，记录命令、统计范围、排除依据、报告和限制，MUST NOT 以 E2E 或编译成功替代单测
