## Context

后端已提供模型 Profile 的 CRUD、连通性测试和 `TEST_LOG_COMPARE` 阶段绑定接口，且 API key 已在服务端加密保存。管理中心当前仅包含用户管理和邮箱配置，前端未调用上述接口，因此比较任务会因没有阶段绑定而失败。

## Goals / Non-Goals

**Goals:**

- 在既有管理中心页签中提供一致的模型配置体验。
- 让超级管理员能完成 Profile 创建、配置测试、启停、删除及阶段绑定。
- 明确呈现可执行测试结果比较所需的配置状态。

**Non-Goals:**

- 不新增模型供应商、后端 API 或任意模型调用入口。
- 不在浏览器保存、回显或记录 API key。
- 不改变测试比较 agent 的 prompt、执行协议或任务调度。

## Decisions

- 复用 `AdminLayout` 的页签入口：模型配置与用户、邮箱同属平台级超级管理员配置，避免分散至项目设置。
- 采用列表加 Modal 编辑：Profile 是低频配置对象；Modal 可将敏感字段局部化，并与现有新增/编辑用户交互保持一致。
- 阶段绑定置于页面顶部的单独状态区：当前只有一个阶段 `TEST_LOG_COMPARE`，不引入过度的多阶段表格；选择已启用 Profile 后显式保存绑定。
- 测试动作调用既有 `:test` API，并展示后端返回的兼容性结果。保存 Profile 不等同于测试成功，只有启用、已绑定且 `testLogCompareCompatible=true` 才显示为可用。

## Risks / Trade-offs

- [Codex CLI 在后端运行环境不可用] → 测试结果直接呈现后端受控错误，保存配置不伪装为可用。
- [第三方模型仅支持 Chat Completions] → 表单暴露 `wireApi`，默认 `RESPONSES` 并说明可切换为 `CHAT`。
- [删除已绑定的 Profile] → 沿用后端 `MODEL_PROFILE_ASSIGNED` 约束，前端在确认后展示错误反馈。

## Migration Plan

1. 发布前端页面与管理员页签。
2. 超级管理员创建并测试 Profile。
3. 将通过兼容性测试且启用的 Profile 绑定到 `TEST_LOG_COMPARE`。
4. 若需回滚，移除前端入口即可；后端现有配置数据不受影响。
