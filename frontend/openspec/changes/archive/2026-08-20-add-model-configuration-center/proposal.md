## Why

测试结果比较依赖模型 Profile 和 `TEST_LOG_COMPARE` 阶段绑定；当前后端能力已完成，但管理中心没有配置入口，导致比较任务无法执行。

## What Changes

- 在管理中心增加“模型配置”页签，仅对超级管理员可见。
- 提供模型 Profile 的列表、创建、编辑、启用状态、连通性测试和删除操作。
- 提供“测试结果比较”阶段与已启用 Profile 的绑定配置，并展示当前绑定与测试兼容性状态。
- 在模型未配置、未绑定或不兼容时，以明确状态提示阻止误以为比较功能可用。

## Capabilities

### New Capabilities

- `model-configuration-center`: 超级管理员维护模型 Profile 并绑定测试结果比较阶段。

### Modified Capabilities

- 无。

## Impact

- 前端管理中心路由、页签、接口客户端与模型配置页面。
- 复用既有 `/api/admin/model-profiles` 和 `/api/admin/model-stage-assignments` 后端接口，不新增后端接口或依赖。
