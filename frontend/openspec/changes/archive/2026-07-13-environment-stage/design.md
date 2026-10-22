## Context

`env` 节点目前复用 Default Drawer，无法展示或维护项目的 SSH 环境。产品与 API 文档已定义环境列表、创建、更新、连接测试和环境信息采集接口；环境状态又是后续 SBOM、构建和测试可用性的前置条件。

环境管理将作为一个工作台型阶段嵌入既有 StageDrawer。用户已确定：环境列表是唯一的环境状态展示来源；新建入口位于列表标题右侧；新建、修改、检查、脚本和记录都在同一个 Drawer 内切换内容，不嵌套 Drawer 或 Modal。

## Goals / Non-Goals

**Goals:**

- 为 `env` 节点提供专属 Drawer 和项目环境列表。
- 支持环境新建、修改、连接检查和环境信息采集。
- 使用环境角色、连接与采集状态约束进入源码制品管理。
- 保证 SSH 密码、私钥和密钥正文不出现在读取模型、缓存或列表中。

**Non-Goals:**

- 不实现脚本执行、执行记录、日志详情、任务取消或 SSE 推送。
- 不实现跳板机、容器直连、交叉编译或环境删除。
- 不新增运行时依赖或全局设计 token。

## Decisions

### 使用单个 Drawer 的内部视图切换

`StageDrawer/Environment/index.tsx` 维护判别式 `view` 状态：`list`、`create`、`edit` 和 `check`。Drawer 本体、遮罩、焦点管理和关闭行为保持不变；Header、Body 和 Footer 随视图切换。

选择该方案而非嵌套 Drawer 或 Modal，是因为环境配置和检查均有完整表单或结果内容。内部视图可保留项目和阶段上下文，并提供一致的返回行为。

### 环境列表为唯一状态摘要

列表展示名称、角色、架构、OS、主机、连接状态、最近采集时间和行级操作。不会额外渲染“环境接入”摘要，避免重复 x86/RISC-V 连接信息。

列表标题右侧提供新建环境；修改、检查与采集均绑定到具体环境行。后续脚本执行与执行记录也必须绑定行内环境，而不是在全局操作中再次选择目标环境。

### API 按环境资源而非阶段详情建模

Environment Drawer 使用 `GET /projects/{projectId}/environments` 加载列表，使用以下资源接口执行 mutation：

- `POST /projects/{projectId}/environments`
- `PATCH /environments/{environmentId}`
- `POST /environments/{environmentId}/test-connection`
- `POST /environments/{environmentId}/collect`

环境列表查询与 mutation 结果通过 TanStack Query 缓存更新或失效刷新。Workflow 推进继续使用既有阶段推进 API，并将返回的 workflow 状态写回画布查询缓存。

### 凭据只写入，不读取

环境读取模型只返回连接配置摘要和 `configured` 等状态，不返回密码、私钥或密钥正文。新建表单根据登录类型展示账号密码或密钥输入；修改表单的敏感字段默认空，只有重新填写才覆盖保存的凭据。

### 进入源码制品管理由后端校验

环境列表 Footer 只显示“进入源码制品管理”。点击后由服务端校验：存在 x86 源环境与 RISC-V 目标环境、两者连接成功、两者均已有环境信息采集结果。校验通过时，服务端将 `env` 置为 DONE 并激活 `assets`；前端关闭 Drawer 并渲染返回的 workflow 状态。

### 首版异步任务使用 mock 终态

连接检查与采集在正式平台中创建异步任务。首版前端调用 mock 后展示终态或失败摘要，并预留状态字段；SSE、实时日志和执行记录在后续 change 接入。

## Risks / Trade-offs

- [内部视图状态增多] → 使用判别式 view 和单一返回入口；仅在视图内容真正复杂时再拆分文件。
- [检查/采集正式接口异步] → 首版统一以任务终态刷新列表，后续接入任务状态和 SSE 时不改变资源模型。
- [凭据处理不当] → 类型、mock 和表单状态均禁止返回或缓存敏感正文；只允许写入覆盖。
- [阶段推进与前端状态不一致] → 后端是唯一前置条件裁决方，前端仅消费返回 workflow 快照。

## Migration Plan

1. 注册 `env` 专属 Drawer，并保留其他未实现阶段继续使用 Default Drawer。
2. 新增环境领域类型、API 模块和 mock 数据，不改变现有项目创建阶段接口。
3. 环境 mutation 成功后刷新环境列表与 workflow 状态；失败时使用既有请求错误反馈。
4. 如需回滚，移除 `env` 的专属分发注册即可恢复 Default Drawer，不影响已有 workflow 拓扑。

## Open Questions

- 首版环境检查是否允许用户选择检查项，还是固定执行连接、基础工具、工作目录与权限检查。
- “采集环境信息”是否作为环境行的独立动作，还是在连接检查成功后自动触发。
- 进入源码制品管理失败时，服务端缺失条件的具体错误结构与前端展示形式。
