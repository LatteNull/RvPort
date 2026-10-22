## ADDED Requirements

### Requirement: 任务运行时必须支持两类专项分析任务
任务运行时 SHALL 支持 `FLOATING_POINT_ANALYSIS` 与 `MEMORY_ORDER_ANALYSIS`，并 SHALL 返回领域 resource、stageId、源码版本和运行记录关联。

#### Scenario: 创建浮点任务
- **WHEN** 浮点分析 API 创建任务
- **THEN** 任务 SHALL 使用 `stageId=floating-point-analysis`
- **AND** resource SHALL 指向浮点分析运行记录

#### Scenario: 创建内存序任务
- **WHEN** 内存序分析 API 创建任务
- **THEN** 任务 SHALL 使用 `stageId=memory-order-analysis`
- **AND** resource SHALL 指向内存序分析运行记录

### Requirement: 专项分析必须支持日志、取消和跨进程事件
Worker SHALL 通过现有任务日志、取消和项目事件机制运行两个工具，并 SHALL 在 API/Worker 分离部署时通过 Redis 向项目 SSE 广播生命周期变化。

#### Scenario: 运行中输出日志
- **WHEN** 工具向 stdout 或 stderr 输出进度和诊断
- **THEN** Worker SHALL 保存 merged/stdout/stderr 日志
- **AND** SHALL 发布 task.log 或日志可用通知

#### Scenario: 取消内存序分析
- **WHEN** 用户取消正在运行的内存序任务
- **THEN** Worker SHALL 写入 cancel file 并等待协作停止
- **AND** 超过宽限期后 SHALL 终止进程树并写入 CANCELLED

#### Scenario: 风险退出码不触发失败重试
- **WHEN** memory-order 返回协议定义的风险退出码 3
- **THEN** Worker SHALL 将任务标记成功
- **AND** RabbitMQ MUST NOT 重投该消息

### Requirement: 专项分析 latest 必须优先返回运行中任务
领域 latest 与项目 overview SHALL 在当前源码版本存在排队或运行中任务时返回该活动状态，而不是旧的成功或失败结果。

#### Scenario: 旧成功后启动重跑
- **WHEN** 当前源码版本已有成功运行并启动新的同类分析
- **THEN** latest SHALL 返回新运行的 QUEUED 或 RUNNING 状态
- **AND** 旧运行仍可通过历史列表查询
