## ADDED Requirements

### Requirement: Codex Provider 配置实现必须覆盖三类测试
Codex provider 配置实现 SHALL 配套单元测试和必要的 API E2E 测试，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 超级管理员保存、查询并测试 Codex provider 配置
- **THEN** 测试 SHALL 验证普通配置写入 `system_configs`
- **AND** 测试 SHALL 验证 API key 加密保存且查询响应只返回遮蔽摘要
- **AND** 测试 SHALL 验证测试接口返回脱敏后的成功或失败摘要

#### Scenario: 覆盖异常流程
- **WHEN** 非超级管理员访问 Codex provider 配置 API
- **THEN** 测试 SHALL 验证请求被拒绝
- **WHEN** 请求包含非法 `baseUrl`、非法 `modelProviderType`、非法 `wireApi`、空 `model` 或越界超时参数
- **THEN** 测试 SHALL 验证 API 返回参数校验错误
- **WHEN** Codex executable 不存在或 provider 配置不完整
- **THEN** 测试 SHALL 验证测试接口返回受控失败且不泄漏 secret

#### Scenario: 覆盖 edge case
- **WHEN** 保存配置时未传入 `apiKey`
- **THEN** 测试 SHALL 验证已有 API key 被保留
- **WHEN** 保存配置时传入空字符串 `apiKey`
- **THEN** 测试 SHALL 验证已有 API key 被清空
- **WHEN** provider 测试失败信息包含 API key、授权头或本地敏感路径
- **THEN** 测试 SHALL 验证响应和持久化摘要均已脱敏
