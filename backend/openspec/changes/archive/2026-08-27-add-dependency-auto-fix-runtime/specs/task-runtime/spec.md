## ADDED Requirements

### Requirement: 任务运行时必须支持依赖自动修复任务类型
任务运行时 SHALL 支持 `DEPENDENCY_AUTO_FIX` 长任务类型，并 SHALL 将其纳入现有 worker、日志、事件、SSE、取消和失败处理机制。

#### Scenario: 创建依赖自动修复任务
- **WHEN** 依赖自动修复 API 创建任务
- **THEN** 任务运行时 SHALL 创建类型为 `DEPENDENCY_AUTO_FIX` 的 `tasks` 记录
- **AND** 任务输入快照 SHALL 包含项目 ID、源源码版本 ID、原依赖分析运行 ID、自动修复运行 ID、目标环境 ID 和环境配置版本
- **AND** 任务输入快照 MUST NOT 包含明文凭据、完整安装脚本、完整 SSH 参数或服务器真实路径

#### Scenario: Worker 执行依赖自动修复 handler
- **WHEN** worker 认领 `DEPENDENCY_AUTO_FIX` 任务
- **THEN** worker SHALL 分发到依赖自动修复 handler
- **AND** handler SHALL 通过任务执行上下文更新进度、写入 stdout/stderr/merged 日志、登记可取消资源并写入终态

#### Scenario: 依赖自动修复事件
- **WHEN** 依赖自动修复任务进入 `QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **THEN** 任务运行时 SHALL 追加任务事件
- **AND** 项目级 SSE SHALL 只向有权访问该项目的连接推送事件

#### Scenario: 取消依赖自动修复任务
- **WHEN** `DEPENDENCY_AUTO_FIX` 任务被取消
- **THEN** worker SHALL 尝试终止当前远端安装命令或关闭 SSH session
- **AND** 自动修复运行和未完成条目 SHALL 更新为 `CANCELLED`
- **AND** 已经安装成功的软件包 MUST NOT 被自动卸载
