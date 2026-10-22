## MODIFIED Requirements

### Requirement: 项目工作台加载与阶段导航

工作台 SHALL 通过 overview 获取项目、当前上下文、`workflow.stages` 和 `workflow.recommendedStageId`，并通过路径表示当前视图与阶段。

#### Scenario: 加载项目工作台

- **WHEN** 用户打开项目页
- **THEN** 页面 SHALL 显示局部加载状态，成功后展示项目摘要和流程，失败时提供重试
- **AND** 页面 SHALL 不额外读取旧的 `/workflow/status` 快照接口

#### Scenario: 打开阶段

- **WHEN** 用户点击有效阶段或访问 `/projects/:id/workflow/:stageId`
- **THEN** 页面 SHALL 按阶段 ID 懒加载阶段内容，并在 Workflow 视图以 Drawer 展示
- **AND** 单纯打开页面或阶段 SHALL 不自动启动扫描、报告、构建、测试或归档任务

## ADDED Requirements

### Requirement: Workflow 与 Step 双视图

工作台 SHALL 提供完整 Workflow 画布与顺序化 Step 操作视图，两者使用同一项目与阶段事实，不把缩小或展开的 Workflow 画布作为第三种页面。

#### Scenario: Workflow 查看全局

- **WHEN** 用户访问 `/projects/:id/workflow`
- **THEN** 页面 SHALL 展示完整、可平移缩放的十二阶段画布、拓扑连线、节点状态与项目上下文
- **AND** 点击节点 SHALL 在当前画布上打开该阶段 Drawer，不切换为左右画布布局
- **AND** 打开或关闭 Drawer SHALL 保持用户当前的画布平移与缩放，只更新节点选中态；首次加载或明确从 Step 切回 Workflow 时仍可定位阶段

#### Scenario: Workflow 节点视觉语义

- **WHEN** 用户查看 Workflow 或点击节点打开 Drawer
- **THEN** 节点 SHALL 独立表达业务状态、业务当前阶段和点击选中，且三种含义可同时存在
- **AND** 业务状态 SHALL 保留状态色竖条、图标与底色，当前阶段 SHALL 使用节点下方的小号灰字「当前阶段」且不加边框、底色或胶囊，节点标题 SHALL 保持统一字重，点击选中 SHALL 使用底部蓝色短线
- **AND** 查看其他阶段或关闭 Drawer SHALL 不改变业务当前阶段标记
- **AND** 当前阶段 SHALL 常驻现有 hover 放大及关联连线流动效果且保留业务状态色；减少动态效果时 SHALL 不放大、不流动

#### Scenario: Step 阶段工作区

- **WHEN** 用户切换到 Step 或访问 `/projects/:id/steps/:stageId`
- **THEN** 页面 SHALL 在左侧沿用分组式紧凑导航，按顺序列出十二阶段的名称、辅助说明、事实状态与当前选中态，在右侧展示所选阶段内容
- **AND** 左侧导航 SHALL 不复刻 Workflow 的拓扑与分支连线，右侧宽表格 SHALL 在内容内部滚动
- **AND** 等待或阻塞状态 SHALL 不禁止查看阶段

#### Scenario: Step 内切换阶段

- **WHEN** 用户在 Step 导航或阶段内容中选择另一个有效阶段
- **THEN** 页面 SHALL 留在 Step 并以内嵌 Panel 展示新阶段，复用与 Workflow Drawer 相同的阶段业务内容
- **AND** 浏览器后退 SHALL 能恢复先前的 Step 阶段

#### Scenario: Step 根视图操作

- **WHEN** 用户查看 Step 阶段根视图
- **THEN** 页面 SHALL 不显示阶段级手动刷新，且不为该操作增加工具栏或内容留白
- **AND** 内容中的列表刷新、环境检查等业务操作及内部详情页操作 SHALL 保留，Workflow Drawer 的刷新 SHALL 不变

#### Scenario: 视图切换保留阶段

- **WHEN** 用户从已打开阶段 Drawer 的 Workflow 切换到 Step
- **THEN** 页面 SHALL 在 Step 打开同一阶段；没有已打开阶段时 SHALL 使用有效的推荐阶段，缺失时回到项目基础配置
- **AND** 从 Step 返回 Workflow SHALL 保留画布并定位刚查看的阶段，不自动打开另一个 Drawer
- **AND** 连续返回同一阶段 SHALL 再次定位；取消未保存更改确认后 SHALL 不改变仍处于隐藏状态的画布定位

#### Scenario: 完整详情与主展示视口滚动

- **WHEN** 用户在 Workflow Drawer 或 Step 中查看日志、源码或分析详情
- **THEN** 页面 SHALL 完整保留必要的摘要、判断、建议及上下文信息，正文超过可见高度时允许正文滚动，页头与返回入口保持固定
- **AND** 主代码、日志及分析证据视口 SHALL 使用统一的独立高度 `clamp(720px, 80vh, 1200px)`，不被上方元信息挤压；视口内容溢出时在内部滚动
- **AND** 紧凑桌面上下排列时 SHALL 保留代码区的独立高度，不与问题列表平分剩余屏幕高度
- **AND** Step 阶段根视图与内部详情之间切换时 SHALL 将正文滚动到顶部，完整展示概要

#### Scenario: 阶段内部列表与详情往返

- **WHEN** 用户在同一阶段的列表设置筛选、页码、每页条数或排序后进入详情，再通过详情返回入口回到该列表
- **THEN** Workflow Drawer 与 Step SHALL 恢复该列表的查询控件状态，并使用这些条件重新请求数据
- **AND** 列表搜索框 SHALL 在阶段局部范围内按数据集保留尚未生效的输入草稿，失焦 SHALL NOT 提交查询；进入详情取消防抖计时，返回列表恢复草稿并继续正常防抖，Enter 和清空仍立即提交
- **AND** 清空全部筛选 SHALL 同时清除已应用查询条件和待生效搜索草稿、取消防抖并回到第一页，即使已应用搜索词原本为空；清空后的新输入 SHALL 仍可在详情往返恢复，不得重新应用清空前的旧草稿
- **AND** 未生效搜索草稿的失焦 SHALL NOT 因触发查询而替换或卸载详情入口；指针点击和键盘激活 SHALL 均能进入详情，无论查询缓存是否命中或后续请求快慢、成功或失败
- **AND** 最新查询结果的总数减少导致已保存页码越界时，列表 SHALL 校正到最后一个有效页码并重新请求，保留筛选、每页条数与排序；总数为零时 SHALL 回到第一页
- **AND** 不同记录数据集 SHALL 独立保存状态，返回同一数据集时恢复对应状态；不常驻隐藏列表或复用过期的行选择
- **AND** 报告模块、文件、问题和依赖自定义列表 SHALL 同样校正越界页码；从依赖详情返回 SHALL 恢复依赖清单实际展开状态，而不仅保存局部状态值
- **AND** 关闭阶段时 SHALL 清空局部表格状态，跨阶段、跨项目及切换 Workflow/Step 不保证保留；正文滚动仍遵守既定详情滚动规则

#### Scenario: URL 与历史

- **WHEN** 用户刷新、复制阶段地址或使用浏览器前进后退
- **THEN** 工作台 SHALL 从 `/workflow`、`/workflow/:stageId`、`/steps/:stageId` 路径恢复对应视图与阶段
- **AND** 不要求旧 `panel` 查询参数兼容

#### Scenario: 切换与未保存更改

- **WHEN** 用户在环境表单、项目描述、源码导入、扫描配置或构建/测试配置有未保存更改时切换视图、阶段或离开工作台
- **THEN** 页面 SHALL 在导航前提供继续编辑或放弃更改的选择；继续编辑时 SHALL 留在原阶段并保留输入
- **AND** 已保存的服务端数据 SHALL 继续由查询缓存复用，但滚动、筛选、局部弹窗等临时 UI 状态不保证跨视图保留
- **AND** 项目描述、源码导入与扫描配置 SHALL 在提交期间暂停编辑与局部返回/取消；失败后 SHALL 保留原输入供重试
- **AND** 允许提交期间继续编辑的执行配置，成功提交 SHALL 只清除当次提交内容的脏状态，后续输入 SHALL 仍受离开保护
- **AND** 用户重新打开扫描配置时 SHALL 开始新的编辑会话，不能以此前提交过的相同配置判定新输入已保存

#### Scenario: 项目任务更新

- **WHEN** 用户切换视图或 overview 与任务状态刷新
- **THEN** 项目级任务事件订阅 SHALL 不因展示载体切换而重建，阶段事实状态 SHALL 同步更新

#### Scenario: 桌面端宽度

- **WHEN** 视口位于 1024–1199px、1200–1599px、1600–1919px 或 1920px 以上
- **THEN** 页面 SHALL 分别使用紧凑、标准、宽屏或最大 1920px 的桌面布局，Step 右侧内容 SHALL 占用剩余宽度
- **AND** 低于 1024px SHALL 保留 1024px 桌面最小宽度，不切换移动端布局
