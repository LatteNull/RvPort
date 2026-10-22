## Context

本 change 是基于 Vercel Web Interface Guidelines 的静态审查整改。已确认的主要问题包括：

- `ProjectCard` 使用 `article` 的点击事件与 `tabIndex` 承担导航，缺少与语义对应的键盘行为。
- 主布局未提供跳过链接与 `main` 地标；`MainLayout` 的 Logo 没有明确宽高。
- `BaseModal` 和 `BaseDrawer` 的滚动正文未隔离 overscroll；工作流悬浮边线动效没有减少动态效果分支。
- 构建配置输入需要显式关联标签、稳定标识和 autocomplete；通用筛选器也必须保证生成的控件都有可访问名称和稳定标识。

## Goals / Non-Goals

**Goals:**

- 为共享 UI 建立可复用、可测试的可访问性与交互基线。
- 维持当前视觉设计、Ant Design 技术栈和业务流程。
- 使修复点可通过组件测试和静态检查长期防回归。

**Non-Goals:**

- 不重构全部页面文案、日期格式或表格虚拟化策略。
- 不引入新 UI、无障碍或动效依赖。
- 不修改没有本次审查证据支持的业务交互。

## Decisions

### 项目卡片使用实际语义元素

项目卡片是前往项目详情的导航入口，应使用 `<Link>`（或保持按钮语义并显式处理 Enter/Space）。优先选用 `<Link>`，保留浏览器的键盘、Cmd/Ctrl 点击和中键打开行为；卡片现有 hover/focus-visible 样式继续附着于该元素。

### 共享布局提供一个稳定的主内容目标

在每个应用 layout 中放置指向 `#main-content` 的跳过链接，并用 `<main id="main-content">` 包裹 `Outlet`。跳过链接默认视觉隐藏，仅在 `:focus-visible` 时显示；固定 Header 不得遮挡其焦点或目标内容。

### 输入语义由组件边界保证

`FilterForm` 扩展字段契约，使每个生成的控件都有可访问名称和稳定标识；原生输入提供 HTML `name`，Ant Design 复合控件提供稳定 `id`，调用方可提供可见标签或 `aria-label`。构建配置中的超时时间和环境变量使用 `<label htmlFor>`、输入 `id`、稳定 `name` 与适合该非认证字段的 autocomplete 策略。

### 浮层与动效采用共享安全默认值

`BaseModal` 和 `BaseDrawer` 的正文滚动区设置 `overscrollBehavior: 'contain'`，防止滚动链泄漏到页面。工作流边线仅在 `prefers-reduced-motion: no-preference` 时启用；`reduce` 时保留静态高亮，不播放循环动效。

### 焦点由用户动作触发而非属性抢占

构建配置输入不得使用 `autoFocus`。如果后续交互确实需要自动聚焦，只能由明确的用户操作触发，并通过受控 ref 与 effect 聚焦一次；否则保持当前焦点。

## Risks / Trade-offs

- 将卡片改为 Link 需要确保嵌套内容不含其他交互控件。当前卡片内容均为展示，风险可控。
- `FilterForm` 是共享组件；新增必填语义字段前应盘点所有调用方，并为调用方补齐字段文案。
- 受控聚焦可能与 Drawer 的焦点陷阱竞争，因此当前构建配置保持自然焦点顺序，并通过组件测试防止打开时抢占焦点。

## Migration Plan

1. 先补共享布局、浮层和全局样式基线。
2. 调整项目卡片、工作流动效和构建目录编辑器。
3. 扩展筛选表单接口并同步全部调用方。
4. 添加测试，运行前端检查与 OpenSpec 校验；若出现交互回归，可独立回退相应 UI 文件，不影响 API 或数据迁移。

## Open Questions

无。
