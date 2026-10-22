## 1. 项目列表数据边界

- [x] 1.1 新增 `ProjectListItem` 等项目列表类型，字段覆盖项目名称、源架构、目标架构、当前阶段、高风险数、最近扫描时间、最近构建状态、最近测试状态和报告可用状态。
- [x] 1.2 新增 `src/api/project.ts`，提供 `getProjects` API 方法，并复用现有 Axios request client。
- [x] 1.3 新增 `mock/project.ts`，在 Vite serve 模式下提供 `GET /api/projects` mock 数据，并使用当前 `code/data/message` 响应包络。
- [x] 1.4 准备与设计图一致的 mock 项目数据，覆盖有风险数、无风险数、扫描中、未开始、报告可用和缺省状态值。

## 2. 首页页面结构

- [x] 2.1 将 `src/pages/home/index.tsx` 从基础占位页改为项目列表页容器。
- [x] 2.2 使用 `useQuery` 调用 `getProjects` 加载项目列表，不使用 `useEffect + useState` 管理请求生命周期。
- [x] 2.3 实现标题区，包含“项目列表”、辅助说明“创建项目或进入已有迁移流水线”和 `+ 新建` 按钮。
- [x] 2.4 `+ 新建` 按钮只提供视觉与扩展点，不打开弹窗、不跳转新建项目页。

## 3. 项目卡片组件

- [x] 3.1 新增 `src/pages/home/components/ProjectCard/` 局部组件。
- [x] 3.2 卡片展示项目名称、架构标签、高风险数、当前阶段、最近扫描时间、最近构建状态和最近测试状态。
- [x] 3.3 将数据层 `riscv64` 展示为 `RISC-V`，并保留 `x86_64` 展示。
- [x] 3.4 对缺失的扫描、构建或测试状态展示中性占位。
- [x] 3.5 对报告可用项目展示“评估报告”类入口文案，但不实现报告页跳转。

## 4. 视觉与状态

- [x] 4.1 使用 SCSS Modules 按 `public/首页@2x.png` 还原页面间距、卡片宽度、网格布局和视觉密度。
- [x] 4.2 还原风险角标、架构标签、阶段条、状态字段和蓝/橙两类阶段视觉。
- [x] 4.3 实现卡片 hover/focus/active 视觉状态。
- [x] 4.4 在项目列表区域实现骨架屏 loading 状态，不使用整页 Spin。
- [x] 4.5 实现项目列表错误态和重试操作。
- [x] 4.6 实现空列表状态。
- [x] 4.7 确认窄屏下卡片自然降列，文字不溢出、不互相遮挡。

## 5. 范围控制

- [x] 5.1 不实现新建项目弹窗、新建项目页面、项目详情页、迁移流水线跳转或报告页跳转。
- [x] 5.2 不引入 US18 多项目迁移状态看板、趋势图、周报导出或全局指标。
- [x] 5.3 不修改登录、权限 loader、MainLayout 或现有路由结构。
- [x] 5.4 不调整全局 API 响应包络；保持本 change mock 适配当前 request client。

## 6. 验证

- [x] 6.1 运行 `pnpm format:check`。
- [x] 6.2 运行 `pnpm lint`。
- [x] 6.3 运行 `pnpm typecheck`。
- [x] 6.4 运行 `pnpm build`。
- [x] 6.5 运行 `openspec validate build-project-list-home`。

## 7. 设计图核对修正

- [x] 7.1 将 MainLayout 顶部品牌从文字改为设计图中的 RvPort logo。
- [x] 7.2 将首页项目卡片横向间距调整为设计图中的 20px，并保持 315px 卡片宽度。

## 8. Figma 126:2 设计还原完善

- [x] 8.1 将首页标题与说明文字行高调整到 Figma 设计图的 30px / 22px。
- [x] 8.2 将项目卡片标题、架构标签、风险角标、阶段条和状态字段的字号、字重与间距收敛到 Figma 设计图。
- [x] 8.3 同步调整项目列表骨架屏尺寸，避免 loading 状态与真实卡片布局跳动。
- [x] 8.4 参考 Figma `9:319` 为项目卡片增加 hover 动画和“进入流水线”视觉入口，不实现跳转行为。

## 9. 列表滚动与大屏布局完善

- [x] 9.1 扩充 `mock/project.ts` 项目数量和状态组合，用于验证多行列表、页面滚动、长项目名和最后一行布局。
- [x] 9.2 为首页内容区域增加最大宽度约束，保留 315px 固定卡片宽度并减少超宽屏右侧空白。
- [x] 9.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `openspec validate build-project-list-home`，不运行 `pnpm build`。

## 10. 主布局内容滚动

- [x] 10.1 将 MainLayout 改为固定视口高度的纵向 flex 布局，避免长列表触发页面级滚动。
- [x] 10.2 将滚动容器收敛到 `Content`，让 header 不被页面滚动条覆盖。
- [x] 10.3 为 `Content` 增加局部滚动条样式，不全局覆盖浏览器或 Semi 内部滚动条。

## 11. 骨架屏与卡片外壳复用

- [x] 11.1 使用 Semi `Skeleton` 替换首页手写骨架屏动画。
- [x] 11.2 将首页项目卡片外壳样式提升到 `home.module.scss`，让真实卡片和 Skeleton 复用同一外壳。
- [x] 11.3 将真实卡片 hover/active 外壳交互保留在 Home 层，`ProjectCard` 只保留卡片内部内容样式。
