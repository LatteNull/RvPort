## MODIFIED Requirements

### Requirement: Codex Provider 配置实现必须覆盖三类测试
模型 profile 和 `TEST_LOG_COMPARE` 阶段绑定实现 SHALL 配套单元测试和必要的 API E2E 测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 超级管理员创建、查询、更新并测试模型 profile
- **THEN** 测试 SHALL 验证普通配置写入 `model_profiles`
- **AND** 测试 SHALL 验证 API key 加密保存且查询响应只返回遮蔽摘要
- **AND** 测试 SHALL 验证测试接口返回脱敏后的成功或失败摘要
- **AND** 测试 SHALL 验证 `TEST_LOG_COMPARE` 阶段绑定能解析到已启用模型 profile

#### Scenario: 覆盖异常流程
- **WHEN** 非超级管理员访问模型 profile 或阶段绑定 API
- **THEN** 测试 SHALL 验证请求被拒绝
- **WHEN** 请求包含非法 `baseUrl`、非法 `modelProviderType`、非法 `wireApi`、空 `model`、重复 profile 名称、非 `TEST_LOG_COMPARE` 阶段或越界超时参数
- **THEN** 测试 SHALL 验证 API 返回参数校验错误
- **WHEN** Codex executable 不存在、profile 配置不完整、阶段未绑定或绑定 profile 已禁用
- **THEN** 测试 SHALL 验证接口或阶段解析返回受控失败且不泄漏 secret

#### Scenario: 覆盖 edge case
- **WHEN** 更新模型 profile 时未传入 `apiKey`
- **THEN** 测试 SHALL 验证已有 API key 被保留
- **WHEN** 更新模型 profile 时传入空字符串 `apiKey`
- **THEN** 测试 SHALL 验证已有 API key 被清空
- **WHEN** provider 测试失败信息包含 API key、授权头或本地敏感路径
- **THEN** 测试 SHALL 验证响应和持久化摘要均已脱敏
- **WHEN** 删除已被阶段绑定的模型 profile
- **THEN** 测试 SHALL 验证删除被拒绝
