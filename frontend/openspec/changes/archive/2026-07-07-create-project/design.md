## Context

首页项目列表已经提供 `+ 新建` 入口，但当前入口不触发创建流程。根目录交互文档将创建项目描述为“新建项目页”，字段包含项目名称、描述、源架构、目标架构和源码输入方式；当前产品实现方向改为在首页打开 Modal，以减少页面跳转并对齐设计图中的统一弹窗样式。

现有前端已经具备 React Router、TanStack Query、Axios request client、Vite mock、SCSS Modules 和 Ant Design。接口响应包络已对齐正式 `success/data/error/traceId/timestamp` 结构，新增 mock 和 API 需要继续遵守该约定。

## Goals / Non-Goals

**Goals:**

- 在首页 `+ 新建` 上接入创建项目弹窗。
- 封装一个轻量公共业务 Modal，用来统一设计图中的弹窗外观。
- 实现项目基础字段表单、校验、提交、成功反馈和列表刷新。
- 新增 `POST /projects` API 方法和 Vite mock。

**Non-Goals:**

- 不实现独立新建项目页面。
- 不实现源码压缩包上传、Git 拉取、Git 账号密码、环境管理或创建后自动跳转。
- 不实现项目详情页、项目概览页或迁移流水线导航。
- 不新增主题包或第三方依赖。

## Decisions

### 1. 使用业务 Modal 包裹 Ant Design Modal

封装 `BaseModal` 公共组件，底层使用 Ant Design 的 `Modal`。公共组件通过 Ant Design Modal 的 `title` 和 `footer` 承载业务 header/footer，只用集中 CSS 补齐设计图需要的 header/footer border、padding、body 滚动和关闭按钮位置。

弹窗宽度不做全局写死。公共 Modal 可以提供一个默认宽度，但必须继续透传 Ant Design Modal 的 `width` 等基础 props，让新建项目、源码上传、环境配置等不同业务弹窗按设计图覆盖自己的宽度。

备选方案是每个业务弹窗直接改 Ant Design Modal 样式。该方案初期更快，但会让后续环境、源码、扫描、构建、测试等弹窗重复处理相同视觉差异。轻量封装能保留 Ant Design 的可访问性和交互能力，同时减少重复样式。

### 2. 业务表单放在首页领域组件中

创建项目弹窗作为首页相关组件实现，例如 `src/pages/home/components/CreateProjectModal`。它使用公共 Modal 和 Ant Design Form，负责字段默认值、校验、提交状态和关闭行为。

创建项目弹窗应参考 Figma `node-id=14-296`：

- 弹窗宽度为 `800px`。
- 内容左右间距为 `24px`，表单字段单列铺满内容区。
- 表单分为“项目基本信息”和“架构配置与源码来源”两个区块。
- footer 使用 Modal footer 区域，按钮右对齐，包含“取消”“保存”“保存并进入环境管理”。

`src/pages/home/index.tsx` 只保留页面级编排：标题区、项目列表、`+ 新建` 按钮、弹窗 open/close 状态，以及创建成功后的列表刷新入口。表单字段、mutation、提交 loading 和错误反馈不应堆在首页文件中。

公共 Modal 不感知项目字段、API、query key 或业务按钮文案，避免形成过厚抽象。

### 3. 本次只提交基础创建请求

`POST /projects` 请求使用根目录 API 设计中的基础字段：

- `name`
- `description`
- `sourceArch`
- `targetArch`
- `sourceInputType`

源码上传和 Git 拉取在产品文档中属于创建项目后的源码入口能力，本次只记录用户选择的源码输入方式，不提交文件或凭据。Figma `node-id=14-296` 默认展示“稍后在源码管理页导入”，因此 `sourceInputType` 需要支持稍后导入、源码压缩包、Git 更新三种选择，并默认稍后导入。

### 4. 创建成功后刷新项目列表

创建接口通过 `src/api/project.ts` 暴露为 `createProject`，业务 API 使用 `request.post<ProjectListItem>` 或明确的创建结果类型。提交成功后关闭弹窗、显示成功反馈，并 invalidate 首页项目列表 query。

这延续首页已有 TanStack Query 数据边界，也避免手动维护列表状态造成 mock 与真实 API 切换时行为不一致。

## Risks / Trade-offs

- [Risk] 根目录文档写的是新建项目页，而当前实现选择 Modal。→ 在 OpenSpec 中明确承载形态变化，但保持字段、按钮语义和 `POST /projects` API 不变。
- [Risk] 公共 Modal 封装过厚会限制后续不同业务弹窗。→ 公共组件只处理壳层视觉与基础交互，业务内容、footer 动作和表单留给调用方。
- [Risk] 本次不处理源码上传/Git 拉取，会让源码输入方式看起来未完整落地。→ 在文案和 spec 中明确本次只创建项目上下文，源码导入能力后续单独 change 实现。
- [Risk] 创建成功后如果 mock 数据只保存在内存，刷新页面会丢失新增项目。→ 开发期可接受；真实后端接入后由服务端持久化。

## Migration Plan

1. 增加公共 Modal 组件和样式，不影响现有页面。
2. 增加项目创建类型、API 和 mock。
3. 在首页接入创建弹窗和 query invalidation。
4. 按小改约定运行 format、lint、typecheck 和 `openspec validate create-project`。
