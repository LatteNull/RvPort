## Context

当前 RvPort-Frontend 已完成基础框架：`/home` 通过 lazy route 加载，外层 `MainLayout` 提供顶部栏和内容区，应用已接入 TanStack Query、Axios request client、Vite mock、SCSS Modules 和 Semi UI。

产品文档将首页定义为项目列表页，字段来自 `MVP_INTERACTION_SPEC.md` 中 PL-F01 至 PL-F08；视觉参考来自 `public/首页@2x.png` 和 `public/首页.svg`。这次 change 只把首页从占位页升级为项目列表展示，不实现新建弹窗、项目详情页或多项目迁移状态看板。

## Goals / Non-Goals

**Goals:**

- 用项目卡片网格实现首页项目列表。
- 通过项目列表 API 边界和 Vite mock 提供开发期数据。
- 扩充 mock 数据量，验证列表多行滚动、最后一行展示和 hover 状态在长列表下的表现。
- 用 React Query 负责项目列表请求、加载态、错误态和空态。
- 使用 SCSS Modules 还原设计图中的密度、颜色、卡片、风险角标、阶段条和 hover/active 状态。
- 在保留 Figma 固定卡片尺寸的前提下，通过内容最大宽度约束优化超宽屏右侧空白。
- 数据字段对齐项目列表页 PL 字段，并保留后续进入项目工作台、查看报告和新建项目的扩展点。

**Non-Goals:**

- 不实现新建项目弹窗或新建项目页面。
- 不实现项目详情页、项目工作台、迁移流水线页面或报告页跳转。
- 不实现 US18 多项目迁移状态看板、趋势图、周报导出或全局指标。
- 不修改登录、权限 loader、MainLayout 或路由结构。
- 不在本 change 中调整全局 API 响应包络；mock 继续适配当前 request client 的 `code/data/message` 包络。

## Decisions

### 1. Home 作为项目列表页，能力名独立为 `project-list-home`

基础框架中的 Home 只用于验证路由和 layout，本 change 开始由业务能力接管 `/home`。将项目列表独立成 `project-list-home`，可以避免把后续项目详情、流水线或看板能力混入基础框架 spec。

备选方案是直接修改 `frontend-application-foundation`，但这样会让基础能力承担业务需求，不利于后续归档和范围控制。

### 2. 数据层使用 API 枚举，展示层做文案映射

项目数据中源架构和目标架构使用 API 设计里的枚举，例如 `x86_64` 和 `riscv64`。卡片展示时将 `riscv64` 映射为设计图中的 `RISC-V`。

这样后续接入真实后端时不需要迁移数据模型，也能保持当前设计图的可读标签。

### 3. 项目列表走 React Query，不在页面中手写请求生命周期

Home 页面通过 `useQuery` 调用 `getProjects`。加载态在卡片区域内展示骨架屏，错误态展示可重试提示，空态展示无项目提示。

这延续基础框架已经归档的 server state 边界，也方便后续在新建项目成功后做 query invalidation。

### 4. 项目卡片拆为首页局部组件

`ProjectCard` 放在 `src/pages/home/components/ProjectCard/`，只服务首页项目列表，不提升为全局通用组件。卡片固定展示项目列表字段，样式使用 `index.module.scss`。

后续如果项目概览页也需要复用卡片，再根据真实复用点抽象，不提前创建全局组件。

### 5. 新建按钮与卡片动作只保留视觉和扩展点

本 change 中 `+ 新建` 按钮展示为可点击控件，但不打开弹窗；卡片 hover/active 按设计图展示，但不进入详情。点击行为可以保留 no-op handler 或 TODO 风格的局部函数，不引入路由。

这能让首页视觉和数据先落地，同时避免把新建项目和详情页范围带进来。

### 6. 大屏布局保持固定卡片尺寸，通过内容宽度约束收敛空白

项目卡片继续保持 Figma 中的 315px 固定宽度和 20px 间距，不改为 `1fr` 弹性拉伸。弹性拉伸虽然可以减少右侧空白，但会改变卡片内部状态字段宽度和视觉密度，偏离设计图。

为减少超宽屏上右侧空白过多的问题，首页内容区域增加最大宽度约束，让卡片网格在较宽屏幕上停止无限向右铺展。标题区与卡片网格保持同一内容宽度，仍然左对齐。

### 7. Mock 数据覆盖滚动验证

开发期 mock 项目数量扩充到足以产生多行列表和页面滚动。数据应覆盖报告可用、扫描中、不同构建状态、不同测试状态、长项目名和高风险数等组合，方便在本地直接观察列表滚动、hover 蒙层、卡片换行和最后一行布局。

## Risks / Trade-offs

- [Risk] 设计图中的卡片是固定 1440 宽布局，实际浏览器宽度变化会导致卡片换行和间距变化。→ 使用 CSS Grid 的 `minmax` 和固定卡片最小宽度，在桌面端贴近设计，在窄屏自然降列。
- [Risk] 超宽屏下固定卡片从左排列会产生明显右侧空白。→ 保留固定卡片尺寸，同时给首页内容加最大宽度约束，不通过拉伸卡片牺牲设计密度。
- [Risk] mock 数据过少无法验证滚动和最后一行布局。→ 扩充 mock 项目数量，但仍只作为开发期数据，不改变真实 API 边界。
- [Risk] 当前 request client 使用 `code/data/message`，根目录 API 设计使用 `success/data/traceId`。→ 本 change 的 mock 先适配当前 request client；后续单独处理响应包络统一。
- [Risk] 设计图里文本部分来自 SVG path，无法直接抽取全部字体指标。→ 使用 Semi/SCSS 还原主要视觉密度，优先保证信息层级、间距、颜色和状态清晰。
- [Risk] 暂不实现跳转可能让按钮看起来可操作但无结果。→ 文案和 spec 明确本 change 只提供视觉与扩展点；后续新建项目和详情页 change 接管行为。

## Migration Plan

1. 新增项目类型、项目 API 和覆盖多行滚动场景的 mock 数据。
2. 将 Home 页面替换为项目列表容器，并通过 React Query 加载数据。
3. 新增 ProjectCard 局部组件和样式，按设计图还原卡片网格。
4. 补齐 loading、error、empty 和正常列表状态。
5. 增加首页内容最大宽度约束，避免超宽屏右侧空白过多。
6. 运行格式、lint、typecheck 和 OpenSpec validate。

回滚时可删除项目列表相关 API、类型、mock 和卡片组件，并恢复当前最小 Home 占位页。
