## Why

当前测试结果比较运行时固定使用 Codex CLI，模型 profile 虽然已经支持多模型和分项探测，但无法让前端选择不同的开源 agent。随着不同模型对不同 agent 协议和工具闭环支持差异变大，后端需要把“模型配置”和“agent 执行器”拆开管理，支持 Codex、DeepSeek Harness 和另一个开源 agent 作为可选运行时。

## What Changes

- 新增 agent runtime 选择能力，支持 `CODEX`、`DEEPSEEK_HARNESS` 和 `OPENCODE` 三类 agent。
- 将阶段绑定从“阶段 -> 模型 profile”扩展为“阶段 -> 模型 profile + agent runtime”。
- 保留现有 `TEST_LOG_COMPARE` 阶段，测试结果比较继续自动触发，但运行时通过阶段绑定解析 agent 和模型。
- 模型 profile 测试能力扩展为可指定 agent runtime 进行基础文本、workspace/tool 闭环和测试比较 schema 探测。
- 后端提供 agent runtime 列表和详情展示 API，供前端选择和展示可用 agent。
- 后端 Docker 镜像需要安装或预留 Codex、DeepSeek Harness、OpenCode 的可执行入口，并在不可用时返回可观测状态。
- 旧 Codex 专用实现需要收敛为通用 agent adapter，不再让业务运行时直接拼接 Codex 命令。
- 不在本 change 中新增新的业务阶段；当前只处理 `TEST_LOG_COMPARE`。

## Capabilities

### New Capabilities

- `agent-runtime-selection`: 管理和选择后端 agent runtime，定义支持的 agent 类型、探测、阶段绑定和运行时解析边界。

### Modified Capabilities

- `model-profile-management`: 模型 profile 测试和阶段绑定需要支持指定 agent runtime。
- `backend-api-design`: 增加 agent runtime 展示/选择 API，并调整模型阶段绑定和模型测试 API。
- `backend-database-design`: 增加 agent runtime 持久化表，并调整阶段绑定表保存 agent runtime 引用。
- `test-result-comparison-runtime`: 测试结果比较运行时需要通过阶段绑定解析 agent runtime，而不是固定 Codex。
- `backend-infrastructure`: 后端容器需要支持 Codex、DeepSeek Harness 和 OpenCode 的安装、路径配置和可用性检查。
- `api-e2e-test-suite`: E2E 需要覆盖 agent runtime 列表、阶段绑定、模型测试和测试比较降级路径。

## Impact

- 影响后端数据库 schema、jOOQ 生成代码、模型管理 API、测试结果比较 runtime、Dockerfile、E2E 脚本和相关中文文档。
- `model_stage_assignments` 需要新增或迁移 `agent_runtime_id`，既有 `TEST_LOG_COMPARE` 绑定应默认关联 Codex agent runtime。
- `model_profiles.executable_path` 当前语义应迁移到 agent runtime；为兼容历史数据，可在迁移时用已有值初始化 Codex runtime，后续模型 profile 不再作为 agent 可执行路径的事实来源。
- Agent 输出、命令行、API key、完整 prompt、完整日志和服务器真实路径仍需脱敏，不得通过 API 返回。
- 本 change 如产生测试比较报告或运行摘要，需要继续登记归档候选。
