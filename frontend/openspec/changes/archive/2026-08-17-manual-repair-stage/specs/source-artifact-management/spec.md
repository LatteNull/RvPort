## MODIFIED Requirements

### Requirement: 源码管理阶段详情

项目流水线工作台 SHALL 在用户点击 `assets` 节点后打开专属源码管理 Drawer，并使用当前 `projectId` 请求阶段详情。

#### Scenario: 展示或缺失当前有效源码

- **WHEN** 阶段详情加载成功
- **THEN** Drawer SHALL 展示当前有效源码的来源、版本标识、来源元数据、版本说明和最近更新时间
- **AND** 当前有效源码 SHALL 仅来自压缩包或 Git 中的一种来源
- **WHEN** 不存在当前有效源码
- **THEN** 系统 SHALL 展示更新入口且禁止启动依赖该源码版本的扫描

#### Scenario: 源码更新子视图

- **WHEN** 用户选择上传压缩包或从 Git 更新
- **THEN** Drawer SHALL 切换至对应子视图，并隐藏关闭按钮且禁止遮罩或键盘关闭
- **WHEN** 用户取消更新
- **THEN** 未修改表单 SHALL 直接返回概览，存在未提交修改时 SHALL 要求确认放弃

### Requirement: 上传源码压缩包

系统 SHALL 允许用户以 `.zip` 压缩包和版本说明覆盖当前有效源码。

#### Scenario: 上传成功或失败

- **WHEN** 用户提交合法 `.zip` 文件和版本说明
- **THEN** 系统 SHALL 使用 `multipart/form-data` 上传并以服务端返回的源码制品替换当前版本
- **AND** SHALL 刷新源码管理详情和 workflow 状态
- **WHEN** 文件格式或服务端大小校验失败
- **THEN** 系统 SHALL 展示可理解原因并保留表单信息

#### Scenario: 上传后不自动启动扫描

- **WHEN** 用户确认上传成功
- **THEN** 系统 SHALL NOT 自动启动环境与依赖对比、知识库扫描或其他分析任务
- **AND** SHALL 提示用户在对应扫描节点手动创建或开始分析

### Requirement: 从 Git 更新源码

系统 SHALL 允许用户使用仓库地址、Ref 和可选用户名加 Access Token 覆盖当前有效源码。

#### Scenario: Git 更新与凭据保护

- **WHEN** Git 更新成功
- **THEN** 系统 SHALL 刷新 Git 来源、版本标识和更新时间
- **AND** SHALL NOT 自动启动环境与依赖对比、知识库扫描或其他分析任务
- **AND** 阶段详情、缓存、日志和 mock fixture SHALL NOT 返回或保存 Access Token
- **WHEN** 仓库、Ref 或认证失败
- **THEN** 系统 SHALL 保持在 Git 子视图、展示失败原因且不覆盖当前有效源码

## REMOVED Requirements

### Requirement: 启动源码分析

**Reason**: 当前业务流要求用户在环境与依赖对比、知识库扫描等阶段显式触发分析，源码更新不再隐式启动六项分析。

**Migration**: 移除源码管理中的“启动源码分析”确认入口；将用户引导至对应扫描节点的手动执行操作。
