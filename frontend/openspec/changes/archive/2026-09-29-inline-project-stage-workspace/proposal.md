## Why

完整 Workflow 能直观展示流程关系，但在画布旁长期放置操作内容会让两者都过于局促。原试验中的“总览画布 → 左侧画布加右侧内容 → 展开画布”形成了三个近似页面。项目工作台改为两个用途明确的视图：Workflow 用于理解全局关系，Step 用于连续操作。

## What Changes

- Workflow 视图保留完整、可平移缩放的十二阶段画布。点击节点仍以 Drawer 查看或操作阶段内容。
- Step 视图恢复原有分组式紧凑导航，右侧为阶段内容；导航强调阶段顺序、分组、辅助说明、事实状态和当前阶段，不在有限宽度内复刻拓扑依赖连线。
- 阶段业务内容复用同一组件；展示载体由 Drawer 或内嵌 Panel 决定。全部十二阶段均可在 Step 内直接查看和操作，阶段内部的局部弹窗与详情面板保留原有行为。
- URL 改为 `/projects/:id/workflow`、`/projects/:id/workflow/:stageId` 和 `/projects/:id/steps/:stageId`，支持深链接与浏览器历史，不兼容旧 `panel` 查询参数。
- 切换视图保留所选阶段的定位和服务端数据；不承诺完整保留滚动、筛选或局部弹窗。对未保存的表单更改，离开前明确确认。
- 沿用既有桌面端宽度规则；不增加接口、依赖或移动端重排。

## Capabilities

### Modified Capabilities

- `project-pipeline-workbench`：全部阶段的双视图导航、URL、共享载体与未保存更改保护。
- `environment-management`：同一环境业务内容在 Drawer 和 Panel 两种载体中复用，局部表单与详情面板保持原有操作。

## Impact

影响项目详情的路由、Workflow 节点导航、全部阶段载体、首页项目入口及测试。不复制阶段业务组件；Step 与 Workflow 只切换承载方式。
