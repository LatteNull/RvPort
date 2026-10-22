## Why

首页已经具备项目列表和 `+ 新建` 入口，但目前入口不触发创建流程。为了打通 MVP 的项目创建起点，需要在首页提供新建项目弹窗，让用户可以创建迁移项目并刷新项目列表。

设计图中的弹窗形态与 Ant Design 默认 Modal 存在统一视觉差异，后续多个业务弹窗也会复用该样式，因此本变更需要同时建立轻量的业务 Modal 外壳。

## What Changes

- 新增项目创建弹窗，由首页 `+ 新建` 按钮打开。
- 新增轻量公共业务 Modal 组件，底层使用 Ant Design Modal，统一标题区、内容区、footer、宽度、遮罩和关闭行为。
- 新增项目创建表单，覆盖 MVP 新建项目基础字段：项目名称、项目描述、源架构、目标架构、源码输入方式。
- 新增 `POST /projects` API 边界和 Vite mock，响应使用正式 `success/data/error/traceId/timestamp` 包络。
- 创建成功后关闭弹窗、提示成功，并通过 TanStack Query 刷新首页项目列表。
- 本变更不实现源码上传、Git 拉取、环境管理、项目详情页或创建后自动跳转。

## Capabilities

### New Capabilities

- `project-creation`: 覆盖首页创建项目弹窗、项目创建表单、创建 API 调用、成功/失败反馈和列表刷新。

### Modified Capabilities

- `project-list-home`: 将首页 `+ 新建` 按钮从仅展示入口改为打开新建项目弹窗。

## Impact

- 影响 `src/pages/home` 的新建入口状态管理和 query invalidation。
- 新增或扩展 `src/api/project.ts`、`src/types/project.ts` 和 `mock/project.ts`。
- 新增公共 Modal 组件及其 SCSS Module 样式。
- 依赖现有 React Router、TanStack Query、Axios request client、Ant Design、SCSS Modules 和 Vite mock。
