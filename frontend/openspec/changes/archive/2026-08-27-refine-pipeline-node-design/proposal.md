## Why

当前项目流水线画布的节点名称、副标题和 Drawer 操作仍按早期单线流程表达，无法准确反映节点的多个输入与输出。需要从起始节点开始逐一梳理，使画布、节点内容和 Drawer 操作表达同一套业务关系。

## What Changes

- 将第一个 Workflow 节点由“项目创建”调整为“项目基础配置”，表达它是持续可查看、编辑的项目基础信息节点，而非一次性历史事件。
- 移除该画布节点的泛化副标题，避免重复解释标题；节点详情保留在 Drawer 中展示。
- 将项目基础配置 Drawer footer 从单一“进入环境管理”入口改为与节点输出一致的两个同级入口：“进入环境管理”和“进入源码管理”。
- 将环境管理 Drawer 的项目级环境区块更名为“当前运行环境”，从仅服务“分析”的旧语义调整为后续构建、验证、测试等环境相关操作共用的项目级运行环境配置。
- 脚本运行表单的脚本编辑区必须展示行号，便于定位脚本内容。
- 整理脚本执行记录：不再展示 `scriptSha256` 或前端推导的脚本名称/类型，改用执行 ID 标识记录；退出码以普通文本呈现。卡片、筛选器和表格统一使用连接状态。
- 将脚本执行日志页从旧的日志元数据/摘要卡片展示迁移至任务日志内容接口。完成态通过 `GET /api/tasks/{taskId}/log-content` 读取 `merged`、`stdout`、`stderr` 正文并支持按类型向上分页；旧日志元数据接口仅用于受控下载。
- 压缩执行日志页顶部概要，使用紧凑的横向信息布局承载状态、提交时间、退出码、日志数量和执行摘要，将主要空间留给日志内容。
- 编辑项目级运行环境时，环境候选查询增加 `status=AVAILABLE` 过滤；保留前端对启用状态和连接成功状态的校验。
- 弱化私钥导入等拖拽区域的辅助提示文字颜色，使其使用次级文本层级。
- 调整源码管理节点副标题为实际支持的“Git / 源码压缩包”；源码 Drawer 仅请求并展示当前有效源码，Git 仓库地址可跳转并展示 Git 分支，收敛空状态和上传辅助提示，并在关闭后释放缓存。
- 知识库扫描 Drawer 打开时强制读取最新扫描状态，关闭时清理扫描列表、详情和关联结果缓存，避免复用五分钟全局查询缓存。
- 知识库扫描结果列表统一使用“风险”语义：文件和风险列固定在左侧，行号随横向滚动；每行提供迁移输入操作。
- 将 Node 6 固化为 x86 构建节点，移除无实际业务意义的构建前置提示，收敛构建配置与日志操作；完成态日志适配最新到更旧的分页协议。
- 新增 Node 7 依赖分析 Drawer：按后端结果映射风险、依赖类型和目标侧匹配状态，提供分析概览、历史记录、制品下载、依赖详情及迁移输入操作。
- Node 8 评估报告补齐依赖分析来源、风险和目标侧匹配状态的中文展示映射。
- 后续按节点逐项补充画布名称、输入输出关系和 Drawer 行为；本 proposal 已固化 Node 1 至 Node 8 当前已确认的方向。

## Capabilities

### New Capabilities

<!-- 本 change 不新增独立能力。 -->

### Modified Capabilities

- `project-pipeline-workbench`: 调整项目起始节点的画布表达和其 Drawer 的分流操作。
- `project-environment-management`: 调整项目级运行环境语义、脚本执行记录与完成态日志展示，并对接任务日志内容接口。
- `project-source-management`: 调整源码版本的画布表达、列表展示与缓存策略。
- `project-knowledge-base-scan`: 调整扫描入口的查询缓存策略。
- `project-x86-build`: 调整构建前置条件、配置布局和完成态日志分页展示。
- `project-dependency-analysis`: 新增依赖分析结果的概览、映射、详情和迁移输入入口。
- `project-assessment-report`: 补齐依赖分析输入在评估报告中的展示映射。

## Impact

- 受影响前端区域：`src/pages/project-detail/Workflow/`、项目基础配置 Drawer、`src/pages/project-detail/StageDrawer/Environment/`、`src/pages/project-detail/StageDrawer/Assets/`、`src/pages/project-detail/StageDrawer/KnowledgeBase/`、`src/pages/project-detail/StageDrawer/X86Build/`、`src/pages/project-detail/StageDrawer/DependencyAnalysis/`、`src/pages/project-detail/StageDrawer/AssessmentReport/`、项目 API 类型与其单元测试。
- 前端将接入后端已提供的 `GET /api/tasks/{taskId}/log-content`；不新增或变更后端 API、任务状态和服务端数据契约。
