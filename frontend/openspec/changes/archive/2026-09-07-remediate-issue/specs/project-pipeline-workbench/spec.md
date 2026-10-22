## ADDED Requirements

### Requirement: 阶段执行必须以 readiness 为唯一门禁

具有执行前置条件的 Stage Drawer SHALL 请求 `GET /api/projects/{projectId}/readiness?stageId={stageId}`，并 SHALL 只根据返回的 `prerequisites[]` 判断当前操作能否执行。

#### Scenario: 判断执行条件

- **WHEN** Drawer 收到 readiness 响应
- **THEN** 仅当该操作要求的 prerequisite 均为 `SATISFIED` 时 SHALL 允许提交
- **AND** `key` SHALL 决定条件身份、中文名称和恢复入口
- **AND** `status` SHALL 决定中文状态和执行门禁
- **AND** `details` MAY 补充数量或关联事实
- **AND** `reasonCode` SHALL NOT 决定展示标题或恢复入口

#### Scenario: 多个条件未满足

- **WHEN** readiness 同时返回多个非 `SATISFIED` prerequisite
- **THEN** 页面 SHALL 展示全部未满足条件
- **AND** 每个可恢复条件 SHALL 在自身条目中提供对应入口

#### Scenario: readiness 请求失败

- **WHEN** readiness 无法读取
- **THEN** 页面 SHALL 展示事实读取失败及重新加载操作
- **AND** 页面 SHALL NOT 将请求失败解释为某项业务条件缺失

### Requirement: 阶段当前事实必须来自领域 latest

知识库扫描、依赖分析、评估报告、自动化测试、优化闭环和归档 SHALL 使用各自领域 latest 判断当前 Context 的执行事实，不得使用 List 第一条推算当前结果。

#### Scenario: latest 返回当前结果

- **WHEN** latest 返回 `freshness=CURRENT`
- **THEN** 页面 SHALL 使用 `execution` 展示本次运行状态，并在成功时展示 `result`
- **AND** 最新失败、取消、超时、排队中或运行中记录 SHALL NOT 回退到较早成功记录

#### Scenario: latest 返回旧 Context 结果

- **WHEN** latest 返回 `freshness=STALE`
- **THEN** 页面 SHALL 明确该结果不属于当前 Context
- **AND** 页面 SHALL NOT 将其作为当前成功事实或执行门禁
- **AND** 用户 MAY 从历史入口查看旧记录

#### Scenario: 当前 Context 无结果

- **WHEN** latest 返回 `freshness=EMPTY` 且 readiness 已满足
- **THEN** 页面 SHALL 展示首次执行就绪状态和唯一主操作
- **AND** 页面 SHALL NOT 使用普通无数据空态弱化可执行事实

### Requirement: 历史 List 不得选择当前事实

分页 List SHALL 仅用于历史浏览或记录型主视图，不得替代领域 latest 选择当前 Context 的最新事实。

#### Scenario: 进入历史视图

- **WHEN** 用户打开历史列表或历史详情
- **THEN** frontend SHALL 停用不可见的 current readiness 与 latest observer
- **AND** 历史详情 SHALL 保持只读
- **AND** 历史记录 SHALL NOT 改变当前执行门禁、当前批次或当前结果

#### Scenario: 关闭 Drawer

- **WHEN** 用户开始关闭 Drawer
- **THEN** frontend SHALL 立即停用 current 查询
- **AND** frontend SHALL 在关闭动画完成后重置详情、筛选和内部视图
- **AND** 关闭过程 SHALL NOT 因状态重置重新发起 latest 请求

### Requirement: x86 构建必须以记录表作为主视图

x86 构建 SHALL 展示当前 readiness Context 下的 `SOURCE_ONLY` 分页记录，并使用 `SOURCE_ONLY latest` 标记当前记录和初始化最近一次构建命令。

#### Scenario: 打开 x86 构建

- **WHEN** x86 构建 Drawer 打开
- **THEN** 页面 SHALL 并行读取 `x86-build` readiness、分页构建记录和 `SOURCE_ONLY latest`
- **AND** latest `result.id` 对应的表格行 SHALL 标记“当前”
- **AND** latest 为 `CURRENT` 时 SHALL 优先使用最近一次 `command` 初始化配置
- **AND** 当前 Context 无构建记录时 SHALL 使用默认命令
- **AND** 异步 latest 刷新 SHALL NOT 覆盖用户已经编辑的命令

#### Scenario: 筛选构建记录

- **WHEN** 用户选择任务状态
- **THEN** List 请求 SHALL 附加 `status` 并将其纳入 Query Key
- **AND** 清除筛选 SHALL 仍保持当前源码、当前源环境和 `SOURCE_ONLY` 范围
- **AND** 状态、创建时间、日志和取消操作 SHALL 保持独立列

### Requirement: 构建验证必须与 x86 构建统一记录结构

构建验证 SHALL 直接展示 `BOTH` 分页记录，并使用 `VALIDATION latest` 标记当前记录，不增加“当前结果到历史记录”的二级导航。

#### Scenario: 展示构建验证记录

- **WHEN** 构建验证 Drawer 打开
- **THEN** ID、状态、创建时间、操作、筛选、状态 Tag、当前标识和行密度 SHALL 与 x86 构建一致
- **AND** 构建验证 SHALL 额外展示环境列区分 x86 与 RISC-V
- **AND** 退出码 SHALL 只在日志详情中展示

### Requirement: 自动化测试必须以 latest 锚定当前批次

自动化测试 SHALL 使用 `test` readiness 的 `BUILD_VALIDATION` prerequisite 作为唯一门禁，并使用 `automated-tests/latest` 的 `CURRENT` 结果确定当前批次。

#### Scenario: latest 仅返回批次单侧结果

- **WHEN** backend latest 只包含当前批次的一侧运行
- **THEN** frontend MAY 使用当前源码测试 List 补齐同一批次另一侧结果
- **AND** List SHALL NOT 据此选择其他当前批次或改变门禁

#### Scenario: 展示结果比较

- **WHEN** 当前或历史批次存在比较结果
- **THEN** 页面 SHALL 分层展示一致性状态、风险、摘要和处理建议
- **AND** 失败时 SHALL 提供按需日志入口，不得将 Agent 原始输出直接铺成业务摘要

### Requirement: 优化闭环必须回答本轮是否收敛

优化闭环 SHALL 使用 `optimize` readiness 和 `optimization-cycles/latest` 组织本轮结论、闭环进度、问题收敛、验证结果和待处理事项。

#### Scenario: 当前轮次存在

- **WHEN** optimization latest 为 `CURRENT`
- **THEN** 页面 SHALL 展示轮次、源码版本、结论原因、开始时间和历史入口
- **AND** 双端结果比较未通过、失败或无法判断时 SHALL NOT 提供进入归档的主操作
- **AND** Footer SHALL 只保留由本轮结论决定的一个主操作

### Requirement: 归档必须说明当前源码是否可交付

归档 SHALL 使用 `archive` readiness 的 `ARCHIVE_CANDIDATES` 作为唯一创建门禁，并使用 `archives/latest` 判断最近归档是否属于当前源码。

#### Scenario: 当前源码归档完成

- **WHEN** latest 为 `CURRENT`、归档成功且存在可下载产物
- **THEN** 页面 SHALL 展示交付结论、交付快照、完整性信息和交付清单
- **AND** Footer SHALL 以下载归档包作为唯一主操作

#### Scenario: 最近归档属于旧源码

- **WHEN** latest 为 `STALE`
- **THEN** 页面 SHALL 明确当前源码尚未归档
- **AND** 旧归档 MAY 下载，但创建当前归档仍 SHALL 由 `ARCHIVE_CANDIDATES` readiness 决定

### Requirement: 项目 SSE 必须按节点元数据刷新事实

frontend SHALL 将项目 SSE 作为变化通知，并按 `stageId` 与 `resource.type/mode/environmentRole` 失效对应 overview、readiness、latest 和 List。

#### Scenario: 接收任务生命周期事件

- **WHEN** frontend 收到带节点和资源元数据的任务事件
- **THEN** frontend SHALL 按节点和资源路由领域 Query Key
- **AND** frontend SHALL NOT 仅依赖 `taskType` 猜测节点
- **AND** terminal 事件 SHALL 展示一次全局通知
- **AND** `task.log` SHALL 只推进游标，不刷新业务查询

#### Scenario: 接收 Context 变化

- **WHEN** frontend 收到 `project.context.changed`
- **THEN** frontend SHALL 使用 `changedFields` 和 `resource.type` 区分源码与运行环境变化
- **AND** frontend SHALL 刷新 overview 及受影响的下游 readiness、latest 和 List
- **AND** 未识别字段 SHALL 使用保守的完整 Context 刷新

#### Scenario: 合并 overview 刷新

- **WHEN** 同一项目连续收到事件
- **THEN** `project.context.changed` SHALL 在 250ms 固定窗口合并
- **AND** `task.created/queued/started` SHALL 在 5 秒固定窗口合并
- **AND** `task.progress` SHALL 最多每 10 秒刷新一次
- **AND** `task.succeeded/failed/cancelled/timeout` SHALL 取消被覆盖的延迟刷新并立即读取

#### Scenario: 刷新领域查询

- **WHEN** 同一领域连续收到非终态事件
- **THEN** 对应 Query Key SHALL 在 250ms 短窗口内只失效一次
- **AND** terminal SHALL 取消待执行刷新并立即读取最终事实
- **AND** SSE 正常期间 SHALL NOT 为同一 latest 配置固定轮询

### Requirement: 异步 mutation 与 SSE 必须只有一个主要刷新所有者

创建、取消或启动异步任务成功 SHALL 只反馈请求已提交，运行态与终态的领域刷新 SHALL 由 SSE 负责。

#### Scenario: 创建或取消任务成功

- **WHEN** mutation 成功返回
- **THEN** frontend SHALL NOT 立即失效同一领域 latest 或 List
- **AND** 后续 lifecycle SSE SHALL 推进运行态和最终态
- **AND** 用户手动刷新 SHALL 继续立即读取当前可见事实

#### Scenario: 依赖自动修复

- **WHEN** 自动修复任务生命周期变化
- **THEN** `dependency_auto_fix_run` SHALL NOT 覆盖 dependency analysis latest
- **AND** 重新分析产生的 `dependency_analysis_run` SHALL 负责刷新分析 latest 与 List

### Requirement: Stage Drawer 必须按 stage ID 稳定挂载

Stage Drawer 的组件身份 SHALL 只由 stage ID 决定，不得因任务、readiness 或 Workflow 展示状态变化替换领域组件。

#### Scenario: Drawer 打开期间状态变化

- **WHEN** 当前阶段事实从等待变为运行或终态
- **THEN** Drawer SHALL 保留表单输入、滚动位置和当前子视图
- **AND** 页面 SHALL NOT 关闭后重新打开 Drawer
