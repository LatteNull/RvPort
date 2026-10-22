## ADDED Requirements

### Requirement: 项目源码环境 API 必须执行项目访问守卫
项目、源码和环境 API SHALL 对项目级资源执行统一项目访问守卫，普通用户只能访问自己创建的项目资源，超级管理员可以访问任意未软删除项目资源。

#### Scenario: 查询和更新项目
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}`、`PATCH /api/projects/{projectId}` 或 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 无权限时 SHALL 返回与项目不存在一致的安全错误

#### Scenario: 查询项目列表
- **WHEN** 普通用户调用 `GET /api/projects`
- **THEN** 后端 SHALL 只返回当前用户创建的未软删除项目
- **AND** 后端 MUST NOT 返回其他用户创建的项目

#### Scenario: 超级管理员查询项目列表
- **WHEN** 超级管理员调用 `GET /api/projects`
- **THEN** 后端 SHALL 返回所有未软删除项目

#### Scenario: 访问源码 API
- **WHEN** 已登录用户调用源码列表、压缩包上传、Git 同步或源码版本切换 API
- **THEN** 后端 SHALL 校验当前用户有权访问 URL 中的项目
- **AND** 源码版本切换 SHALL 同时校验源码版本属于该项目
- **AND** 无权限时 SHALL 返回安全错误且 MUST NOT 暴露源码版本或服务器本机路径

#### Scenario: 访问环境 API
- **WHEN** 已登录用户调用环境列表、创建、详情、更新、禁用、快照、连接测试、环境检查、环境采集或脚本运行 API
- **THEN** 后端 SHALL 校验当前用户有权访问对应项目
- **AND** 对只包含 `environmentId` 的 API，后端 SHALL 根据环境所属项目执行访问守卫
- **AND** 无权限时 SHALL 返回安全错误且 MUST NOT 暴露环境主机、用户名、凭据摘要、跳板机摘要或快照内容

#### Scenario: 校验跳板机归属和访问权限
- **WHEN** 用户创建或更新环境并设置 `jumpHostEnvironmentId`
- **THEN** 后端 SHALL 验证跳板机属于同一项目
- **AND** 后端 SHALL 验证当前用户有权访问该项目
- **AND** 无权限时 SHALL 拒绝请求且 MUST NOT 暴露跳板机环境信息
