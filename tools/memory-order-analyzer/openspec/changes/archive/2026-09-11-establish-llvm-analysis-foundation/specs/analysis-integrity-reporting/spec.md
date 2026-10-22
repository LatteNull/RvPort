## ADDED Requirements

### Requirement: Publish versioned and deterministic artifact contracts

系统 SHALL 为 manifest、facts、scope/index 和 RunReport 提供可校验的版本化 schema、显式对象引用及确定性排序；消费者 SHALL 拒绝不支持的主 schema 版本。相同输入的语义事实和引用 SHALL 稳定，时间戳等运行字段 SHALL 与语义身份分离；机器输出不得混入日志文本。

#### Scenario: A consumer receives a future schema version

- **WHEN** worker 或编排层输入不支持的主 schema 版本
- **THEN** 输出版本不兼容诊断而非按旧字段静默解析

#### Scenario: Repeat fact extraction for the same artifact

- **WHEN** 相同 BC、extractor 版本和配置被重复读取
- **THEN** 事件/符号身份、语义内容和排序一致，运行时间等字段不改变 artifact 引用

### Requirement: Separate infrastructure completion from safety evaluation

RunReport SHALL 独立表达 build_status、ir_status、source_mapping、scope_status 和各阶段执行状态，并保存缺口原因。本 change SHALL 始终声明 semantic_analysis=not_run、safety=not_evaluated、findings=null，不输出“已确认安全”或用空 finding 列表暗示已完成风险扫描。

#### Scenario: All requested BC files are processed successfully

- **WHEN** 所有计划 BC 编译和读取成功
- **THEN** 报告对应基础设施阶段完成，但并发分析仍为 not_run，安全性仍为 not_evaluated

#### Scenario: A module lacks debug information

- **WHEN** IR 读取成功但无源码定位信息
- **THEN** 分别报告 IR 成功和 source_mapping unavailable，不将映射失败掩盖为全阶段完整

### Requirement: Account for the full planned input set

报告 SHALL 记录原始编译记录、去重后的计划 TU、生成/读取/校验成功数、失败项、缓存命中、未知调用及可定位事件比例，并说明各计数分母。失败或不支持的 TU SHALL 不从计划集合消失；分母为零的比例 SHALL 为 null 而非 100%。

#### Scenario: Only part of the planned build succeeds

- **WHEN** 计划 10 个 TU，仅 8 个生成有效 BC
- **THEN** 报告计划 10、成功 8 及另 2 个失败原因，build_status 为 partial，不以成功集合重算为完整构建

#### Scenario: There are no planned translation units

- **WHEN** 编译数据库没有有效计划输入
- **THEN** 明确空输入或校验失败，比例不为 100%，不显示全程序无风险

### Requirement: Return exit statuses consistent with requested operations

CLI SHALL 使用退出码 0 表示请求的基础设施操作完成且无该操作完整性缺口，2 表示有可用结果但部分失败/降级，1 表示非法请求、全失败或不可继续；SHALL 尽力为非零结果生成结构合法的诊断报告。未请求的后续风险分析 SHALL 不被当作已执行；collect 未要求 scope 时可成功但仍报告 scope unknown。

#### Scenario: One worker fails while others produce usable facts

- **WHEN** collect 中部分 TU 失败而其余 TU 产生可用事实
- **THEN** 保存成功事实和失败诊断，退出 2，不仅透传最后一个子进程的 0

#### Scenario: Explicit link lacks a scope

- **WHEN** 用户请求 link 却没有提供必要的 scope
- **THEN** 拒绝请求并退出 1，不自动链接目录内所有 BC
