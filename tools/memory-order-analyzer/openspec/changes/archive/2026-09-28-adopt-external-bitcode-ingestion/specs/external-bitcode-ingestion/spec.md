## ADDED Requirements

### Requirement: Define independent external bitcode ingestion contracts
系统 SHALL 定义严格版本化的 `ExternalBitcodeBundleManifest v1`、`ExternalBitcodeArtifactRecord v1` 和双语 `ExternalBitcodeIngestionReport v1`，包含 schema/producer/policy identity、canonical digest、显式记录引用、planned 分母、scope、预算和确定排序。未知字段、未来版本、悬空/替换引用、重复 record/TU/scope identity 及不一致 digest MUST 被拒绝；P1 `BCArtifact`、`ModuleFacts v2`、`RunReport v2` 及 P2–A6、R1–R3 既有协议 MUST 保持不变。

#### Scenario: A record is replaced after manifest creation
- **WHEN** manifest 引用的 record 文件内容与登记 digest 不同
- **THEN** ingestion 以请求错误拒绝该 bundle，不读取替换记录并伪造原 identity

#### Scenario: Existing downstream analysis consumes ingested facts
- **WHEN** 外部逐 TU BC 完成 ingestion 并生成既有 BCArtifact 与 ModuleFacts v2
- **THEN** P2–A6 和 R1–R3 通过原协议消费产物，不要求识别外部 manifest 私有字段

### Requirement: Account for every planned external artifact and scope member
bundle SHALL 显式登记全部 planned `ExternalBitcodeArtifactRecord`，每项状态为 `produced`、`missing` 或 `failed`；produced 项 SHALL 引用 BC 路径和 SHA-256，missing/failed 项 SHALL 保存受限中英文上游原因。scope SHALL 以 record identity 显式列出成员和闭合边界；没有 BC 的计划项 MUST 保留在分母，不得通过扫描现存文件缩小计划。

#### Scenario: The external build produced eight of ten planned TUs
- **WHEN** bundle 计划十个 TU，其中两个记录为 missing 或 failed
- **THEN** 报告 planned=10、可用=8 并保持 request partial，不把八个文件解释为完整 target

#### Scenario: A directory contains an unlisted bitcode file
- **WHEN** bundle root 中存在未被 record 引用的 `.bc`
- **THEN** ingestion 不自动纳入该文件，也不据此扩大任何 scope

### Requirement: Validate external paths and immutable contents before publication
ingestion SHALL 仅解析 bundle root 内由 record 显式引用的相对路径，拒绝绝对路径、路径穿越、解析后逃逸和不允许的符号链接目标。系统 SHALL 在读取前后校验非空文件和 SHA-256，使用受限流式 I/O 将完整产物复制或安全物化到分析器拥有的内容寻址 store，并在发布前再次核对 digest；输入变化时 MUST 不发布成功 artifact。

#### Scenario: A record escapes the bundle root
- **WHEN** record 使用 `../`、绝对路径或符号链接解析到 bundle root 外
- **THEN** 该请求被拒绝并输出 path-boundary 诊断，不读取边界外文件

#### Scenario: Bitcode changes while it is imported
- **WHEN** BC 在第一次 hash 与发布前校验之间变化
- **THEN** 记录为 inputs-changed，临时产物不发布且旧缓存不作为本次命中

### Requirement: Accept only supported raw LLVM bitcode and reader-compatible modules
produced 输入 SHALL 具有受支持的 raw LLVM bitcode magic，并由锁定 reader 执行 parse 和 verifier；实际模块 hash、target triple、DataLayout 与 record 声明 SHALL 一致。GCC LTO/GIMPLE、ELF/Mach-O/COFF 容器、截断/损坏 BC、reader 不兼容版本、定制未知 dialect 和伪扩展名 MUST 被拒绝，不得调用转换、反汇编、编译或链接工具修复。

#### Scenario: A GCC LTO object is named with a bc suffix
- **WHEN** 输入文件扩展名为 `.bc` 但内容是 GCC LTO/GIMPLE 或 ELF 容器
- **THEN** ingestion 输出 format-unsupported，不运行 GCC、objcopy 或 Clang 转换

#### Scenario: LLVM reader cannot parse a newer producer format
- **WHEN** record 声明的 producer 存在但锁定 reader 无法 parse/verify 实际 BC
- **THEN** 输出 reader-incompatible/verify-failed 并保留计划缺口，不因版本字符串相似而接受

### Requirement: Compute analyzer-owned artifact identities and preserve provenance boundaries
分析器 SHALL 根据 BC digest、规范化 record 语义字段、extractor/schema/policy 计算内部 artifact identity，不得接受外部提供的 `artifact_key`。host 路径、bundle 位置、时间戳、调度顺序和 cache hit MUST NOT 进入 semantic identity；相同字节对应不同 TU/profile 时 SHALL 保留不同 artifact identity。外部自述字段 SHALL 标明 attested，只有实际交叉验证字段可标为 verified，二者均不得描述为生产语义等价或安全证明。

#### Scenario: The same bytes are used by two configurations
- **WHEN** 两个 record 具有相同 BC hash 但 physical TU、语言 profile 或 target membership 不同
- **THEN** 生成两个可追溯 artifact identity，同时允许底层内容去重而不合并配置语义

#### Scenario: An external record supplies an internal-looking key
- **WHEN** producer 在未知字段或描述中提供 64 位 artifact key
- **THEN** schema 拒绝未知身份字段或将其仅作不可信描述，内部 key 仍由分析器计算

### Requirement: Distinguish producer host from analyzed target and ABI
record SHALL 分别记录 producer host 与声明 target，ingestion SHALL 从 BC 提取实际 target triple 和 DataLayout，并与 target/ABI/profile 交叉验证。x86 host 产生的交叉目标 BC MAY 按实际目标处理；x86_64 target BC MUST NOT 声称覆盖 ARM/RISC-V 配置。target、DataLayout、ABI、语言标准或 scope 成员冲突 MUST 失败或进入明确 partial/frontier，不得改写 module triple 绕过。

#### Scenario: An x86 host emits ARM-target bitcode
- **WHEN** producer host 是 x86_64，而 record 与实际 BC target 均为受支持 ARM triple
- **THEN** 报告分开展示 host/target，并按 ARM target identity 校验而不是按 host 拒绝

#### Scenario: X86-target evidence is requested as ARM evidence
- **WHEN** 实际 BC target 为 x86_64 而请求/scope 声明 ARM
- **THEN** ingestion 以 target-mismatch 拒绝，不把语言级原子事件推广为 ARM 构建覆盖

### Requirement: Prefer per-TU raw modules and bound linked or optimized evidence conservatively
`module_kind=translation-unit` 的逐 TU raw BC SHALL 是可形成完整 physical TU/source/scope lineage 的正式路径。显式声明的 linked/LTO LLVM BC 或缺少逐 TU identity 的模块 MAY 仅作为受限 IR-only 输入，且 MUST 产生非空 frontier、禁止伪造 TU/source 对齐或 closed scope；未声明 linked/LTO 特征 MUST 被拒绝。优化 profile SHALL 原样记录，优化消除的访问不得由零事件推断不存在。

#### Scenario: A declared linked module is imported
- **WHEN** record 明确声明 linked module 且实际 BC 可读
- **THEN** 系统可保留 IR 事实但报告 physical-TU-lineage-unknown，不能形成完整 AST overlay 或全 scope 无风险结论

#### Scenario: O2 bitcode contains no expected source load
- **WHEN** 外部 build-faithful BC 经优化不再包含某源码读取
- **THEN** 系统只报告现存 IR 与优化证据缺口，不重新编译也不把缺失事件当成反证

### Requirement: Publish existing artifacts and normalized scopes atomically
每个完整 record SHALL 通过既有 worker 生成结构合法的 `ModuleFacts v2`，并与内容寻址 `BCArtifact` 一同原子发布到标准 artifact store。bundle scope SHALL 在全部成员映射完成后生成使用内部 artifact key 的规范化 `ScopeManifest`；重复 lineage、target/DataLayout/ABI 冲突、缺失成员和开放边界 SHALL 保留为 scope 诊断。partial/failed record MUST NOT 伪造空 facts。

#### Scenario: One record fails while another succeeds
- **WHEN** 同 bundle 两个独立 record 中一个 verify 失败、另一个完整
- **THEN** 成功 record 的 artifact/facts 可发布，失败 record 留在报告分母，相关 scope 为 partial

#### Scenario: Scope members have incompatible layouts
- **WHEN** 一个外部 scope 引用 target 或 DataLayout 不一致的 produced records
- **THEN** 不生成可声明完整的 closed scope，报告冲突而不调用 llvm-link

### Requirement: Expose bounded offline ingestion and compatibility import CLI
系统 SHALL 提供 `ingest-bc-bundle --bundle --output --worker`，要求显式 bundle、全新输出目录和有界记录/字节/worker 时间/输出预算；命令 MUST NOT 执行 compiler、dependency generator、linker、configure/build、网络、SSH 或目标程序。`import-bc` SHALL 作为单文件兼容入口复用同一校验/发布 primitive，但缺少 bundle planned/scope/provenance 时 MUST 报告低完整性，不能替代正式 ingestion。

#### Scenario: Pure ingestion runs without compiler tools
- **WHEN** 环境只有兼容 reader/worker，没有 GCC、Clang driver、llvm-link 或 build system
- **THEN** 合法 bundle ingestion 完成，readiness 不因未请求工具缺失而失败

#### Scenario: A caller imports one bare BC file
- **WHEN** 使用 `import-bc` 且没有外部 record/manifest
- **THEN** 文件经内容和 reader 校验后可供 IR 检查，但 provenance/scope 为 unknown，结果不能声明 bundle 完整

### Requirement: Report ingestion completeness separately from safety
`ExternalBitcodeIngestionReport` SHALL 分别统计 planned、produced、missing、upstream-failed、hash-valid、format-valid、parsed、verified、published、facts-complete/partial/failed、source-bound、scope-resolved、cache-hit 和 frontier，并提供中英文 reason/limitation/suggestion。退出码 SHALL 为 0（ingestion 分母完整）、2（有可用产物但 partial/unknown）或 1（非法或无可用产物）；报告 MUST 固定 `safety=not_evaluated`、`findings=null`，不得把成功导入或零事件解释为无风险。

#### Scenario: All planned records ingest successfully
- **WHEN** 全部计划记录和 closed scope 完成 hash、parse、verify、facts 与映射校验
- **THEN** ingestion 可返回 0，但报告明确仅完成输入基础设施，不是并发安全证明

#### Scenario: A usable subset and an upstream failure coexist
- **WHEN** 至少一个 record 可发布且另一个计划 record 为 upstream failed
- **THEN** 返回 2，同时保留可用 artifact、完整分母和候选相关 frontier

### Requirement: Cache only complete stable ingestion results
ingestion cache identity SHALL 包含 bundle/record digest、BC hash、reader/extractor/schema/policy、target/profile、scope 依赖和影响完整性的预算。只有内容稳定、引用闭合且 facts 完整的 record 可作为成功 cache hit；missing、failed、partial、损坏、陈旧或未穷尽输入 MUST NOT 作为 complete 复用。每次消费 cached artifact 仍 SHALL 校验已发布内容 hash。

#### Scenario: Reader protocol changes
- **WHEN** 相同外部 BC 使用新的 extractor/reader protocol
- **THEN** 生成新的事实/cache identity，不覆盖旧事实或把旧结果当成命中

#### Scenario: A cached artifact file is corrupted
- **WHEN** artifact store 中内容与登记 digest 不同
- **THEN** cache 被拒绝并输出 cache-corrupt，不回退为成功空 facts
