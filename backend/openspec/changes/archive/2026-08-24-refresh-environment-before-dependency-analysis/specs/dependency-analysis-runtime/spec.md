## ADDED Requirements

### Requirement: 依赖分析执行前必须刷新环境快照
依赖分析运行时 SHALL 在每次执行分析前刷新当前 source/x86 和 target/RISC-V 环境采集结果，并 SHALL 使用本次刷新产生的成功快照进行依赖匹配。

#### Scenario: 分析前刷新 source 和 target 环境
- **WHEN** `DEPENDENCY_ANALYSIS` worker 开始处理依赖分析任务
- **THEN** worker SHALL 对 source/x86 构建环境执行环境采集
- **AND** worker SHALL 对 target/RISC-V 目标环境执行环境采集
- **AND** worker SHALL 使用本次采集产生的 source snapshot 和 target snapshot 读取环境组件
- **AND** worker MUST NOT 默认使用任务开始前已存在的旧成功快照进行依赖匹配

#### Scenario: 目标环境删除软件后重新分析
- **WHEN** target/RISC-V 环境在旧快照后删除了某个已安装工具或软件包
- **AND** 用户重新创建依赖分析任务
- **THEN** worker SHALL 重新采集 target/RISC-V 环境
- **AND** 依赖结果 MUST NOT 根据旧快照返回该工具或软件包为 `TARGET_INSTALLED`
- **AND** 如果目标软件源仍提供该工具或软件包，依赖结果 SHALL 返回 `REPO_AVAILABLE` 或等效软件源可用状态

#### Scenario: source 环境采集失败
- **WHEN** source/x86 环境采集失败、超时或返回不可解析结果
- **THEN** 依赖分析任务 SHALL 失败
- **AND** 依赖分析运行 SHALL 标记为 `FAILED`
- **AND** 错误摘要 SHALL 标明 source 环境刷新失败
- **AND** 后端 MUST NOT 使用旧 source snapshot 继续分析

#### Scenario: target 环境采集失败
- **WHEN** target/RISC-V 环境采集失败、超时或返回不可解析结果
- **THEN** 依赖分析任务 SHALL 失败
- **AND** 依赖分析运行 SHALL 标记为 `FAILED`
- **AND** 错误摘要 SHALL 标明 target 环境刷新失败
- **AND** 后端 MUST NOT 使用旧 target snapshot 继续分析

#### Scenario: 记录本次刷新快照
- **WHEN** 依赖分析任务成功完成
- **THEN** 依赖分析 JSON artifact SHALL 包含本次使用的 `sourceSnapshotId` 和 `targetSnapshotId`
- **AND** artifact SHALL 包含对应的 collected time 或等效采集时间
- **AND** 任务日志或运行 summary SHALL 能审计本次环境刷新已启用
