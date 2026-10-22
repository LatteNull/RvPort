## ADDED Requirements

### Requirement: 人工修复节点作为源码更新入口
系统 SHALL 将人工修复节点作为轻量过渡页，展示当前迁移输入摘要、最近源码版本和线下修复提示，并提供跳转源码管理的主操作。

#### Scenario: 查看人工修复页
- **WHEN** 用户打开某项目的人工修复节点
- **THEN** 系统 MUST 返回当前迁移输入摘要、最近 active 源码版本摘要和线下修复提示
- **AND** 页面 MUST 提供 `更新源码` 主操作

#### Scenario: 从人工修复跳转源码管理
- **WHEN** 用户在人工修复页点击 `更新源码`
- **THEN** 前端 MUST 跳转到同项目源码管理页
- **AND** 源码管理页 MUST 支持继续使用已锁定的源码来源上传源码包或执行 Git 更新

#### Scenario: 人工修复页不提供在线修改
- **WHEN** 用户查看人工修复页
- **THEN** 系统 MUST NOT 提供在线代码编辑、自动 patch 应用或一键修复操作

### Requirement: 源码更新后创建新源码版本
系统 SHALL 在源码包上传或 Git 同步成功后创建新的 `source_revisions` 记录，并在请求要求激活时将其设为项目 active 源码版本。

#### Scenario: 上传线下修复后的源码包
- **WHEN** 用户在源码管理页上传合法源码压缩包且 `activate=true`
- **THEN** 系统 MUST 创建新的源码版本
- **AND** 系统 MUST 将该源码版本设为项目 active 版本

#### Scenario: Git 更新线下修复后的代码
- **WHEN** 用户在源码管理页执行 Git 同步且同步成功
- **THEN** 系统 MUST 创建新的源码版本
- **AND** 响应 MUST 返回新源码版本摘要

### Requirement: latest compare API
系统 SHALL 提供项目级 latest compare API，由后端基于项目源码版本关系选择当前版本和上一版。

#### Scenario: 获取 latest compare
- **WHEN** 用户调用 `GET /api/projects/{projectId}/source/compare/latest`
- **THEN** 系统 MUST 校验当前用户对项目有访问权限
- **AND** 系统 MUST 使用项目 active 源码版本作为 `currentRevision`
- **AND** 系统 MUST 使用同项目中早于当前版本的最近成功源码版本作为 `previousRevision`

#### Scenario: 只有一个源码版本
- **WHEN** 项目只有一个可用源码版本
- **THEN** latest compare 响应 MUST 返回 `previousRevision=null`
- **AND** 响应 MUST 返回 `emptyReason=NO_PREVIOUS_REVISION`
- **AND** 响应 MUST 返回空差异列表

#### Scenario: 比较结果已生成
- **WHEN** 当前版本和上一版存在已完成的复检记录
- **THEN** latest compare 响应 MUST 返回复检状态、差异摘要和分页差异项入口信息

#### Scenario: 比较结果尚未生成
- **WHEN** 当前版本和上一版存在但没有可用复检记录
- **THEN** latest compare 响应 MUST 返回 `status=NOT_STARTED`
- **AND** 响应 MUST 包含 current/previous 源码版本摘要

#### Scenario: 比较任务运行中
- **WHEN** 当前版本和上一版的复检任务正在运行
- **THEN** latest compare 响应 MUST 返回 `status=RUNNING`
- **AND** 响应 MUST 返回关联任务 ID，供前端结合 SSE 展示进度

#### Scenario: 越权访问 latest compare
- **WHEN** 用户访问无权限项目的 latest compare API
- **THEN** 系统 MUST 返回安全错误
- **AND** 响应 MUST NOT 暴露项目或源码版本是否存在

### Requirement: 代码比较页后端版本选择契约
系统 SHALL 提供 latest compare API 作为代码比较页主入口，避免要求前端主流程显式传入旧版本和新版本 ID。

#### Scenario: 源码更新后恢复代码比较状态
- **WHEN** 源码包上传或 Git 同步成功并创建新源码版本
- **THEN** latest compare API MUST 返回 current/previous 版本和比较状态
- **AND** 响应 MUST 允许前端进入代码比较页后恢复当前状态

#### Scenario: 刷新代码比较页
- **WHEN** 用户刷新代码比较页或更换浏览器重新进入
- **THEN** latest compare API MUST 能恢复当前项目最近比较状态
