## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: 活动模型探测的读取恢复

已知尚未完成的模型探测 SHALL 在首次详情读取失败后继续观察，不得将无响应数据视为终态。

#### Scenario: 首次读取暂时失败

- **WHEN** Profile 带有活动探测任务，首次详情请求失败且尚无详情缓存
- **THEN** 页面 SHALL 继续按既有观察周期读取该任务，直到获得终态或该订阅离开生命周期
