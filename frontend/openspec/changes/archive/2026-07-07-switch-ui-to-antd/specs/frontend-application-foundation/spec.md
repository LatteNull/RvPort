## MODIFIED Requirements

### Requirement: Application providers

前端应用 SHALL 初始化 React，并提供顶层 Ant Design 配置、message contextHolder、TanStack Query 和 React Router。

#### Scenario: Application starts

- **WHEN** 浏览器加载 Vite 应用
- **THEN** React SHALL 渲染包含 Ant Design `ConfigProvider`、message `contextHolder`、`QueryClientProvider` 和 `RouterProvider` 的应用树

#### Scenario: Ant Design theme is configured

- **WHEN** Ant Design 组件渲染
- **THEN** 组件 SHALL 通过 Ant Design provider 边界获得 RvPort 当前全局主题值，包括主色和圆角

### Requirement: Styling foundation

前端应用 SHALL 使用 SCSS、CSS Modules 和 Ant Design theme tokens 管理样式。

#### Scenario: Component styles are authored

- **WHEN** 页面或组件需要本地样式
- **THEN** 样式 SHALL 使用 `*.module.scss`

#### Scenario: UI library theme is customized

- **WHEN** foundation 需要自定义 Ant Design 视觉行为
- **THEN** 优先 SHALL 使用 Ant Design `ConfigProvider` theme token 和 component token，而不是散落的全局 CSS 覆盖

#### Scenario: Business styles need local colors

- **WHEN** 业务 CSS modules 需要项目颜色、文本色、边框、阴影或背景
- **THEN** 它们 SHALL 在局部样式中表达当前设计需要，并 SHALL NOT 依赖 Semi CSS 变量或 Ant Design 内部实现变量

#### Scenario: Global reset is applied

- **WHEN** 全局 reset 样式被加载
- **THEN** reset SHALL 避免无意覆盖 Ant Design 组件内部样式

### Requirement: Frontend UI library

RvPort-Frontend SHALL 使用 Ant Design 作为唯一运行时 UI 组件库。

#### Scenario: UI dependencies are reviewed

- **WHEN** reviewer 检查应用运行时依赖
- **THEN** 前端 SHALL 包含 Ant Design，并且 SHALL NOT 包含 `@douyinfe/semi-ui`、`@semi-bot/semi-theme-ryrepo` 或 `@douyinfe/semi-vite-plugin`

#### Scenario: UI imports are reviewed

- **WHEN** reviewer 检查前端源码
- **THEN** 应用运行时代码 SHALL NOT 从 `@douyinfe/semi-ui`、Semi React adapter、Semi theme package 或 Semi Vite plugin 导入

#### Scenario: Data-entry variants are used

- **WHEN** 表单、搜索框、筛选器或轻量控制渲染
- **THEN** 它们 MAY 按交互场景使用 Ant Design 的 `outlined` 或 `filled` 等数据录入 variant
