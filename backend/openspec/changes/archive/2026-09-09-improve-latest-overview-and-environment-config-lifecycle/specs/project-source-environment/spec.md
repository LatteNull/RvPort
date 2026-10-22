## ADDED Requirements

### Requirement: 环境有效配置变更必须使当前验证事实失效
环境管理 SHALL 区分有效运行配置和纯展示字段，并 SHALL 在有效运行配置变化后使旧连接测试与采集事实失效。

#### Scenario: 修改环境有效配置
- **WHEN** 用户修改环境的角色、架构、主机、SSH 端口、用户名、凭据、跳板机、工作目录或启用状态
- **THEN** 后端 SHALL 递增该环境的 `configVersion`
- **AND** 后端 SHALL 将当前状态重置为 `UNKNOWN`
- **AND** 后端 SHALL 清空当前连接时间和当前采集时间

#### Scenario: 修改环境展示字段
- **WHEN** 用户只修改环境名称等不影响远程执行的展示字段
- **THEN** 后端 SHALL 保持 `configVersion` 不变
- **AND** 当前连接测试、采集快照和环境状态 SHALL 保持有效

#### Scenario: 环境详情只返回当前版本基础信息
- **WHEN** 前端查询环境详情
- **THEN** 后端 SHALL 只使用与环境当前 `configVersion` 匹配的成功快照生成基础信息
- **AND** 仅存在旧配置版本快照时基础信息 SHALL 为空或明确标识未采集
- **AND** 后端 MUST NOT 把旧版本操作系统、软件包或连接信息作为当前事实返回

#### Scenario: 凭据变更传播到引用环境
- **WHEN** 管理员修改被一个或多个环境引用的凭据内容
- **THEN** 后端 SHALL 使所有受影响环境的有效配置版本递增
- **AND** 后端 SHALL 使这些环境的当前连接测试与采集事实失效

#### Scenario: 跳板机变更传播到下游环境
- **WHEN** 用户修改被其他环境选为跳板机的环境有效配置
- **THEN** 后端 SHALL 使直接依赖该跳板机的环境配置版本递增
- **AND** 后端 SHALL 对这些环境应用相同的状态和采集失效规则
