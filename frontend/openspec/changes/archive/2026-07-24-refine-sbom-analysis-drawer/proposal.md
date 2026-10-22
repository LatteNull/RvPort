## Why

当前 SBOM Drawer 将主操作置于 footer，并通过 Modal 配置分析；同时打开 Drawer 即发起两次环境查询，结果表仍消费较低层的组件候选接口。这使组件替代这一主任务不够突出，且难以与后端真实分析记录和结果契约稳定对齐。

## What Changes

- 将 SBOM Drawer 的主视图重构为“概览 + 替代性结果”，保持标题为“SBOM 分析”。
- 将执行/重新分析放入其对应的状态内容区或标题栏，并使用同一 Drawer 内的配置视图替代 Modal。
- 将环境选择查询延迟至进入配置视图，并在后端支持后以 `status=AVAILABLE` 一次查询后按角色分组。
- 以最新分析聚合接口驱动概览，以正式分析结果接口驱动结果表，并增加分析信息与组件替代详情的次级视图。
- 在迁移输入结果项契约未完成前，不允许结果表提交“加入迁移输入”。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `sbom-analysis`: 调整 SBOM Drawer 的主任务、配置流程、数据读取及结果详情行为。
- `knowledge-base-scan`: 调整知识库扫描 Drawer 的主任务、最新扫描读取、扫描结果与历史记录行为。

## Impact

- 受影响前端：`src/pages/project-detail/StageDrawer/Sbom/`、`src/pages/project-detail/StageDrawer/KnowledgeBase/`、对应 API、类型、Mock 及测试。
- 依赖后端新增或确认：环境 `status` 查询参数、最新分析聚合接口、正式结果详情接口和结果项迁移输入契约。
- 不引入新依赖，也不修改后端代码。
