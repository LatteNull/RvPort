## ADDED Requirements

### Requirement: 环境 API 必须返回环境检查产生的基础信息
环境列表、环境详情、环境快照和环境检查相关 API SHALL 能暴露环境检查生成的非敏感基础信息，供前端在不调用独立环境采集入口的情况下展示 OS、架构、包管理器和检查结果。

#### Scenario: 环境列表返回基础信息
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/environments`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 每个环境项 SHALL 返回最近一次成功环境检查或环境采集产生的基础信息摘要
- **AND** 基础信息摘要 SHALL 包含 OS、OS version、kernel、arch、package manager、基础工具摘要、最近成功检查时间和最近快照 ID
- **AND** 尚无成功环境检查或环境采集时，基础信息摘要 SHALL 返回 `null` 或空摘要
- **AND** 响应 MUST NOT 返回明文凭据、私钥、token、passphrase、完整 `raw_snapshot`、远程敏感路径或日志文件路径

#### Scenario: 环境详情返回基础信息
- **WHEN** 已登录用户调用 `GET /api/environments/{environmentId}`
- **THEN** 后端 SHALL 根据环境所属项目校验访问权限
- **AND** 响应 SHALL 返回该环境最近一次成功环境检查或环境采集产生的基础信息摘要
- **AND** 响应 SHALL 保留凭据遮蔽摘要和跳板机非敏感摘要
- **AND** 响应 MUST NOT 暴露完整快照原文或敏感运行输出

#### Scenario: 环境检查任务完成后可查询基础信息
- **WHEN** 已登录用户创建环境检查任务且任务成功完成
- **THEN** 后端 SHALL 允许后续通过环境列表、环境详情或环境快照 API 查询该次检查产生的基础信息
- **AND** 任务详情 MAY 返回检查任务摘要、状态、进度、错误摘要和关联环境引用
- **AND** 任务详情 MUST NOT 返回完整任务输入快照或明文凭据

#### Scenario: 环境检查失败不改变基础信息响应
- **WHEN** 最近一次环境检查失败
- **THEN** 环境列表和详情 MAY 返回失败后的连接状态
- **AND** 基础信息摘要 SHALL 继续来自上一轮成功检查或成功采集
- **AND** 后端 MUST NOT 用失败任务的空信息覆盖上一轮成功基础信息

### Requirement: 普通环境信息展示不依赖独立采集 API
后端 API SHALL 保持独立环境采集 API 的兼容性，但普通环境页面展示所需的基础信息 SHALL 由环境检查 API 产生。

#### Scenario: 环境检查覆盖普通展示需求
- **WHEN** 前端需要展示环境 OS、架构、包管理器、基础工具和工作目录检查结果
- **THEN** 前端 SHALL 能通过环境检查任务完成后的后端环境查询接口获取这些信息
- **AND** 后端 MUST NOT 要求前端额外调用 `POST /api/projects/{projectId}/environments/{environmentId}/collect` 才能获得普通展示所需基础信息

#### Scenario: 保留重型采集 API
- **WHEN** SBOM 分析、兼容流程或测试需要完整 package、library、native file、repo provide 或 ELF metadata
- **THEN** 后端 MAY 继续提供 `POST /api/projects/{projectId}/environments/{environmentId}/collect`
- **AND** 该 API SHALL 继续执行项目访问权限校验
- **AND** 该 API 的任务输入和响应 MUST NOT 暴露明文凭据或服务器敏感路径
