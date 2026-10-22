## ADDED Requirements

### Requirement: 主内容可被键盘快速定位

应用 SHALL 在每个包含主内容的共享 layout 中提供跳过导航链接和唯一的 `main` 地标。跳过链接在普通视觉状态下可以隐藏，但在键盘焦点可见时必须可见，且跳转后焦点目标不得被固定 Header 遮挡。

#### Scenario: 键盘用户跳过站点框架

- **WHEN** 用户在页面起始位置通过 Tab 获得跳过链接焦点并激活该链接
- **THEN** 焦点移动到当前路由页面的主内容起点
- **AND** 用户无需遍历 Header 或管理 Tab 才能访问主内容

### Requirement: 主要导航卡片使用原生导航语义

当项目卡片用于打开项目详情时，前端 SHALL 使用 Link 或等价原生导航语义，而不是用带 `onClick` 的非交互容器模拟导航。

#### Scenario: 使用键盘或浏览器原生链接操作打开项目

- **WHEN** 用户聚焦项目卡片并按 Enter，或使用 Cmd/Ctrl 点击、中键点击该卡片
- **THEN** 浏览器按链接语义打开项目详情
- **AND** 卡片的视觉 hover 与 focus-visible 反馈保持可见

### Requirement: 共享浮层和动效不会破坏用户控制

共享 Modal 与 Drawer 的可滚动正文 SHALL 阻止 overscroll 传递到页面背景。循环工作流动效 SHALL 在用户请求减少动态效果时停止，并保留非动态的状态辨识。

#### Scenario: 用户启用减少动态效果

- **WHEN** 系统媒体查询 `prefers-reduced-motion` 为 `reduce`
- **THEN** 工作流边线不得播放无限循环动画
- **AND** 当前激活或悬浮关联关系仍可通过静态样式辨识

### Requirement: 共享生成的输入控件具有可访问语义

共享筛选表单和脱离 `Form.Item` 的编辑输入 SHALL 具有可访问名称和稳定标识；原生输入 SHALL 提供 HTML `name`，复合控件 SHALL 提供稳定 `id`，并按用途配置 autocomplete。仅在用户明确进入编辑时 MAY 进行受控聚焦，且不得使用无条件 `autoFocus` 抢占焦点。

#### Scenario: 使用辅助技术访问筛选和目录编辑输入

- **WHEN** 用户聚焦任一共享筛选控件或构建配置输入
- **THEN** 辅助技术能读取该控件的用途
- **AND** 浏览器可从 `name` 与 autocomplete 获得正确的输入语义
