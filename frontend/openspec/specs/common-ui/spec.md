## Purpose

定义共享 Modal、Drawer、受控防抖搜索和 Monaco 工作区的交互边界，使业务视图使用一致的标题、内容槽位、搜索提交和编辑器边界行为，同时保持领域请求独立。

## Requirements

### Requirement: 通用 Drawer 封装

前端 SHALL 提供通用 `BaseDrawer` 组件，对 Ant Design Drawer 进行轻量二次封装，并与现有 `BaseModal` 保持一致的基础使用方式。

#### Scenario: BaseDrawer 使用 visible 控制显隐

- **WHEN** 业务组件向 `BaseDrawer` 传入 `visible`
- **THEN** `BaseDrawer` SHALL 将该值映射到 Ant Design Drawer 的 `open`

#### Scenario: BaseDrawer 渲染基础内容槽位

- **WHEN** 业务组件传入 `title`、`children` 和 `footer`
- **THEN** `BaseDrawer` SHALL 将它们分别渲染为 Drawer 标题区、主体区和底部区

#### Scenario: BaseDrawer 渲染标题对象

- **WHEN** 业务组件向 `BaseDrawer` 传入 `title={{ title, subTitle }}`
- **THEN** `BaseDrawer` SHALL 使用统一标题样式渲染主标题和副标题

#### Scenario: BaseModal 渲染标题对象

- **WHEN** 业务组件向 `BaseModal` 传入 `title={{ title, subTitle }}`
- **THEN** `BaseModal` SHALL 使用统一标题样式渲染主标题和副标题
- **AND** `BaseModal` SHALL continue to accept the existing ReactNode `title` usage

#### Scenario: BaseDrawer 默认右侧弹出

- **WHEN** 业务组件未显式传入 `placement`
- **THEN** `BaseDrawer` SHALL 默认从右侧弹出

#### Scenario: BaseDrawer 使用白色主体容器

- **WHEN** `BaseDrawer` 渲染
- **THEN** Drawer 主体 SHALL 使用白色背景、相对定位和占满抽屉区域的基础容器样式

#### Scenario: BaseDrawer 主体区域可滚动

- **WHEN** Drawer 主体内容超过可见高度
- **THEN** `BaseDrawer` SHALL 保持 header 和 footer 分区稳定，并使 body 区域可滚动

#### Scenario: BaseDrawer 合并样式覆盖

- **WHEN** 业务组件传入 Ant Design Drawer `styles`
- **THEN** `BaseDrawer` SHALL 将业务 styles 与默认 styles 合并
- **AND** 业务 styles SHALL 能覆盖默认 slot 样式

#### Scenario: BaseDrawer 透传 Ant Design Drawer 能力

- **WHEN** 业务组件传入其他 Ant Design Drawer props
- **THEN** `BaseDrawer` SHALL 将这些 props 透传给底层 Drawer，除非该 prop 已被 BaseDrawer 明确接管

#### Scenario: BaseDrawer 不内置业务操作

- **WHEN** `BaseDrawer` 渲染 footer
- **THEN** `BaseDrawer` SHALL NOT 内置保存、取消、确认或其他业务按钮文案

### Requirement: 远程列表搜索交互统一

使用共享 DebouncedSearchInput 的远程结果列表 SHALL 采用一致的轻量防抖交互；首页项目列表使用显式提交搜索，按 project-list-home 定义。

#### Scenario: 输入关键词筛选远程列表

- **WHEN** 用户在远程列表搜索框连续输入关键词
- **THEN** 搜索框 SHALL 使用前置搜索图标且不展示主色提交按钮
- **AND** 系统 SHALL 在用户停止输入后的统一防抖间隔提交最新关键词
- **AND** 新查询 SHALL 回到第一页并保留上一批结果直至新结果返回

#### Scenario: 立即提交搜索

- **WHEN** 用户在远程列表搜索框按下 Enter
- **THEN** 系统 SHALL 取消当前等待中的防抖并立即提交已去除首尾空白的关键词

#### Scenario: 清空搜索

- **WHEN** 用户清空远程列表搜索框
- **THEN** 系统 SHALL 立即移除关键词筛选并回到第一页

#### Scenario: 多个远程列表使用搜索

- **WHEN** 知识库扫描结果、评估报告模块列表或其他服务端分页列表提供关键词搜索
- **THEN** 相同搜索状态 SHALL 使用一致的输入外观、清空能力、键盘行为和请求触发规则

### Requirement: Monaco 工作区边界一致

前端 SHALL 为 Monaco 独立视图和带标题栏的组合工作区提供一致的边框、圆角与内部分隔。

#### Scenario: 独立展示 Monaco

- **WHEN** Monaco 不属于带标题栏的组合工作区
- **THEN** 共享组件 SHALL 提供 `1px` 次级边框和 `12px` 圆角

#### Scenario: 将 Monaco 嵌入组合工作区

- **WHEN** 标题栏、列表或 Tabs 与 Monaco 组成同一工作区
- **THEN** 外层工作区 SHALL 提供 `1px` 次级边框和 `12px` 圆角
- **AND** 内部 Monaco SHALL 移除自身边框与圆角，避免出现双重边框
- **AND** 标题栏与内容区 SHALL 使用单一分隔线区分

#### Scenario: 聚焦只读代码上下文

- **WHEN** 用户聚焦只读 Monaco 或移动代码光标
- **THEN** 缩进参考线 SHALL 保持普通颜色，不加深活动缩进
- **AND** 编辑器 SHALL 不绘制光标所在行的默认边框，并保留业务整行高亮与代码片段下划线

### Requirement: Shared business modal shell

前端 SHALL 提供可复用的业务弹窗外壳，用于承载与默认 Ant Design Modal 视觉不同的业务弹窗。

#### Scenario: Business modal renders

- **WHEN** 业务弹窗展示
- **THEN** 它 SHALL 使用 Ant Design Modal 行为，同时应用项目弹窗的 header、body spacing、footer actions、默认宽度、关闭入口和遮罩视觉约定

#### Scenario: Business modal width is overridden

- **WHEN** 功能向共享业务弹窗外壳传入 modal width
- **THEN** 外壳 SHALL 将该 width 透传给 Ant Design Modal，而不是强制使用单一全局宽度

#### Scenario: Business modal remains generic

- **WHEN** 功能使用共享业务弹窗外壳
- **THEN** 外壳 SHALL NOT 包含项目专属表单字段、API 调用或 query invalidation 逻辑

### Requirement: 统一前端字体与标题层级

前端 SHALL 通过现有 Ant Design 主题和官方 CSS 变量定义字体层级，并按 STYLE_GUIDE 复用页面、弹层、区域、正文和辅助信息的样式。

#### Scenario: 展示同级标题

- **WHEN** 页面、公共弹层或阶段内容展示标题
- **THEN** 同级标题 SHALL 使用一致的字号、字重和行高
- **AND** 内部次级标题 SHALL 保留必要的信息层级

#### Scenario: 公共容器接收不同标题形式

- **WHEN** BaseModal 或 BaseDrawer 接收字符串标题或标题对象
- **THEN** 主标题 SHALL 使用 18px / 500 / 24px 的统一规格
- **AND** StepPanel 详情标题 SHALL 使用同一规格

#### Scenario: 展示辅助信息

- **WHEN** 普通页面展示版本、状态、时间或结果元信息
- **THEN** 文字 SHALL 至少使用 12px
- **AND** 源码、密集路径、图标和随画布缩放的标记 MAY 遵循 STYLE_GUIDE 中的专用规格

#### Scenario: 排列同类内容

- **WHEN** 页面排列独立区块、区域内部内容、标题说明、列表或操作按钮
- **THEN** 同类内容关系 SHALL 使用 STYLE_GUIDE 规定的对应间距
- **AND** 执行记录条及紧凑列表卡片 SHALL 使用一致的内边距
- **AND** 编辑器、画布、紧凑元信息及真实分隔边界 MAY 保留用途所需的尺寸

### Requirement: 共享数据状态与交互反馈

前端 SHALL 为数据空态、筛选无结果、请求失败及无固定布局的加载提供共享 ContentState 展示，统一同类容器、按钮与焦点反馈。

#### Scenario: 显示数据状态

- **WHEN** 页面或共享列表显示上述数据状态
- **THEN** 它 SHALL 复用同一图形、文字与操作布局
- **AND** 它 SHALL 区分失败、加载和空结果语义，保留原调用方的重试和清空回调
- **AND** 阶段前置条件、执行状态、已知布局骨架和行内加载 SHALL 保留对应业务展示

#### Scenario: 显示容器

- **WHEN** 展示同类页面内容容器
- **THEN** 小型容器 SHALL 使用 8px 圆角，主要工作区 SHALL 使用 12px 圆角，并复用官方底色变量
- **AND** 静态内容卡片 SHALL 使用底色及必要边界建立层级

#### Scenario: 操作与减少动画

- **WHEN** 用户通过鼠标或键盘操作可点击内容
- **THEN** 主要操作、次要操作、hover 和可见键盘焦点 SHALL 遵循 STYLE_GUIDE
- **AND** 开启减少动画设置时，前端 SHALL 停止重复装饰动画并缩短交互过渡

### Requirement: 业务弹窗提交生命周期保护

具有提交操作的业务弹窗 SHALL 明确表达忙碌状态；忙碌期间所有用户关闭入口及输入修改 SHALL 遵循同一保护规则，异步成功仅影响所属编辑会话。共享弹窗 SHALL NOT 内置领域 API 或默认阻止非忙碌弹窗关闭。

#### Scenario: 提交期间尝试关闭或修改

- **WHEN** 用户在用户、模型、邮件、密码等业务弹窗中提交，动作仍在进行
- **THEN** 保存按钮 SHALL 显示进行中反馈，重复提交、输入修改、右上角关闭、ESC、蒙层和 footer 取消 SHALL 不结束或改变当前编辑会话

#### Scenario: 提交失败或结束

- **WHEN** 所属提交失败
- **THEN** 弹窗 SHALL 恢复编辑与关闭能力，保留已填写内容并提供失败反馈
- **WHEN** 所属提交成功
- **THEN** 弹窗 SHALL 执行既定成功行为，且迟到的旧会话结果 SHALL NOT 关闭或重置新会话

#### Scenario: 管理弹窗异步校验

- **WHEN** Worker 并发或重置用户密码开始异步表单校验
- **THEN** 提交 SHALL 在校验前加锁，并在校验后检查弹窗、目标及身份归属；校验失败 SHALL 恢复输入能力
- **AND** 重置密码目标改变时 SHALL 清空上一用户的密码草稿

### Requirement: 表格筛选单次通知

共享表格 SHALL 对一次有效的筛选操作只通知消费方一次，并维持正确的筛选、页码及清空行为，不因框架重复求值状态更新而执行额外业务回调。

#### Scenario: 普通筛选与连续修改

- **WHEN** 用户修改一次筛选值，或连续进行多次不同筛选操作
- **THEN** 每次有效操作 SHALL 仅产生一次外部筛选通知，最终条件 SHALL 包含正确的最新输入并回到第一页
- **AND** 开发期重复状态求值 SHALL 不增加通知次数

#### Scenario: 清空全部筛选

- **WHEN** 用户清空全部筛选
- **THEN** 表格 SHALL 仅通知一次清空后的条件，清理搜索草稿并回到第一页，保持既有搜索导航规则

### Requirement: 表格占位数据的资源边界

共享表格 SHALL 仅在同一领域资源 key 内保留翻页期间的旧行，不得在切换资源时继续展示可交互的上一资源记录。

#### Scenario: 翻页与切换资源

- **WHEN** 同一表格翻到下一页且请求尚未返回
- **THEN** 表格 MAY 保留该资源上一页的行数据
- **WHEN** 表格切换到另一资源 key
- **THEN** 表格 SHALL 清除上一资源的占位行并等待新资源的数据
