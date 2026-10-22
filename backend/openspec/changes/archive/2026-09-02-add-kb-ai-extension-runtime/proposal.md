## Why

知识库扫描目前只能返回规则库静态建议，无法结合具体源码上下文给出更可执行的迁移处理意见。已有 agent runtime、模型 profile 和阶段绑定能力已经具备基础执行条件，因此可以把 AI 扩展扫描作为 KB 扫描后的增强能力，提升 finding 的解释和处理建议质量。

## What Changes

- 新增知识库 AI 扩展扫描运行时：用户在 KB 扫描结果页点击“AI 扩展扫描”后，后端创建异步任务，导出当前扫描 findings 到 agent workspace 文件，由已配置 agent 读取文件并生成结构化 AI 建议。
- AI 扩展结果逐条入库，并在 KB finding 列表和 finding 详情中直接返回当条最新 AI 建议；前端日常展示不需要额外查询 AI result 列表。
- agent workspace SHALL 包含 findings 输入文件和当前源码只读副本；当 finding 自带信息不足时，agent 可以读取项目源码辅助判断，但不得修改源码。
- 新增 `KB_AI_EXTENSION` 模型阶段绑定，用于管理员配置该节点使用的 agent runtime 和模型 profile。
- 新增 AI 扩展运行记录、输出 artifact、解析校验、任务日志、SSE 进度和失败状态处理。
- 保持原 KB Scanner 输出契约不变：AI 扩展不得修改 `scan-result.json`、`scan-report.html` 或 scanner 主输出结构。

## Capabilities

### New Capabilities

- `kb-ai-extension-runtime`: 定义 KB AI 扩展扫描的任务创建、agent 输入输出、结果入库、查询和安全边界。

### Modified Capabilities

- `kb-scan-runtime`: KB finding 列表和详情需要返回当条 finding 的最新 AI 扩展建议，并保持原 scanner 输出不被修改。
- `model-profile-management`: 阶段模型绑定需要支持 `KB_AI_EXTENSION` 阶段。
- `agent-runtime-selection`: agent runtime 受控阶段需要允许 `KB_AI_EXTENSION` 使用统一 adapter 执行。

## Impact

- 后端 API：新增 KB AI 扩展扫描启动、运行记录查询、readiness 查询和 artifact 下载接口；扩展 KB finding 列表/详情响应字段。
- 数据库：新增 KB AI 扩展运行表、逐条结果表，并扩展阶段绑定枚举/约束和 artifact owner 类型。
- Worker：新增 `KB_AI_EXTENSION` task handler，复用现有任务、日志、SSE、取消、artifact 和 agent adapter 基础设施。
- 安全：继续使用项目权限校验、路径边界校验、路径脱敏、密钥脱敏和 agent workspace 隔离。
- 测试：覆盖正常流程、异常流程和 edge case，并补充 API E2E 模块验证。
