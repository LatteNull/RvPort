## ADDED Requirements

### Requirement: 源码制品管理阶段详情

项目流水线工作台 SHALL 在用户点击 `assets` 节点后打开专属源码制品管理 Drawer，并使用当前 `projectId` 请求该阶段详情。

#### Scenario: 展示当前有效源码

- **WHEN** `assets` 阶段详情加载成功
- **THEN** Drawer SHALL 展示当前有效源码的来源、版本标识、来源元数据、版本说明和最近更新时间
- **AND** 当前有效源码 SHALL 仅来自压缩包或 Git 中的一种来源

#### Scenario: 没有当前有效源码

- **WHEN** `assets` 阶段详情不包含当前有效源码
- **THEN** Drawer SHALL 展示明确空状态和更新源码的入口
- **AND** 系统 SHALL NOT 允许用户启动源码分析

#### Scenario: 打开源码更新子视图

- **WHEN** 用户在源码制品概览选择上传压缩包或从 Git 更新
- **THEN** Drawer SHALL 分别切换至 `upload` 或 `git` 子视图
- **AND** 子视图 SHALL 隐藏右上角关闭按钮，且遮罩点击或键盘操作 SHALL NOT 关闭当前 Drawer

#### Scenario: 返回源码制品概览

- **WHEN** 用户在源码更新子视图选择返回或取消
- **THEN** 系统 SHALL 返回源码制品概览
- **AND** 若表单存在未提交修改，系统 SHALL 要求用户确认放弃修改

### Requirement: 上传源码压缩包

系统 SHALL 允许用户以 `.zip` 压缩包覆盖项目当前有效源码。

#### Scenario: 提交源码压缩包

- **WHEN** 用户在上传子视图选择 `.zip` 文件并填写版本说明后提交
- **THEN** 系统 SHALL 使用 `multipart/form-data` 上传文件和版本说明
- **AND** 上传成功后 SHALL 使用服务端返回的源码制品替换当前有效源码并返回概览

#### Scenario: 非法压缩包

- **WHEN** 用户选择非 `.zip` 文件或服务端拒绝文件大小
- **THEN** 系统 SHALL 阻止或拒绝提交并展示可理解的失败原因
- **AND** 系统 SHALL 保留用户尚未重新选择的表单信息

#### Scenario: 上传后启动分析

- **WHEN** 用户选择“更新后启动源码分析”并确认上传
- **THEN** 系统 SHALL 在上传成功后请求启动源码分析
- **AND** 系统 SHALL 使用服务端返回的 workflow 状态更新画布

### Requirement: 从 Git 更新源码

系统 SHALL 允许用户从 Git 仓库获取源码并覆盖项目当前有效源码。

#### Scenario: 提交 Git 更新

- **WHEN** 用户提供仓库地址和 Ref 并提交 Git 更新
- **THEN** 系统 SHALL 请求服务端获取对应 Git 版本
- **AND** 更新成功后 SHALL 使用服务端返回的 Git 来源、版本标识和更新时间刷新源码制品概览

#### Scenario: 使用可选 Git 凭据

- **WHEN** 用户选择使用用户名加 Access Token 认证
- **THEN** 系统 SHALL 仅提交本次输入的用户名和 Access Token
- **AND** 阶段详情、缓存、日志和 mock fixture SHALL NOT 返回或保存 Access Token

#### Scenario: Git 更新失败

- **WHEN** 服务端无法访问仓库、Ref 不存在或认证失败
- **THEN** 系统 SHALL 保持在 Git 更新子视图并展示服务端返回的业务失败原因
- **AND** 系统 SHALL NOT 覆盖当前有效源码

### Requirement: 启动源码分析

系统 SHALL 在确认当前有效源码后固定启动全部六条源码分析支路。

#### Scenario: 确认启动全部源码分析

- **WHEN** 用户在源码制品概览确认启动源码分析
- **THEN** 系统 SHALL 请求推进 `assets` 阶段
- **AND** 确认提示 SHALL 明确说明将启动 SBOM、知识库、纯 AI、内存模型、浮点精度和对齐与布局优化六项分析

#### Scenario: 当前源码存在时启动成功

- **WHEN** 服务端确认存在当前有效源码并接受启动请求
- **THEN** 服务端返回的 workflow 状态 SHALL 将 `assets` 标记为完成
- **AND** `sbom`、`kb`、`ai-scan`、`memory`、`fp` 和 `alignment` SHALL 标记为运行中
- **AND** 系统 SHALL 刷新 workflow 状态并关闭源码制品管理 Drawer

#### Scenario: 启动条件不满足

- **WHEN** 用户尝试启动源码分析但不存在当前有效源码或服务端校验失败
- **THEN** 系统 SHALL 保持在源码制品概览
- **AND** 系统 SHALL 展示服务端返回的缺失条件或失败原因

### Requirement: 源码制品首期范围

源码制品管理首期 SHALL 仅维护当前有效源码，不提供二进制制品或版本历史能力。

#### Scenario: 更新当前版本

- **WHEN** 用户成功上传压缩包或从 Git 更新源码
- **THEN** 系统 SHALL 直接替换当前有效源码
- **AND** Drawer SHALL NOT 展示版本历史、回滚、二进制制品或源码对比基线入口
