## ADDED Requirements

### Requirement: SBOM 分析必须使用项目当前运行双环境
SBOM 分析 SHALL 从项目运行环境配置读取源环境和目标环境，并 SHALL 使用该配置版本创建分析运行。

#### Scenario: 创建 SBOM 分析读取运行环境
- **WHEN** 用户创建 SBOM 分析任务
- **THEN** 后端 SHALL 读取项目当前运行环境配置
- **AND** 后端 SHALL 使用配置中的源环境和目标环境创建 `SBOM_ANALYSIS` 任务
- **AND** `sbom_runs` SHALL 保存源环境 ID、目标环境 ID 和环境配置版本

#### Scenario: 缺少双环境时拒绝 SBOM 分析
- **WHEN** 用户创建 SBOM 分析任务且项目运行环境配置不完整
- **THEN** 后端 SHALL 返回运行环境未配置完整错误
- **AND** 后端 MUST NOT 创建 `sbom_runs`、任务或队列消息

#### Scenario: 环境配置变更后 SBOM 结果过期
- **WHEN** 用户查询 SBOM 分析列表或详情
- **THEN** 响应 SHALL 标识该 SBOM 运行是否属于当前项目运行环境配置版本
- **AND** 非当前版本结果 SHALL 保留为历史记录但不得作为当前报告默认输入
