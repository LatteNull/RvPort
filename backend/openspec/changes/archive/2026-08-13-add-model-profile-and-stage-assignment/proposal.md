## Why

当前后端只有单个 `codex-provider` 默认配置，无法支持自动化测试结果比较阶段选择专用模型。测试结果比较需要处理较长日志和报告文本，模型的上下文长度、成本、响应稳定性会直接影响结果质量，因此需要把“模型配置”和“测试结果比较阶段绑定”抽象为可管理配置。

## What Changes

- 新增模型配置 profile 管理能力，允许超级管理员维护多个 OpenAI-compatible 模型配置。
- 新增阶段模型绑定能力，允许将某个已启用模型 profile 分配给 `TEST_LOG_COMPARE` 测试结果比较阶段。
- 新建数据库表保存模型 profile 和阶段绑定，不再依赖 `system_configs` 表表达多模型列表。
- 保留 Codex 作为 agent runtime 的执行方式，但将测试结果比较使用的 provider/model 参数从“全局单例配置”升级为“按 `TEST_LOG_COMPARE` 阶段解析的模型配置”。
- API 响应和日志继续只暴露 API key 配置状态和遮蔽摘要，不暴露明文或密文。
- 测试结果比较运行时只通过阶段绑定解析模型；业务任务请求不得直接提交 base URL、API key 或任意模型参数。

## Capabilities

### New Capabilities
- `model-profile-management`: 管理多个模型配置、模型可用性测试和测试结果比较阶段模型绑定。

### Modified Capabilities
- `backend-api-design`: 管理员配置 API 从单个 Codex provider 配置扩展为模型 profile 列表和阶段绑定。
- `backend-database-design`: 新增 `model_profiles` 和 `model_stage_assignments` 持久化要求。
- `backend-app-skeleton`: 模型配置和阶段绑定实现需要覆盖正常流程、异常流程和 edge case。

## Impact

- 新增 Liquibase changelog 和 jOOQ 生成代码。
- 新增或调整管理员模型配置 API、service、repository、请求解析和测试探测逻辑。
- 后续测试结果比较 agent runtime 通过 `TEST_LOG_COMPARE` 阶段 key 获取模型配置。
- 移除旧 `/api/admin/configs/codex-provider` 管理入口；历史 `system_configs.codex-provider` 仅作为一次性迁移来源。
