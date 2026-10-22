## ADDED Requirements

### Requirement: 构建验证列表必须默认收敛到当前上下文
构建验证列表 API SHALL 默认返回当前 active source revision 和当前运行环境配置版本下的构建记录，并 SHALL 支持显式查看历史记录。

#### Scenario: 默认查询当前构建记录
- **WHEN** 用户调用 `GET /api/projects/{projectId}/builds` 且未指定 `sourceRevisionId`、`environmentConfigVersion` 或 `includeStale`
- **THEN** 后端 SHALL 使用项目 active source revision 作为默认源码版本
- **AND** 后端 SHALL 使用当前项目运行环境配置版本作为默认环境版本
- **AND** 响应 MUST NOT 混入旧源码版本或旧运行环境配置版本的构建记录

#### Scenario: 显式查看历史构建记录
- **WHEN** 用户调用构建列表 API 并显式提交历史 `sourceRevisionId`、历史 `environmentConfigVersion` 或 `includeStale=true`
- **THEN** 后端 SHALL 按请求参数返回匹配历史记录
- **AND** 响应 SHALL 标明每条记录是否属于当前源码版本和当前运行环境配置版本

#### Scenario: 构建记录返回陈旧原因
- **WHEN** 构建记录不属于当前 active source revision 或当前运行环境配置版本
- **THEN** 响应 SHALL 返回 `currentSourceRevision=false` 或 `currentRuntimeEnvironment=false`
- **AND** 响应 SHALL 返回 `staleReasons`，取值至少支持 `SOURCE_REVISION_CHANGED` 和 `RUNTIME_ENVIRONMENT_CHANGED`
