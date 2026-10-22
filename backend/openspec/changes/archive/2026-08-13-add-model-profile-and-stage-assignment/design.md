## Context

当前后端已经实现单个 `codex-provider` 配置，配置保存在 `system_configs` 的 `codex-provider` namespace 中，并通过 Codex CLI 调用 OpenAI-compatible 模型。这个设计只能表达一个全局默认 provider，无法支持“为测试结果比较选择专用模型”的产品形态。

本 change 只处理自动化测试结果比较阶段。测试结果比较可能输入两侧大段日志、报告文件摘要和退出码，需要更强的上下文窗口和更稳定的模型，因此模型配置需要成为可管理资源，`TEST_LOG_COMPARE` 阶段绑定需要成为独立配置。

## Goals / Non-Goals

**Goals:**
- 支持超级管理员维护多个模型 profile。
- 支持将模型 profile 绑定到固定使用阶段 `TEST_LOG_COMPARE`。
- 使用新建表保存模型 profile 和阶段绑定，便于列表、测试状态、启停、排序和审计。
- 保持 API key 加密保存，并在 API、日志、测试摘要中脱敏。
- 为后续测试结果比较 agent runtime 提供按 `TEST_LOG_COMPARE` 阶段解析模型配置的服务入口。

**Non-Goals:**
- 不在本 change 实现自动化测试日志比较 agent。
- 不允许业务任务请求直接传入任意 base URL、API key 或模型参数。
- 不设计用户级、项目级或租户级模型覆盖规则。
- 不支持非 OpenAI-compatible provider 类型，除非后续 change 扩展。
- 不实现迁移报告摘要、finding 解释、通用助手或其他阶段的模型绑定；这些阶段后续单独提出。

## Decisions

### 新建表而不是继续使用 system_configs

使用 `model_profiles` 保存模型配置，使用 `model_stage_assignments` 保存阶段绑定。

原因：
- 多模型天然是列表资源，需要分页、启停、默认排序、唯一名称和测试状态。
- API key 需要和 profile 生命周期绑定，删除或禁用 profile 时行为明确。
- 阶段绑定需要外键约束，避免绑定到不存在的模型。

备选方案是把 profiles 保存为 `system_configs` 中的大 JSON。这个方案实现快，但排序、局部更新、测试状态、唯一约束和后续扩展都会变差。

### 阶段使用稳定枚举

阶段使用后端白名单枚举，本 change 初始只包含：
- `TEST_LOG_COMPARE`

原因：
- 阶段绑定是运行时安全边界，不能让前端提交任意字符串驱动模型选择。
- 后续新增阶段必须通过新的 OpenSpec change 和代码显式扩展。

### Codex 仍作为 runtime，模型 profile 只表达模型连接参数

`model_profiles` 保存 `modelProviderType`、`baseUrl`、`model`、`wireApi`、`apiKey`、`timeoutSeconds`、`maxRuntimeSeconds` 等参数。Codex executable path 可以先作为 profile 字段保存，或者保留全局默认值并允许 profile 覆盖。

原因：
- 当前实现已经通过 Codex CLI 运行 provider 测试。
- 后续测试结果比较需要 Codex 作为 agent runtime，而不是后端直接调用 LLM API。

### 移除旧 codex-provider API

新能力以 `/api/admin/model-profiles` 和 `/api/admin/model-stage-assignments` 为准。旧 `/api/admin/configs/codex-provider` 管理入口不再保留，避免出现 `system_configs` 和 `model_profiles` 两套运行事实来源。

历史 `system_configs.codex-provider` 数据只允许作为一次性迁移来源，用于生成默认模型 profile；运行时解析、阶段绑定和管理 API 均不得继续读取旧入口。

## Risks / Trade-offs

- 旧配置迁移不完整 → 在迁移时将已有 `system_configs.codex-provider` 转换为一个默认 profile，并保证旧配置不作为运行事实来源。
- 测试结果比较阶段未绑定模型导致任务失败 → 阶段解析服务返回明确 `MODEL_ASSIGNMENT_MISSING`，测试结果比较任务在创建或执行前失败。
- API key 泄漏 → API 只返回 `apiKeyConfigured` 和遮蔽摘要，测试错误统一脱敏。
- 禁用或删除被绑定 profile → 禁用 profile 后阶段解析应失败；删除被绑定 profile 应被拒绝或先解除绑定。
- 多模型测试调用外部 API 成本不可控 → `:test` 使用短 prompt、短超时，并保存脱敏测试摘要。

## Migration Plan

1. 新增 Liquibase changelog 创建 `model_profiles` 和 `model_stage_assignments`。
2. 如存在 `system_configs` 的 `codex-provider` 配置，迁移为一个默认 profile。
3. 实现 profile 管理 API 和阶段绑定 API。
4. 将 Codex provider 解析逻辑改为可基于 profile 解析。
5. 后续测试结果比较任务只通过 `TEST_LOG_COMPARE` 阶段绑定获取模型配置。
