## 1. 共享可访问性与布局

- [x] 1.1 在 `MainLayout` 与 `AdminLayout` 增加键盘可见的跳过链接和唯一 `main#main-content` 地标，并验证 Header 不遮挡焦点目标。
- [x] 1.2 为主布局 Logo 增加明确的 `width` 与 `height`，保持现有显示尺寸。
- [x] 1.3 为 `BaseModal`、`BaseDrawer` 正文滚动区增加 `overscroll-behavior: contain`，并在全局样式中显式设置触控反馈基线。

## 2. 可访问交互与表单

- [x] 2.1 将首页项目卡片替换为语义化 `Link`，保留卡片视觉样式与项目打开行为。
- [x] 2.2 扩展 `BaseTable/FilterForm` 字段模型，为所有生成控件提供稳定的 `name` 与可访问名称；更新全部调用方和相关测试。
- [x] 2.3 为构建配置输入关联可点击标签、稳定 `id`、`name` 和 autocomplete，并验证打开配置时不会无条件抢占焦点。

## 3. 动效与回归验证

- [x] 3.1 为工作流边线循环动效添加 `prefers-reduced-motion` 分支；减少动态效果时只保留静态激活样式。
- [x] 3.2 为布局、项目卡片、筛选控件、构建配置输入及动效分支新增或更新单元测试。
- [x] 3.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test` 与 `openspec validate improve-web-interface-guidelines --strict`。
