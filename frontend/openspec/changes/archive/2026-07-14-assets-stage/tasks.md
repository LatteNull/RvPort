## 1. 源码制品领域契约与开发 mock

- [x] 1.1 在 `src/types/project.ts` 定义当前源码制品、压缩包上传、Git 更新、并行 workflow 焦点和聚合当前阶段摘要类型。
- [x] 1.2 在 `src/api/project.ts` 增加 `assets` 阶段详情、源码压缩包上传、Git 更新和阶段推进的领域 API 边界。
- [x] 1.3 在 `mock/project.ts` 实现当前源码制品的读取与覆盖更新、压缩包/Git 失败场景和启动条件失败场景，并使用正式响应包络。
- [x] 1.4 让 `assets` 阶段推进 mock 同时标记六个分析节点运行、返回六条活动边、`focusGroupId=scan` 和聚合当前阶段摘要。

## 2. 并行源码分析 workflow 展示

- [x] 2.1 扩展 Workflow 状态消费逻辑，支持服务端返回的聚合当前阶段摘要和分组焦点，而不改变前端固定拓扑。
- [x] 2.2 实现源码扫描分组的视觉聚焦，并正确展示 `assets` 到六个分析节点的并行活动边。
- [x] 2.3 更新工作台摘要的当前阶段展示，使并行分析时显示服务端聚合文案而非任意单一节点。

## 3. 源码制品管理 Drawer

- [x] 3.1 在 `StageDrawer` 注册 `assets` 专属组件，并建立 `Assets` 的 `overview`、`upload` 和 `git` 子视图结构及嵌套 SCSS 模块。
- [x] 3.2 实现源码制品概览：加载、空态、错误态、来源二选一元数据、版本说明、更新时间和 Footer 操作。
- [x] 3.3 实现压缩包上传子视图：`.zip` 校验、版本说明、上传后动作、提交 loading、失败反馈和未保存表单返回确认。
- [x] 3.4 实现 Git 更新子视图：仓库地址、Ref、可选用户名和 Access Token、敏感凭据不回显、失败反馈和未保存表单返回确认。
- [x] 3.5 实现更新成功后的详情刷新，以及“启动源码分析”的二次确认、workflow 缓存更新、Drawer 关闭和失败恢复。

## 4. 测试与验证

- [x] 4.1 为源码制品表单、敏感凭据不回显、启动六项分析和并行状态映射增加针对性单元测试。
- [x] 4.2 运行 `pnpm test`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `openspec validate assets-stage --type change`。
