## Why

依据 Vercel Web Interface Guidelines 对 `Frontend/src` 的静态审查发现，项目的主要 UI 框架已采用 Ant Design，但共享布局、项目卡片、浮层、工作流动效和少数受控输入仍存在可访问性、减少动态效果、触控滚动及布局稳定性缺口。需要以一个范围受控的前端 change 将这些跨页面基线统一，避免各功能后续重复修补。

## What Changes

- 为主内容区增加跳过导航与语义化 `main` 容器，保证键盘用户能直接进入路由页面内容。
- 将可打开项目的 `ProjectCard` 改为原生可访问的导航/操作元素，移除仅依赖 `article + onClick + tabIndex` 的交互。
- 为品牌 Logo 补充固有尺寸；为共享筛选控件、构建配置等脱离 `Form.Item` 的输入补充关联标签、稳定标识与恰当的 `autocomplete`。
- 在共享 Modal、Drawer 的可滚动正文增加 `overscroll-behavior: contain`；为全局交互元素补齐触控反馈基线。
- 让工作流边线动效遵循 `prefers-reduced-motion`，并仅在允许动效的环境中启用。
- 禁止构建配置输入使用无条件 `autoFocus`，避免移动端或重复打开时抢占焦点。

## Capabilities

### New Capabilities

- `web-interface-guideline-compliance`: 前端共享界面必须满足本 change 规定的键盘、焦点、动效、滚动和输入语义基线。

### Modified Capabilities

<!-- 无既有 capability 需要修改。 -->

## Impact

- 受影响区域：`src/layouts/`、`src/pages/home/components/ProjectCard/`、`src/components/BaseModal/`、`src/components/BaseDrawer/`、`src/components/BaseTable/`、`src/pages/project-detail/Workflow/`、`src/pages/project-detail/StageDrawer/Build/`、全局样式与 `index.html`。
- 不变更后端 API、路由地址、领域数据或新增运行时依赖。
