## Why

当前模型兼容性探测虽然以模型 Profile 和 Agent Runtime 为输入，却固定执行测试结果比较与知识库 AI 扩展的阶段专属输出契约，导致兼容性结论被业务阶段耦合。随着更多 Agent 阶段加入，这种设计会持续扩张探测字段、DTO 和前端矩阵，因此需要把兼容性收敛为“模型 Profile × Agent Runtime”的稳定关系。

## What Changes

- 将模型 Agent 兼容性探测限定为通用 Agent 闭环：模型响应、workspace 读取、workspace 写入和基础结构化结果解析。
- 移除 `TEST_COMPARE_SCHEMA`、`KB_AI_EXTENSION_SCHEMA` 等阶段专属探测及对应兼容性字段。
- **BREAKING**：模型 Profile 与 Agent probe API 不再返回 `testLogCompareCompatible`、`kbAiExtensionCompatible`、`lastTestCompareCompatible` 等阶段兼容性字段。
- 通过 Liquibase 新 changeset 删除不再使用的阶段兼容性数据库列，并同步生成 jOOQ 元数据。
- 保留 `model_stage_assignments`：阶段仍选择模型 Profile 与 Agent Runtime 组合，但不参与兼容性探测和兼容性结论计算。
- 各阶段在实际任务执行时继续验证自己的输出文件和 schema；阶段契约失败只影响该次业务任务，不改写模型与 Agent 的通用兼容性。
- 更新中文 API/数据库文档以及模型管理 E2E，并为变更代码补充正常流程、异常流程和边界条件单元测试，执行项目整体及受影响模块至少 90% 的行覆盖率与可用分支覆盖率验收。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `model-profile-management`: 将兼容性结果定义为模型 Profile 与 Agent Runtime 的通用闭环结果，移除阶段兼容性字段。
- `agent-runtime-selection`: 将 Agent Runtime probe 从阶段 schema 探测改为通用 workspace/tool 闭环探测。
- `backend-api-design`: 调整模型兼容性相关 API 的返回契约，并保持阶段绑定 API 职责独立。
- `api-e2e-test-suite`: 更新模型兼容性 E2E，覆盖通用闭环、多个 Runtime、失败隔离和阶段无关性。

## Impact

- 影响 `CodexProviderProbeService`、probe 名称与结果模型、模型 Profile service/repository/response、数据库迁移和 jOOQ 生成代码。
- 模型管理前端需要停止读取阶段兼容性字段，改为展示每个模型 Profile 与 Agent Runtime 组合的通用兼容状态和分项检查。
- 测试结果比较、KB AI 扩展等实际运行逻辑继续通过 `model_stage_assignments` 解析配置，不改变其任务创建和输出校验入口。
- 历史阶段兼容性列将被删除；通用 probe 历史记录及运行记录继续保留。
