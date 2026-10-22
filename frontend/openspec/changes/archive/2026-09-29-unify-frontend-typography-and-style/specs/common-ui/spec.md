## ADDED Requirements

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
