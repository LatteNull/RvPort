## Context

当前依赖分析已经从 source/x86 成功构建事实中提取依赖，并结合 target/RISC-V 环境采集结果生成逐条结果。结果中已经包含 `riskLevel`、`targetMatchStatus`、`sourceProviderPackage`、`sourceProviderVersion`、`targetProviderPackage`、`targetProviderVersion` 和 `providerVersionStatus` 等字段。

新的依赖自动修复能力只处理一个收敛场景：source 和 target 默认属于同一类发行版包生态，且依赖分析已经确认目标环境或目标软件源存在可安装包。用户在前端选择候选项后，后端在 target 环境中安装包，记录安装结果，并在修复后自动重新执行依赖分析。

## Goals / Non-Goals

**Goals:**

- 为依赖分析结果提供可分页、可过滤、可排序的自动修复候选项接口。
- 支持基于用户选择的候选项创建异步依赖修复任务。
- 在目标环境中受控安装软件包，并逐条记录安装计划和安装结果。
- 修复完成后自动刷新环境并重新创建依赖分析任务。
- 复用现有任务、日志、SSE、取消、SSH、项目权限和审计机制。
- 覆盖正常流程、异常流程和 edge case 的单元测试与 API E2E。

**Non-Goals:**

- 不做源码级自动修复。
- 不做跨发行版包名 alias 推断，例如 `glibc` 到 `libc6`。
- 不默认安装高风险依赖；高风险只展示可选候选项。
- 不处理无法在目标源中确认包名或版本的依赖。
- 不实现前端页面。

## Decisions

### 1. 自动修复作为独立任务，而不是依赖分析 handler 的内部步骤

依赖分析负责识别问题，自动修复负责改变目标环境。两者的副作用不同，必须有独立运行记录、任务状态和日志。

备选方案是把安装逻辑追加到依赖分析任务中，但这会让“分析”具有远端环境修改副作用，也会让失败状态难以解释。因此新增 `DEPENDENCY_AUTO_FIX` 任务类型。

### 2. 候选项从依赖分析结果实时派生

候选项不单独存表。候选项查询根据 `dependency_analysis_result_items` 现有字段派生 `defaultSelected`、`selectable`、`installPackageName`、`installVersionConstraint` 和 `reason`。

提交修复后，后端再把被选中的候选项快照写入 `dependency_auto_fix_items`。这样可以保证执行记录可审计，也避免候选缓存与分析结果不一致。

### 3. 中风险默认选中，高风险只展示不默认选中

中风险对应“源环境没有 owner package，但目标环境或目标源有可确认 provider package/version”的场景，自动安装目标包风险相对可控。

高风险对应“源环境有 owner package，但目标版本低于源版本或目标匹配存在较高风险”的场景。该类条目可以通过同包名和源主版本尝试匹配目标源，但不应默认选中。

### 4. 安装计划按包管理器适配

第一版优先支持 RPM 包生态：

- `dnf`
- `yum`

安装前先执行包管理器查询，确认候选包存在；安装时使用受控脚本执行，并记录实际安装命令摘要、exit code、stdout/stderr 日志和错误摘要。

后续可以扩展：

- `apt`
- `zypper`

### 5. 包名和版本必须做安全校验

所有来自数据库结果、前端选择或 evidence 的包名、版本约束都必须经过白名单校验后才能进入远端脚本：

- 包名允许字母、数字、点、下划线、加号、冒号、连字符。
- 版本允许字母、数字、点、下划线、加号、波浪号、冒号、连字符。
- 不允许空白、分号、反引号、管道、重定向、命令替换或换行。

远端执行应优先使用上传临时脚本或现有 SSH 执行封装中的安全 stdin 机制，执行完成后删除临时文件。

### 6. 修复后自动重跑依赖分析

如果至少一个条目安装成功或被确认已经满足，修复任务完成后应自动创建新的 `DEPENDENCY_ANALYSIS` 任务。新分析任务复用当前 active source revision、当前 project runtime environment 和当前环境配置版本。

如果所有条目均失败或不可安装，修复任务记录失败或部分失败结果，不自动重跑依赖分析。

### 7. 运行记录逐条落库

新增：

- `dependency_auto_fix_runs`
- `dependency_auto_fix_items`

`runs` 保存整体状态、关联分析 run、目标环境、源码版本、任务 ID、重跑分析 run/task、统计和 summary。

`items` 保存每个依赖结果项对应的安装计划、默认选择快照、安装状态、exit code、错误摘要和 evidence。

## Risks / Trade-offs

- [Risk] 目标环境被修改，且安装包可能引入额外依赖。
  Mitigation: 只对用户显式提交的 result item 执行安装；候选项必须来自已有依赖分析；记录完整任务日志和 item 结果。

- [Risk] 包管理器版本约束语法在不同发行版之间有差异。
  Mitigation: 第一版明确支持 `dnf/yum`；其他包管理器返回不支持错误或只做候选预览。

- [Risk] 高风险包使用源主版本匹配目标源可能找不到包。
  Mitigation: 高风险不默认选中；执行前查询目标源；失败时逐条标记为不可安装，不影响其他条目。

- [Risk] 依赖分析结果过期，安装计划基于旧环境或旧源码。
  Mitigation: 创建修复任务时校验当前 active source revision 和当前 environment config version；过期时要求重新跑依赖分析。

- [Risk] 安装命令注入。
  Mitigation: 包名、版本、包管理器参数全部做白名单校验和受控拼接；日志脱敏；任务输入不保存明文凭据。

- [Risk] 安装成功但重新分析失败。
  Mitigation: 自动修复运行保持 `PARTIALLY_SUCCEEDED` 或 `SUCCEEDED_WITH_REANALYSIS_FAILED` 这类可诊断状态，保留安装结果和重跑分析创建失败原因。
