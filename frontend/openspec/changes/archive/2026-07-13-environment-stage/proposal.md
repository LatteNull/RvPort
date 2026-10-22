## Why

项目流水线的环境管理节点目前只展示通用阶段信息，无法管理 x86 源环境与 RISC-V 目标环境，也无法为源码制品管理、SBOM、构建和测试提供经过验证的环境状态。需要将该节点扩展为专属环境资源管理工作区，并在阶段推进前由后端校验环境前置条件。

## What Changes

- 为 `env` Workflow 节点提供专属 Environment Drawer，默认展示项目的远程环境列表。
- 支持在同一个 Drawer 内切换环境列表、新建环境、修改环境和环境检查视图，不嵌套 Drawer 或 Modal。
- 支持 SSH 环境的新建、修改、连接检查与环境信息采集，并在列表中展示连接和最近采集状态。
- 将环境检查与采集操作绑定到具体环境行；环境列表标题提供新建环境入口。
- 在环境列表 Footer 提供进入源码制品管理的入口，由后端校验 x86 源环境和 RISC-V 目标环境是否可用后推进 Workflow。
- 明确环境详情接口不得返回密码、私钥或密钥正文；敏感凭据仅允许在新建或重新配置时写入。
- 本次不实现运行脚本、执行记录、实时任务日志与 SSE 状态推送。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-pipeline-workbench`: 扩展环境管理节点的专属抽屉、环境资源操作与进入源码制品管理的条件化推进。

## Impact

- 影响 `src/pages/project-detail/StageDrawer/` 的阶段分发与环境管理视图。
- 影响 `src/types/project.ts`、`src/api/project.ts` 和 `mock/project.ts`，新增环境资源与阶段推进相关的数据契约及 mock 接口。
- 复用现有 `BaseDrawer`、`BaseModal`、TanStack Query、Ant Design 和 Vite mock；不新增依赖。
