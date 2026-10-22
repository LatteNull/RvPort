# project-stage-runtime Specification

## Purpose

定义各执行阶段共享的 readiness 门禁、领域 latest、历史查询、状态反馈及异步刷新边界。项目事件连接由 project-overview-current-context 定义。

## Requirements

### Requirement: 阶段执行必须以 readiness 为唯一门禁

具有执行前置条件的 Stage Drawer SHALL 请求 `GET /api/projects/{projectId}/readiness?stageId={stageId}`，并 SHALL 根据当前操作需要的 `prerequisites[]` 判断服务端前置条件；提交还需满足表单校验和可用请求参数要求。

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

### Requirement: 阶段前置条件必须复用一致结构

多个 Stage Drawer 展示执行前置条件时 SHALL 复用共享前置条件展示结构，组件 SHALL 只接收页面已经转换完成的状态、事实和操作，不得自行请求领域 API。

#### Scenario: 展示多个前置条件

- **WHEN** readiness 返回一个或多个 prerequisite
- **THEN** 页面 SHALL 为每个条件展示名称和中文状态
- **AND** 恢复操作 SHALL 归属对应条件，不得只展示一个无法解释其他阻断项的总操作
- **AND** 条件数量变化时布局 SHALL 自适应换行，不依赖固定分割线

#### Scenario: 前置条件满足

- **WHEN** 当前操作需要的 prerequisite 均为 `SATISFIED`
- **THEN** 共享结构 SHALL 使用成功语义展示可执行状态
- **AND** 页面 MAY 继续展示当前源码、环境或构建等领域事实

### Requirement: 阶段页面状态必须复用 StageStateNotice

知识库扫描、依赖分析、评估报告、优化闭环和归档 SHALL 使用纯展示组件 `StageStateNotice` 表达 prerequisite、ready、processing、execution-error 和 request-error 状态。

#### Scenario: 前置条件不满足

- **WHEN** 页面判断当前操作不可执行
- **THEN** `StageStateNotice` SHALL 使用 prerequisite 语义展示全部相关条件及恢复入口
- **AND** 页面 SHALL NOT 同时展示普通暂无结果状态或不可执行的主操作

#### Scenario: 首次执行就绪

- **WHEN** readiness 满足且 latest 为 `EMPTY`
- **THEN** `StageStateNotice` SHALL 使用 ready 语义展示已满足事实和首次执行主操作

#### Scenario: 正在执行

- **WHEN** latest execution 为 `PENDING`、`QUEUED` 或 `RUNNING`
- **THEN** `StageStateNotice` SHALL 使用 processing 语义展示进度、消息和可用查看操作

#### Scenario: 最近执行失败

- **WHEN** latest execution 为 `FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** `StageStateNotice` SHALL 使用 execution-error 语义保留失败状态、原因和时间
- **AND** 业务重试 SHALL 使用“重新执行”类文案，不得与接口“重新加载”混淆

#### Scenario: 查询失败

- **WHEN** readiness 或 latest 请求失败
- **THEN** `StageStateNotice` SHALL 使用 request-error 语义展示失败原因和重新加载操作
- **AND** 页面 SHALL NOT 将接口失败呈现为业务执行失败

### Requirement: 共享记录标题必须表达真实返回层级

具有当前结果、历史列表和历史详情的 Drawer SHALL 使用共享记录标题表达当前位置，并在关闭后回到默认当前视图。

#### Scenario: 从历史详情返回

- **WHEN** 用户从历史列表进入详情
- **THEN** 返回操作 SHALL 回到历史列表
- **AND** 从最新结果进入的详情 SHALL 返回最新结果
- **AND** 页面 SHALL NOT 跳过真实上一层或保留上一次打开的错误路径

### Requirement: 跨步骤展示必须遵循明确的状态组合规则

frontend SHALL 为全部项目步骤建立展示矩阵，并按独立展示、条件＋记录型、当前概览型明确适用规则。同类事实 SHALL 使用一致的状态语义、文案及操作层级；业务例外 SHALL 有明确依据。

#### Scenario: 全部步骤覆盖

- **WHEN** 核查步骤展示一致性
- **THEN** 矩阵 SHALL 覆盖实际注册的全部步骤及 Workflow/Step
- **AND** SHALL 记录事实来源、展示条件、操作、历史/日志入口和不适用项理由

#### Scenario: 当前受阻且存在旧终态结果

- **WHEN** 当前操作的前置条件未满足且存在此前成功或失败结果
- **THEN** 当前概览 SHALL 以单一前置条件主状态解释阻碍及恢复入口
- **AND** SHALL 保留历史入口，不叠加旧终态完整状态块或不可执行的主操作

#### Scenario: 当前受阻且已有任务运行

- **WHEN** 上游状态变化导致当前前置条件未满足且服务端仍返回正在执行的任务
- **THEN** 页面 SHALL 阻止新执行，同时以辅助信息保留任务运行事实和可用日志或记录入口
- **AND** SHALL NOT 推断任务已取消、失败或完成

#### Scenario: 当前阻碍不妨碍历史阅读

- **WHEN** 用户从受阻概览进入历史列表及详情
- **THEN** 页面 SHALL 根据历史查询展示记录，不受 current readiness 或 latest 失败阻断
- **AND** 返回 SHALL 回到真实上一层，历史详情 SHALL 保持只读

### Requirement: 相同前置条件与操作必须一致表达

各步骤 SHALL 使用 prerequisite 的 key 和 status 映射统一名称、中文状态及恢复目标，保留各操作所需条件的业务差异。

#### Scenario: x86 正在构建

- **WHEN** 四项分析收到 X86_BUILD 为 RUNNING
- **THEN** 各页面 SHALL 使用一致的 x86 正在构建提示、等待说明与前往构建入口
- **AND** SHALL NOT 将其笼统表达为未配置或执行失败

#### Scenario: 状态反馈与操作层级

- **WHEN** 展示就绪、执行中、业务失败或请求失败
- **THEN** 相同语义 SHALL 复用共享状态结构，且每个主状态最多提供一个主操作
- **AND** 重新执行 SHALL 与重新加载明确区分，日志和历史 SHALL 使用一致的次要操作层级

### Requirement: 节点事实与两种视图必须保持语义一致

Workflow 和 Step SHALL 共享业务展示条件。节点执行事实与当前操作门禁 SHALL 分别表达，不互相替代。

#### Scenario: 已完成节点的上游重新构建

- **WHEN** 节点仍为已完成而当前 readiness 受上游重建影响
- **THEN** frontend SHALL 保留真实节点事实，并在步骤内容中说明当前执行限制
- **AND** SHALL NOT 仅依据节点已完成状态允许重新执行

#### Scenario: 切换视图

- **WHEN** 相同项目和步骤在 Workflow 与 Step 中展示
- **THEN** 状态含义、条件、文案和操作可用性 SHALL 一致
- **AND** SHALL 保持既有 Drawer/面板和二级内容容器，不新增第三种页面层级

### Requirement: 默认视图按两套展示逻辑组织

frontend SHALL 将 x86 构建、构建验证、自动化测试展示为当前条件及执行配置加跨源码版本历史记录；依赖、知识库、两项专项分析、报告、优化、归档 SHALL 展示当前概览并保留固定历史入口。项目配置、环境、源码及人工修复 SHALL 保留独立展示。

#### Scenario: 条件与记录独立读取

- **WHEN** 条件加载、失败或未满足
- **THEN** 记录 SHALL 独立读取并保持可访问
- **AND** 历史查询 SHALL 显式退出接口默认当前上下文约束，按接口可用时间倒序分页并标识源码版本
- **AND** frontend SHALL NOT 新增源码版本筛选

#### Scenario: 条件加记录型已有活动任务

- **WHEN** x86 构建、构建验证或自动化测试已有运行任务
- **THEN** frontend SHALL 保留真实记录状态，并根据当前执行条件决定新建可用性
- **AND** SHALL NOT 仅因存在活动任务额外全局禁用新建
- **AND** 请求提交期间 SHALL 防止重复点击，失败 SHALL 保留配置

#### Scenario: 当前概览型已有活动任务

- **WHEN** 当前概览型返回 PENDING、QUEUED 或 RUNNING，包括可确认的旧版本活动任务
- **THEN** frontend SHALL NOT 提供再次执行入口
- **AND** SHALL 保留任务身份及可用详情或日志入口

#### Scenario: 当前条件满足且只有旧终态

- **WHEN** 当前概览型条件满足，但 latest 只有 STALE 终态或 EMPTY
- **THEN** frontend SHALL 展示当前版本就绪引导及已满足条件
- **AND** 旧结果 SHALL 从历史查看，不作为当前结果
- **AND** 优化周期 SHALL 保持被动聚合，仅提供业务导航而非执行按钮

#### Scenario: 后台刷新失败及提交同步

- **WHEN** 已有内容后台刷新失败
- **THEN** frontend SHALL 保留内容并轻量提示，门禁无法确认时暂停新执行
- **WHEN** 当前概览型提交已受理但执行身份尚未更新
- **THEN** frontend SHALL 显示已提交待同步，不闪回可执行空态

#### Scenario: 测试批次记录

- **WHEN** 打开自动化测试默认页
- **THEN** frontend SHALL 默认展示跨版本批次记录，并在批次内查看两侧测试及比较
- **AND** SHALL 在取得完整聚合数据后进行批次分页，不对半页原始测试行进行不完整批次分页
- **AND** 部分提交失败 SHALL 保留已创建侧，仅补交失败侧

#### Scenario: 历史入口与视觉层级

- **WHEN** 当前概览型处于加载、失败、受阻、就绪、运行或结果状态
- **THEN** 历史入口 SHALL 固定在标题操作区，Workflow 与 Step 均可访问
- **AND** 前置条件与错误说明 SHALL 完整换行，主状态最多一个主操作
- **AND** 成功内容 SHALL 保留各模块结果结构，不替换成通用成功卡片
