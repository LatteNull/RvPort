## 1. 公共 Modal

- [x] 1.1 新增轻量公共业务 Modal 组件，底层使用 Ant Design Modal，并透传必要 Modal props。
- [x] 1.2 新增公共 Modal 的 SCSS Module，统一默认宽度、标题区、内容区、footer、关闭按钮和遮罩视觉。
- [x] 1.3 支持业务弹窗通过 `width` 覆盖公共 Modal 默认宽度。
- [x] 1.4 确认公共 Modal 不包含项目字段、API 调用、query invalidation 或业务文案。

## 2. 项目创建数据边界

- [x] 2.1 扩展项目类型，新增创建项目请求类型和源码输入方式枚举或联合类型。
- [x] 2.2 在 `src/api/project.ts` 新增 `createProject`，通过 `request.post<T>('/projects', data)` 调用 `POST /projects`。
- [x] 2.3 扩展 `mock/project.ts`，支持 `POST /api/projects`，校验项目名称并返回正式响应包络。
- [x] 2.4 mock 创建成功后将新项目加入开发期项目列表，便于首页刷新后看到新增数据。

## 3. 创建项目弹窗

- [x] 3.1 在首页组件目录新增 `CreateProjectModal`，使用公共 Modal 和 Ant Design Form。
- [x] 3.2 表单包含项目名称、项目描述、源架构、目标架构和源码输入方式。
- [x] 3.3 设置默认值：源架构 `x86_64`、目标架构 `riscv64`、源码输入方式为上传源码压缩包。
- [x] 3.4 实现项目名称必填校验，提交时展示 loading 状态。
- [x] 3.5 创建失败时保持弹窗打开并展示错误反馈。
- [x] 3.6 将表单字段、mutation、提交 loading 和错误反馈保留在 `CreateProjectModal` 内，避免堆入首页文件。

## 4. 首页接入

- [x] 4.1 将首页 `+ 新建` 按钮接入弹窗开关状态。
- [x] 4.2 创建成功后关闭弹窗、展示成功提示，并 invalidate 项目列表 query。
- [x] 4.3 首页文件只保留页面级编排和弹窗 open/close 状态。
- [x] 4.4 保持项目详情、报告跳转、源码上传、Git 拉取和环境管理不在本次实现范围内。

## 5. 验证

- [x] 5.1 运行 `pnpm format:check`。
- [x] 5.2 运行 `pnpm lint`。
- [x] 5.3 运行 `pnpm typecheck`。
- [x] 5.4 运行 `openspec validate create-project`。
