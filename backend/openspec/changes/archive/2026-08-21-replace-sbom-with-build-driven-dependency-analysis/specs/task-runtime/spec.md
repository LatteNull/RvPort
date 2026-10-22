## ADDED Requirements

### Requirement: 任务运行时必须支持依赖分析任务类型
任务运行时 SHALL 支持 `DEPENDENCY_ANALYSIS` 长任务类型，并 SHALL 保留 `SBOM_ANALYSIS` 作为 deprecated 历史任务类型。

#### Scenario: 创建依赖分析任务
- **WHEN** 依赖分析 API 创建任务
- **THEN** 任务运行时 SHALL 创建类型为 `DEPENDENCY_ANALYSIS` 的 `tasks` 记录
- **AND** 任务输入快照 SHALL 包含项目 ID、源码版本 ID、依赖分析运行 ID、source 构建运行 ID、target 环境 ID 和环境配置版本
- **AND** 任务输入快照 MUST NOT 包含完整构建日志、完整脚本、明文凭据或服务器真实路径

#### Scenario: Worker 执行依赖分析 handler
- **WHEN** worker 认领 `DEPENDENCY_ANALYSIS` 任务
- **THEN** worker SHALL 分发到依赖分析 handler
- **AND** handler SHALL 通过任务执行上下文更新进度、写入日志、登记可取消资源并写入终态

#### Scenario: 依赖分析事件
- **WHEN** 依赖分析任务进入 `QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 追加任务事件
- **AND** 项目级 SSE SHALL 只向有权访问该项目的连接推送事件

#### Scenario: SBOM 任务类型 deprecated
- **WHEN** 系统遇到历史 `SBOM_ANALYSIS` 任务
- **THEN** 任务运行时 SHALL 保留查询和历史状态展示能力
- **AND** 新迁移主流程 MUST NOT 默认创建 `SBOM_ANALYSIS` 任务
