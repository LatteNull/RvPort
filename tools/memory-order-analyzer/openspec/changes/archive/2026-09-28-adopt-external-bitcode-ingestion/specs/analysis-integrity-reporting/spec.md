## MODIFIED Requirements

### Requirement: Separate infrastructure completion from safety evaluation
既有 RunReport SHALL 继续独立表达 build_status、ir_status、source_mapping、scope_status 和各阶段执行状态；外部 ingestion SHALL 使用独立 `ExternalBitcodeIngestionReport` 表达 upstream/ingestion/fact/scope 完整性，不向 RunReport v2 静默加字段。两类基础设施报告均 SHALL 保存缺口原因，并在未执行风险规则时声明 semantic_analysis=not_run、safety=not_evaluated、findings=null，不输出“已确认安全”或用空 finding 暗示已完成风险扫描。

#### Scenario: All requested external BC files are processed successfully
- **WHEN** 所有 bundle 计划 BC 完成内容、parse/verify、facts 和 scope 校验
- **THEN** ingestion 报告对应基础设施阶段完成，但并发安全仍为 not_evaluated，既有 RunReport schema 不变

#### Scenario: A module lacks debug information
- **WHEN** IR 读取成功但无源码定位信息
- **THEN** 分别报告 IR 成功和 source mapping unavailable/partial，不将映射失败掩盖为全阶段完整

### Requirement: Account for the full planned input set
外部 ingestion 报告 SHALL 以 bundle records/scopes 为分母记录 planned、produced、missing、upstream-failed、hash/format/parse/verify、published、facts、source binding、scope、cache、未知调用及可定位事件比例，并说明每项分母。失败、不支持或未产出的 TU/artifact SHALL 不从计划集合消失；分母为零的比例 SHALL 为 null 而非 100%。既有单文件 import 和历史 RunReport 保持原计数语义，但不得冒充完整 bundle。

#### Scenario: Only part of the external build is available
- **WHEN** bundle 计划 10 个 TU，仅 8 个 produced 且有效
- **THEN** 报告计划 10、可用 8 及另 2 个 missing/failed 原因，ingestion 为 partial，不以成功集合重算完整率

#### Scenario: There are no planned external artifacts
- **WHEN** bundle 没有合法计划 record
- **THEN** 请求失败、比例为 null 且不发布空 scope或显示全程序无风险

### Requirement: Return exit statuses consistent with requested operations
CLI SHALL 使用退出码 0 表示请求的基础设施操作完成且无该操作完整性缺口，2 表示有可用结果但部分失败/降级，1 表示非法请求、全失败或不可继续；SHALL 尽力为非零结果生成结构合法的诊断报告。`ingest-bc-bundle` SHALL 按完整 bundle 分母应用 0/2/1；`import-bc`、`index` 及既有分析命令保持各自既有语义。已移除的 `collect`/`link` MUST 作为未知命令失败，不得以兼容别名继续执行 compiler/linker。

#### Scenario: One record fails while others produce usable facts
- **WHEN** ingestion 中部分外部 record 失败而其余 record 产生可用事实
- **THEN** 保存成功事实和失败诊断，退出 2，不仅透传最后一个 worker 的状态

#### Scenario: A caller invokes a removed producer command
- **WHEN** 用户调用生产 CLI 的 `collect` 或 `link`
- **THEN** 参数解析失败并返回结构化请求错误，不执行 compile database、compiler 或 llvm-link

### Requirement: Isolate extractor generations across artifact paths
系统 SHALL 以一致的 facts/extractor/policy 元数据驱动 worker 协议检查与 `ingest-bc-bundle`、`import-bc`、`index` 身份。旧 worker 或不同 policy SHALL 不因 LLVM 版本相同而被接受。版本变化 SHALL 隔离缓存与输出；迁移 SHALL 通过对不变外部 BC 重新提取 facts 完成，不覆盖旧产物、不抬高 provenance、不丢失已有 lineage。重键后的 record/scope 成员 SHALL 通过显式映射供用户更新，不能自动猜目标范围。

#### Scenario: A worker has the right LLVM but the wrong protocol
- **WHEN** worker 使用锁定 LLVM 却不支持 ModuleFacts v2 或预期 extractor/policy
- **THEN** reader readiness 与实际 ingestion 均报告协议不兼容，不发布伪装新版本事实

#### Scenario: External bitcode is re-extracted under a new protocol
- **WHEN** 相同 bundle/BC 曾由旧 extractor 生成 facts
- **THEN** 新 ingestion 使用不同内部 artifact/facts identity 且不计为旧命中，旧文件不删除并保留 record/TU/profile lineage

#### Scenario: A bare import changes extractor generation
- **WHEN** 无 bundle 的单文件 import 在新 extractor 下运行
- **THEN** 身份包含当前 facts/extractor/policy，provenance/scope 仍为 unknown，重复导入不无限增长 lineage

### Requirement: Isolate P4 risk exit semantics from existing commands
`detect-publication-risks` SHALL 使用 0 表示完整且无 finding、3 表示完整且有 finding、2 表示有可用结果但 partial/unknown/unsupported、1 表示非法或不可继续；partial SHALL 优先于 finding 返回 2。`ingest-bc-bundle`、`import-bc`、`index`、`summarize` 和 `model-threads` 的 0/2/1 语义 MUST 保持与其职责一致，ingestion 状态不得改写 P4 verdict，P4 也不得把输入成功解释为安全。

#### Scenario: Existing P3 analysis completes after external ingestion
- **WHEN** 用户在已导入 artifact store 上只运行 `model-threads`
- **THEN** P3 仍按原 0/2/1 规则退出并保持 findings=null，不因 ingestion 或 P4 可用而运行风险规则

## ADDED Requirements

### Requirement: Prohibit analyzer-side bitcode production in production operations
生产 `memory_order_analyzer` CLI、ingestion driver 和 P1–A6/R1–R3 runner MUST NOT 执行编译器、dependency generator、assembler、`llvm-link`、configure/build/install、网络、SSH 或被分析程序，也 MUST NOT 写出经过转换的新 BC。允许的外部进程仅限经协议握手的只读 reader/source analysis worker；测试 fixture 的预生成命令 SHALL 在调用分析器之前执行并明确隔离。

#### Scenario: Ingestion is traced in a compiler-equipped environment
- **WHEN** 测试环境安装了 clang、gcc、llvm-link 和 CMake，并记录 ingestion/analysis 发起的全部 argv
- **THEN** 只观察到 reader/source worker 请求，不出现 compiler/linker/build/target execution

#### Scenario: A malformed BC might be repairable by a tool
- **WHEN** 输入不是受支持 raw LLVM BC或 verify 失败
- **THEN** 系统报告失败，不调用 clang、llvm-dis、llvm-as、objcopy 或 llvm-link 修复
