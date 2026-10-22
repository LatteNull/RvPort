## MODIFIED Requirements

### Requirement: 构建验证查询必须支持分页排序过滤
后端 SHALL 提供构建验证列表、详情和取消 API，并 SHALL 对所有访问执行项目权限校验。构建详情 SHALL 返回可用于前端回填的完整构建脚本；构建列表 SHALL 保持轻量并使用摘要字段展示脚本信息。

#### Scenario: 查询构建列表
- **WHEN** 用户调用 `GET /api/projects/{projectId}/builds`
- **THEN** 后端 SHALL 返回分页构建运行列表
- **AND** 列表 SHALL 支持按 `sourceRevisionId`、`environmentId`、`status` 和创建时间范围过滤
- **AND** 列表 SHALL 支持按 `createdAt`、`startedAt`、`finishedAt`、`status` 和 `environmentId` 排序
- **AND** 列表响应 SHALL 返回构建脚本摘要字段 `commandSummary`
- **AND** 列表响应 MUST NOT 批量返回完整构建脚本明文用于回填

#### Scenario: 查询构建详情
- **WHEN** 用户调用 `GET /api/builds/{buildId}`
- **THEN** 后端 SHALL 根据构建所属项目执行项目访问守卫
- **AND** 响应 SHALL 包含构建运行 ID、项目 ID、任务 ID、源码版本摘要、环境摘要、源码部署 ID、状态、退出码、失败分类、merged/stdout/stderr 日志引用和时间字段
- **AND** 响应 SHALL 在 `command` 中返回该构建运行提交的完整构建脚本，用于前端回填
- **AND** 响应 SHALL 在 `commandSummary` 中返回脱敏脚本摘要
- **AND** 响应 MUST NOT 返回明文凭据或服务器本机路径

#### Scenario: 构建详情脚本 payload 缺失或校验失败
- **WHEN** 用户查询构建详情
- **AND** 对应构建运行的脚本 payload 不存在、无法解密或 SHA-256 校验失败
- **THEN** 后端 SHALL 返回安全错误
- **AND** 后端 MUST NOT 使用 `build_runs.command` 摘要冒充完整构建脚本
- **AND** 错误响应 MUST NOT 暴露脚本内容、密钥信息或服务器本机路径

#### Scenario: 取消构建
- **WHEN** 用户调用 `POST /api/builds/{buildId}/cancel`
- **THEN** 后端 SHALL 根据构建所属项目执行项目访问守卫
- **AND** 后端 SHALL 复用任务取消服务取消对应任务
- **AND** `build_runs.status` SHALL 最终与任务终态一致

#### Scenario: 无权限访问构建
- **WHEN** 无项目权限用户查询或取消构建运行
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露构建运行是否存在

### Requirement: 构建运行必须提供 latest
构建运行领域 SHALL 提供当前 Context 下的 latest 接口，支持区分 x86 构建和双环境构建验证。latest 返回当前记录时 SHALL 提供可回填构建脚本和脚本摘要。

#### Scenario: 查询 x86 构建 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/builds/latest?mode=SOURCE_ONLY`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新 source-only 构建运行
- **AND** `result` SHALL 包含构建环境、部署记录、构建状态、日志入口和 artifact 摘要
- **AND** 当 `freshness=CURRENT` 且 `result` 存在时，`result.command` SHALL 返回完整构建脚本用于前端回填
- **AND** 当 `result` 存在时，`result.commandSummary` SHALL 返回脱敏脚本摘要

#### Scenario: 查询构建验证 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/builds/latest?mode=VALIDATION`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新构建验证批次或运行摘要
- **AND** `result` SHALL 包含 x86 与 RISC-V 构建运行摘要
- **AND** 当 `freshness=CURRENT` 且 `result` 存在时，`result.command` SHALL 返回完整构建脚本用于前端回填
- **AND** 当 `result` 存在时，`result.commandSummary` SHALL 返回脱敏脚本摘要

#### Scenario: latest 脚本 payload 缺失或校验失败
- **WHEN** 用户查询构建 latest
- **AND** latest 选中的构建运行脚本 payload 不存在、无法解密或 SHA-256 校验失败
- **THEN** 后端 SHALL 返回安全错误
- **AND** 后端 MUST NOT 使用 `build_runs.command` 摘要冒充完整构建脚本

#### Scenario: 构建 latest 不跳过失败
- **WHEN** 当前 Context 下最新构建运行失败
- **THEN** latest SHALL 返回失败 execution
- **AND** 后端 MUST NOT 回退到更早成功构建
