# model-configuration-center Specification

## Purpose

定义超级管理员的模型 Profile、Agent Runtime 兼容性测试和知识库 AI/测试比较阶段绑定。

## Requirements

### Requirement: 模型配置权限与 Profile 管理

`/admin/models` SHALL 仅允许超级管理员访问，提供 Profile 创建、编辑、启用/停用、删除与连接测试。API key SHALL 不回显，编辑时留空表示保留已保存密钥。

#### Scenario: 维护模型配置

- **WHEN** 管理员提交合法 Profile
- **THEN** 页面 SHALL 保存配置并刷新相应列表，展示后端返回的配置和测试状态
- **AND** 非管理员 SHALL 被路由守卫阻止访问管理页面

### Requirement: 模型与 Agent 兼容性测试

Profile 测试 SHALL 允许选择已启用的 Agent Runtime，展示按 Agent 返回的兼容性和能力详情，而不是把一次测试等同于某个业务阶段的测试。

#### Scenario: 选择 Agent 发起测试

- **WHEN** 管理员选择有效的 Agent 集合并确认测试
- **THEN** 页面 SHALL 向后端提交选中的 `agentRuntimeIds`，最多 10 个
- **AND** 页面 SHALL 展示测试状态、兼容性结果及按需查看的详情

### Requirement: AI 能力阶段绑定

页面 SHALL 为 `TEST_LOG_COMPARE` 与 `KB_AI_EXTENSION` 分别维护模型 Profile 和 Agent Runtime 绑定，并根据后端返回的绑定、Provider 连通性与 Agent 测试结果展示可用状态及原因。

#### Scenario: 保存绑定

- **WHEN** 管理员为测试结果比较或知识库 AI 建议选择配置并保存
- **THEN** 页面 SHALL PATCH 对应阶段绑定并刷新状态
- **AND** 缺失、停用或不兼容的配置 SHALL 以明确原因显示，不假定两个阶段共用同一绑定
