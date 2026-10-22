## MODIFIED Requirements

### Requirement: SSH runtime 必须统一环境采集和脚本执行记录语义
后端 SHALL 通过统一 Env Runner/SSH runtime 模型支撑环境检查、环境信息采集和远程脚本执行，并 SHALL 统一保存执行记录、日志和结构化结果。环境检查 SHALL 同时生成轻量环境基础信息，重型环境采集 SHALL 继续负责 SBOM 所需组件清单。

#### Scenario: 环境检查保存检查结果和基础快照
- **WHEN** worker 执行 `ENV_RUN_SCRIPT` 且 `scriptType` 为 `ENV_CHECK`
- **THEN** SSH runtime SHALL 根据输入检查项执行受控环境检查脚本
- **AND** 检查项 SHALL 支持 `CONNECTION`、`BASIC_TOOLS`、`WORKING_DIRECTORY`、`PERMISSIONS`
- **AND** 检查脚本 SHALL 同时采集 OS、OS version、kernel、arch、package manager、基础工具版本、远程用户和工作目录检查结果
- **AND** 后端 SHALL 将每个检查项的结果写入 `tool_runs.summary.checkResults`
- **AND** 后端 SHALL 保存 stdout/stderr 到任务日志
- **AND** 后端 SHALL 写入一条成功的轻量 `environment_snapshots` 记录
- **AND** `environment_snapshots.task_id` SHALL 指向当前任务
- **AND** `raw_snapshot` SHALL 标记该快照来自环境检查，并保存标准化后的非敏感检查结果、脚本版本和解析警告
- **AND** 环境检查 MUST NOT 写入 `environment_components`

#### Scenario: 环境检查失败不覆盖上一轮成功基础信息
- **WHEN** `ENV_CHECK` 连接、认证、脚本执行或解析失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 后端 SHALL 保存执行记录、stdout/stderr 日志和安全失败摘要
- **AND** 后端 MUST NOT 写入成功 `environment_snapshots`
- **AND** 后端 MUST NOT 删除或覆盖上一轮成功的环境基础快照
- **AND** 后端 MUST NOT 更新表示成功采集或成功检查的时间字段

#### Scenario: 环境采集保存环境快照
- **WHEN** worker 执行 `ENV_COLLECT`
- **THEN** SSH runtime SHALL 执行内置环境采集脚本
- **AND** 采集脚本 SHALL 采集 OS、kernel、arch、package manager、软件源摘要、已安装包摘要和基础工具版本
- **AND** 后端 SHALL 写入 `environment_snapshots` 记录
- **AND** `environment_snapshots.task_id` SHALL 指向当前任务
- **AND** `os_name`、`os_version`、`kernel_version`、`arch`、`package_manager` SHALL 来自采集输出
- **AND** `repo_summary` SHALL 保存软件源摘要 JSON
- **AND** `tool_versions` SHALL 保存基础工具版本 JSON
- **AND** `raw_snapshot` SHALL 保存标准化后的非敏感采集结果、脚本版本和解析警告
- **AND** 后端 MAY 写入 `environment_components` 保存系统包、库、工具和 native 文件摘要
- **AND** 后端 SHALL 更新 `environments.last_collected_at`

#### Scenario: 环境采集失败不覆盖上一轮成功结果
- **WHEN** `ENV_COLLECT` 连接、认证、脚本执行或解析失败
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 后端 SHALL 保存执行记录、stdout/stderr 日志和安全失败摘要
- **AND** 后端 MUST NOT 覆盖上一轮成功的 `environment_snapshots`
- **AND** 后端 MUST NOT 更新 `last_collected_at`

#### Scenario: 远程脚本执行保存执行记录
- **WHEN** worker 执行 `ENV_RUN_SCRIPT`
- **THEN** 后端 SHALL 写入 `tool_runs` 执行记录
- **AND** `tool_runs.summary` SHALL 保存脚本类型、工作目录检查结果、执行用户、安全命令摘要和耗时
- **AND** `tool_runs.exit_code` SHALL 保存远程脚本退出码
- **AND** 后端 SHALL 通过 `task_logs` 保存 stdout/stderr
- **AND** 后端 SHALL 写入审计日志记录执行人、环境、脚本类型、开始时间、结束时间、状态和退出码
- **AND** 执行记录、日志摘要和审计详情 MUST NOT 包含明文凭据、私钥、passphrase、token 或未经脱敏的敏感脚本内容

#### Scenario: 连接测试超时
- **WHEN** SSH 连接或探测命令超过配置的超时时间
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 任务错误摘要 SHALL 表示连接超时或命令超时
- **AND** SSH session 和跳板机 session SHALL 被关闭

#### Scenario: 单条长时间命令
- **WHEN** 后续任务通过 SSH runtime 执行单条长时间运行命令
- **THEN** SSH runtime SHALL 将该 SSH session 限定为服务当前命令
- **AND** SSH runtime SHALL 使用命令超时或任务超时控制最长运行时间
- **AND** SSH runtime MUST NOT 在命令完成后保留该 session 等待后续命令

## ADDED Requirements

### Requirement: 环境检查必须提供普通页面所需基础信息
后端 SHALL 将普通环境页面需要展示的基础信息纳入环境检查结果，避免普通页面依赖独立环境采集入口。

#### Scenario: 环境检查生成基础信息摘要
- **WHEN** 环境检查成功完成
- **THEN** 后端 SHALL 生成环境基础信息摘要
- **AND** 摘要 SHALL 至少包含 OS、OS version、kernel、arch、package manager、基础工具可用性、基础工具版本、远程用户、工作目录检查结果和权限检查结果
- **AND** 摘要 MUST NOT 包含明文凭据、私钥、token、passphrase、用户 home 敏感文件内容或服务器敏感路径

#### Scenario: 区分轻量检查和重型采集
- **WHEN** 后端保存环境检查产生的快照
- **THEN** 后端 SHALL 在快照原始摘要或等效字段中标记快照来源为轻量环境检查
- **AND** SBOM 分析 MUST NOT 将只有轻量检查来源的快照误判为完整组件清单
- **AND** 需要 package、library、native file、repo provide 或 ELF metadata 时，后端 SHALL 继续使用重型 `ENV_COLLECT` 快照

#### Scenario: 普通环境采集入口可被前端隐藏
- **WHEN** 前端不再暴露独立环境采集入口
- **THEN** 后端 SHALL 保持环境检查 API 可提供页面所需基础信息
- **AND** 后端 MAY 继续保留 `ENV_COLLECT` API 供兼容、测试或后端流程使用
