## ADDED Requirements

### Requirement: 管理中心展示模型配置入口

系统 SHALL 向超级管理员展示管理中心的“模型配置”页签，并在非超级管理员访问时维持既有权限保护。

#### Scenario: 超级管理员进入模型配置

- **WHEN** 超级管理员在管理中心选择“模型配置”
- **THEN** 系统展示模型 Profile 与测试结果比较阶段绑定状态

#### Scenario: 普通用户访问管理接口

- **WHEN** 非超级管理员请求模型 Profile 或阶段绑定接口
- **THEN** 系统拒绝该请求并返回既有权限错误

### Requirement: 管理员维护模型 Profile

系统 SHALL 允许超级管理员创建、编辑、启用或停用、测试和删除模型 Profile，并且不得在页面回显 API key 明文。

#### Scenario: 创建并测试 Profile

- **WHEN** 管理员提交完整的 OpenAI-compatible Profile 配置后发起测试
- **THEN** 系统保存 Profile 并展示后端返回的连通性与测试结果比较兼容性结果

#### Scenario: 编辑 Profile 时不更新密钥

- **WHEN** 管理员编辑 Profile 但不填写 API key
- **THEN** 系统保留服务端已保存的 API key 且不在页面展示其明文

### Requirement: 管理员绑定测试结果比较模型

系统 SHALL 允许超级管理员将一个已启用的模型 Profile 绑定至 `TEST_LOG_COMPARE` 阶段，并显示该绑定的可执行状态。

#### Scenario: 保存有效阶段绑定

- **WHEN** 管理员选择已启用的 Profile 并保存测试结果比较阶段绑定
- **THEN** 后续测试结果比较任务使用该 Profile 的模型配置

#### Scenario: 配置不完整或不兼容

- **WHEN** 当前阶段未绑定 Profile、绑定的 Profile 被停用，或最近测试显示其不兼容
- **THEN** 系统显示不可用原因和下一步配置指引
