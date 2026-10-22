## Purpose

定义超级管理员在受保护管理中心维护平台账号、SMTP 邮件服务和 Worker 实例时的前端能力、权限边界与安全约束。模型配置由 model-configuration-center 定义。

## Requirements

### Requirement: Admin-center authorization and navigation

The frontend SHALL provide an `/admin/*` management module that is visible and accessible only to users with `isSuperAdmin: true`.

#### Scenario: Administrator enters the management center

- **WHEN** a super administrator selects “管理中心”
- **THEN** the frontend SHALL navigate to `/admin/users` and provide navigation to user management, model configuration, mail configuration and Worker management

#### Scenario: Non-administrator accesses an admin route

- **WHEN** a user without super-administrator permission opens an `/admin/*` route
- **THEN** the route guard SHALL redirect the user to `/403`

### Requirement: Administrator user management

The frontend SHALL allow a super administrator to list, filter, create, update, disable, reset passwords for, and resend invitations to ordinary users through the existing admin user APIs.

#### Scenario: Administrator manages a user

- **WHEN** an administrator submits a valid user-management action
- **THEN** the frontend SHALL call the corresponding `/api/admin/users` endpoint and refresh the displayed user list after success

### Requirement: Administrator mail configuration

The frontend SHALL allow a super administrator to view, update, and test the SMTP mail configuration without exposing a configured password value. 邮箱配置 SHALL 区分初次加载失败与已有数据的后台刷新失败，并提供可恢复入口；后台刷新成功或失败 SHALL NOT 覆盖当前编辑草稿。

#### Scenario: Administrator saves mail configuration

- **WHEN** an administrator submits valid mail settings
- **THEN** the frontend SHALL update `/api/admin/configs/mail`, show the returned password-configured state, and SHALL NOT populate the password field from the response

#### Scenario: 邮箱配置首次加载失败

- **WHEN** 邮箱配置请求失败且没有可展示数据
- **THEN** 页面 SHALL 展示明确的失败说明与重试入口，而不是只保留页头或持续显示加载
- **AND** 重试成功 SHALL 恢复配置内容与既有编辑、测试入口

#### Scenario: 邮箱配置后台刷新失败

- **WHEN** 已有邮箱配置内容后刷新失败
- **THEN** 页面 SHALL 保留已展示内容和未提交输入，说明刷新失败并提供重试
- **AND** 业务提交弹窗 SHALL 遵循 common-ui 的提交生命周期规则

#### Scenario: 邮箱配置后台刷新成功时正在编辑

- **WHEN** 用户正在编辑邮箱配置，后台读取成功并返回更新的配置
- **THEN** 页面 SHALL 更新查询数据与非编辑展示，保留当前表单全部未提交输入，包括本次输入的 SMTP 密码
- **AND** 页面 SHALL 仅在进入编辑、明确取消或所属保存成功时初始化或重置编辑表单，已保存的 SMTP 密码仍 SHALL NOT 回显

### Requirement: Administrator Worker management

前端 SHALL 为超级管理员提供独立 Worker 管理页面，使用后端 Worker 管理 API 展示自动接入实例、运行状态、并发状态、最近心跳和当前运行任务，并允许设置单实例任务消费并发限制。

#### Scenario: Administrator inspects Worker instances

- **WHEN** 超级管理员进入 `/admin/workers`
- **THEN** 前端 SHALL 展示 Worker 列表并支持按实例、主机、在线状态和运行任务筛选
- **AND** 列表 SHALL 区分期望并发、实际并发和运行任务数量
- **AND** 管理员 SHALL 能查看单个 Worker 的完整信息与当前运行任务

#### Scenario: Administrator updates Worker concurrency

- **WHEN** 超级管理员为 Worker 提交非负整数 `concurrencyLimit`
- **THEN** 前端 SHALL 调用对应 Worker 并发更新 API
- **AND** 成功后 SHALL 刷新列表和详情中的并发状态
- **AND** 当值为 `0` 时 SHALL 说明 Worker 将暂停接收新任务，但不会取消正在运行的任务

#### Scenario: Administrator refreshes Worker state

- **WHEN** 超级管理员需要获取最新心跳或负载状态
- **THEN** 前端 SHALL 提供显式刷新入口
- **AND** 页面 SHALL NOT 为此新增后台轮询

### Requirement: 活动模型探测的读取恢复

已知尚未完成的模型探测 SHALL 在首次详情读取失败后继续观察，不得将无响应数据视为终态。

#### Scenario: 首次读取暂时失败

- **WHEN** Profile 带有活动探测任务，首次详情请求失败且尚无详情缓存
- **THEN** 页面 SHALL 继续按既有观察周期读取该任务，直到获得终态或该订阅离开生命周期
