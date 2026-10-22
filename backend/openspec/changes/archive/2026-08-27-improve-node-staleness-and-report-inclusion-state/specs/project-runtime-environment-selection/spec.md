## ADDED Requirements

### Requirement: 运行环境更新必须使依赖环境的当前节点结果失效
项目运行环境配置变更后，依赖远端环境的节点结果 SHALL 被视为非当前结果，但历史记录 SHALL 保留可查。

#### Scenario: 更新运行环境版本
- **WHEN** 用户更新项目当前 source/x86 或 target/RISC-V 运行环境
- **THEN** 后端 SHALL 递增项目运行环境配置版本
- **AND** 后续构建验证、源码部署、依赖分析和自动化测试 SHALL 使用新的运行环境配置版本

#### Scenario: 旧环境版本记录不再作为当前结果
- **WHEN** 节点记录保存的 `environmentConfigVersion` 小于当前项目运行环境配置版本
- **THEN** 当前节点列表默认 MUST NOT 返回该记录
- **AND** 该记录详情或历史列表 SHALL 标明 `currentRuntimeEnvironment=false`
- **AND** 该记录 SHALL 包含 `RUNTIME_ENVIRONMENT_CHANGED` 或等效陈旧原因

#### Scenario: 历史记录仍可查询
- **WHEN** 用户显式请求历史运行环境版本或设置 `includeStale=true`
- **THEN** 后端 SHALL 允许返回旧环境版本下的节点记录
- **AND** 后端 MUST 继续执行项目访问权限校验
