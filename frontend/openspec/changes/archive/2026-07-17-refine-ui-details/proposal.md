## Why

当前前端已完成 Ant Design 切换和主要业务页面搭建，但仍存在一些 UI 细节需要持续打磨。典型问题是 `/home` 项目列表在中等宽度窗口或浏览器右侧打开 DevTools 时，右侧会出现明显空白。

这次 change 用于收敛轻量 UI 细节调整，先处理全局内容容器、横向边距和首页项目卡片网格自适应问题，后续同类小范围视觉一致性问题也可以继续纳入。

## What Changes

- 在主布局中增加统一的页面内容内层容器，用于控制页面最大宽度和居中显示。
- 将全局页面内容最大宽度设置为适合当前项目卡片密度的宽度，避免只在 Home 页面单独维护。
- 调整主内容和顶部 Header 的横向 padding，使中等宽度窗口下留白不过宽，并保持页面内容与 Header 对齐。
- 调整首页项目卡片网格，使卡片列最小宽度保持当前设计密度，同时允许列宽自动拉伸填满可用空间。
- 为项目流水线工作台顶部四张摘要卡片增加与信息语义对应的低对比度背景图，并统一标题、辅助文本和风险状态颜色。
- 允许继续纳入不改变业务流程的小范围 UI 细节修正，例如间距、对齐、轻量响应式行为和视觉状态微调。
- 不新增依赖，不调整 API，不引入新的设计 token 层。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `frontend-application-foundation`: 增加主布局页面内容容器的全局宽度、居中和横向 padding 规范。
- `project-list-home`: 调整项目卡片网格在不同宽度下的自适应行为，减少右侧空白。
- `project-pipeline-workbench`: 优化顶部项目摘要卡片的背景图和信息层级样式。

## Impact

- 影响文件：
  - `src/layouts/MainLayout/index.tsx`
  - `src/layouts/MainLayout/index.module.scss`
  - `src/pages/home/home.module.scss`
  - `src/pages/project-detail/index.tsx`
  - `src/pages/project-detail/index.module.scss`
  - `src/assets/images/detail/*.svg`
- 不影响后端 API、mock 数据结构或运行时依赖。
- 视觉影响集中在认证后主布局、`/home` 项目列表页，以及后续纳入的轻量 UI 细节位置。
