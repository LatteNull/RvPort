## ADDED Requirements

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
