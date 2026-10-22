## ADDED Requirements

### Requirement: 项目 API 必须暴露源码来源锁定摘要
项目 API SHALL 返回项目源码来源锁定状态，使前端能够判断当前项目应使用压缩包上传还是 Git 同步入口。

#### Scenario: 项目详情返回源码来源锁定
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}`
- **THEN** 响应 SHALL 包含 `sourceInputType`
- **AND** `sourceInputType` SHALL 为 `ARCHIVE`、`GIT` 或 `null`
- **AND** 后端 SHALL 继续执行项目访问权限校验

#### Scenario: 项目列表和概览返回源码来源锁定
- **WHEN** 已登录用户调用 `GET /api/projects` 或 `GET /api/projects/{projectId}/overview`
- **THEN** 响应 SHALL 包含项目源码来源锁定摘要
- **AND** 未成功入库源码的项目 SHALL 返回 `sourceInputType=null`

### Requirement: 源码 API 必须执行源码来源锁定校验
源码上传和 Git 同步 API SHALL 在创建源码版本或任务前校验项目源码来源锁定状态。

#### Scenario: 锁定 ARCHIVE 后拒绝 Git 同步
- **WHEN** 项目 `sourceInputType=ARCHIVE`
- **AND** 用户调用 `POST /api/projects/{projectId}/sources/git-sync`
- **THEN** API SHALL 返回 `SOURCE_INPUT_TYPE_LOCKED`
- **AND** 响应 SHALL 使用统一错误格式
- **AND** 后端 MUST NOT 创建任务或投递队列消息

#### Scenario: 锁定 GIT 后拒绝压缩包上传
- **WHEN** 项目 `sourceInputType=GIT`
- **AND** 用户调用 `POST /api/projects/{projectId}/sources/archive`
- **THEN** API SHALL 返回 `SOURCE_INPUT_TYPE_LOCKED`
- **AND** 响应 SHALL 使用统一错误格式
- **AND** 后端 MUST NOT 保存源码包或创建源码版本

#### Scenario: 压缩包上传成功响应
- **WHEN** 用户上传有效源码压缩包且后端完成保存、解包和源码版本创建
- **THEN** API SHALL 返回源码版本摘要和导入记录摘要
- **AND** 源码版本摘要 SHALL 包含 `revisionType=ARCHIVE`
- **AND** 响应 MUST NOT 返回 `archivePath`、`workingCopyPath` 或服务器真实路径

#### Scenario: 压缩包上传失败响应
- **WHEN** 压缩包格式不支持、路径不安全、内容为空或源码结构无效
- **THEN** API SHALL 返回明确错误码
- **AND** 后端 MUST NOT 返回服务器临时路径、目标目录或内部异常堆栈

#### Scenario: Git 同步成功后响应源码来源
- **WHEN** Git 同步任务成功完成
- **THEN** 后续项目详情、项目列表和项目概览 SHALL 返回 `sourceInputType=GIT`
- **AND** 源码列表 SHALL 返回新的 `revisionType=GIT` 源码版本摘要
