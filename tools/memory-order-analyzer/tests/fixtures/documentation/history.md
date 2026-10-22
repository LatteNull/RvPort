# 文档契约历史证据

仅供离线文档契约测试使用。以下记录保留各自原版本的场景映射、统计和限制；不是当前覆盖率或使用手册。日常入口见 [文档索引](../../../doc/README.md)。

<a id="doc-foundation-acceptance"></a>

## FOUNDATION_ACCEPTANCE

Change：`establish-llvm-analysis-foundation`。以下列出全部 27 个 requirement、58 个 scenario 及其实现验证入口。`unit`/`cpp` 为单元测试，`integration` 为独立集成/文档验收，后者不贡献单元覆盖率。

## 自有执行代码与覆盖模块

所有自有执行代码均为首次实现；未复制或导入归档项目代码。保留现有 probe 并在本项目独立单测。

| 模块 | 源码范围 |
| --- | --- |
| Python 编排、契约、执行、上下文、流水线、范围、报告、质量 | `python/memory_order_analyzer/{__init__,__main__,cli,contracts,execution,toolchain,context,pipeline,scope,report,quality}.py` |
| 历史探针 | `doc/experiments/probe_bc.py` |
| C++ LLVM 核心及入口 | `src/facts.cpp`、`src/worker_entry.cpp`、`src/worker.cpp` |

当前 `src/facts.h` 仅含声明，无可执行定义。Dockerfile、CMake、JSON schema/锁清单属于声明式构建/契约配置，分别以实际构建和输入校验验证，不伪造其行/分支率。纯被测 C/C++ 夹具、测试代码、第三方 LLVM/GoogleTest/Python 依赖不作为自有生产逻辑计数。新增自有 Python/C++ 模块即使未被测试加载，必须进入统计；逐源码模块、语言、整体三层同时验收 >=90%，不能平均百分比，也不合并集成 profile。

## analysis-integrity-reporting

### Publish versioned and deterministic artifact contracts

| Scenario | 验证入口 |
| --- | --- |
| A consumer receives a future schema version | [unit/test_contracts.py](../../unit/test_contracts.py) — test_contract_validation |
| Repeat fact extraction for the same artifact | [cpp/test_facts.cpp](../../cpp/test_facts.cpp) — Facts.DeclarationAndDeterminism |

### Separate infrastructure completion from safety evaluation

| Scenario | 验证入口 |
| --- | --- |
| All requested BC files are processed successfully | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_integrity_counts_status_and_no_safety |
| A module lacks debug information | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_integrity_counts_status_and_no_safety |

### Account for the full planned input set

| Scenario | 验证入口 |
| --- | --- |
| Only part of the planned build succeeds | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_integrity_counts_status_and_no_safety |
| There are no planned translation units | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_integrity_counts_status_and_no_safety |

### Return exit statuses consistent with requested operations

| Scenario | 验证入口 |
| --- | --- |
| One worker fails while others produce usable facts | [unit/test_cli.py](../../unit/test_cli.py) — test_collect_partial_and_import |
| Explicit link lacks a scope | [unit/test_cli.py](../../unit/test_cli.py) — test_arguments_and_module_entry |

## analyzer-development-container

### Build an independent development image in this change

| Scenario | 验证入口 |
| --- | --- |
| Build from a clean project context | [integration/test_offline.py](../../integration/test_offline.py) — test_compiler_language_matrix；另见 FOUNDATION_VALIDATION 的实际镜像构建记录 |
| Preserve production container configuration | [integration/test_documentation.py](../../integration/test_documentation.py) — test_local_documentation_links；另见最终 git 范围核对 |

### Pin and verify the analysis toolchain

| Scenario | 验证入口 |
| --- | --- |
| Tools do not match the lock | [unit/test_toolchain.py](../../unit/test_toolchain.py) — test_probe_and_doctor |

### Run isolated development and quality checks

| Scenario | 验证入口 |
| --- | --- |
| Validate inside the built image | [integration/test_offline.py](../../integration/test_offline.py) — test_physical_tus_link_extern_static_overloads_and_lineage；完整 quality 命令实际执行 |

## analyzer-unit-test-quality

### Unit test all owned executable logic

| Scenario | 验证入口 |
| --- | --- |
| Reuse an existing helper | 历史验收使用 `unit/test_probe.py` 的 `test_fixed_assertions_artifacts_and_exit`；原实验采集器及其专用测试已在开源迁移中退役，此条仅保留历史背景 |
| Existing probe remains executable in this project | 历史验收使用 `unit/test_probe.py` 的 `test_failure_timeout_missing_function_and_entry`；当前执行入口见 README，原 probe 不再随源码交付 |

### Enforce whole-project and module coverage thresholds

| Scenario | 验证入口 |
| --- | --- |
| A new module is never imported by tests | [unit/test_quality.py](../../unit/test_quality.py) — test_missing_report_unloaded_source_exclusions_and_invalid_counts |
| Line coverage passes but branch coverage fails | [unit/test_quality.py](../../unit/test_quality.py) — test_threshold_modules_languages_and_weighted_totals |
| Integration tests increase measured coverage | [unit/test_quality.py](../../unit/test_quality.py) — test_quality_orchestration_separates_profiles |

### Make coverage accounting auditable

| Scenario | 验证入口 |
| --- | --- |
| A difficult error-handling file is excluded | [unit/test_quality.py](../../unit/test_quality.py) — test_missing_report_unloaded_source_exclusions_and_invalid_counts |

### Provide a repeatable quality gate and exercise its failures

| Scenario | 验证入口 |
| --- | --- |
| Coverage report is missing | [unit/test_quality.py](../../unit/test_quality.py) — test_missing_report_unloaded_source_exclusions_and_invalid_counts |
| Threshold boundary is tested | [unit/test_quality.py](../../unit/test_quality.py) — test_threshold_modules_languages_and_weighted_totals |

## bc-build-context-documentation

### Document production compiler adaptation limits

| Scenario | 验证入口 |
| --- | --- |
| Replay a GCC compilation with analysis Clang | [integration/test_offline.py](../../integration/test_offline.py) — test_compiler_language_matrix |
| A user supplies an MSVC or clang-cl command | [unit/test_context.py](../../unit/test_context.py) — test_driver_and_precedence |

## gcc-clang-compilation-context

### Ingest supported compiler commands without shell execution

| Scenario | 验证入口 |
| --- | --- |
| Arguments take precedence over command | [unit/test_context.py](../../unit/test_context.py) — test_driver_and_precedence |
| Command requests shell substitution | [unit/test_context.py](../../unit/test_context.py) — test_split_and_responses |
| Response files form a cycle | [unit/test_context.py](../../unit/test_context.py) — test_split_and_responses |

### Preserve production context and explain adaptation

| Scenario | 验证入口 |
| --- | --- |
| GCC implicit C++ headers are required | [integration/test_offline.py](../../integration/test_offline.py) — test_compiler_language_matrix |
| Ordered macro operations affect preprocessing | [unit/test_context.py](../../unit/test_context.py) — test_order_profile_and_output_isolation |

### Give each effective TU a stable configuration identity

| Scenario | 验证入口 |
| --- | --- |
| Reorder compilation database entries | [unit/test_context.py](../../unit/test_context.py) — test_prepare_and_identity |
| One source uses different macro configurations | [unit/test_context.py](../../unit/test_context.py) — test_prepare_and_identity |

### Validate dependencies before artifact cache reuse

| Scenario | 验证入口 |
| --- | --- |
| A new header shadows a previous include | [integration/test_offline.py](../../integration/test_offline.py) — test_dependency_shadow_cache_and_profiles |
| Inputs change while compiling | [unit/test_pipeline.py](../../unit/test_pipeline.py) — test_collect_cache_publication_and_unstable_inputs |
| A required generated header is absent | [integration/test_offline.py](../../integration/test_offline.py) — test_missing_header_and_invalid_bc |

## llvm-bitcode-facts

### Generate verified compile-only artifacts

| Scenario | 验证入口 |
| --- | --- |
| Compiler exits successfully without an artifact | [unit/test_pipeline.py](../../unit/test_pipeline.py) — test_collect_cache_publication_and_unstable_inputs |
| A source references an unavailable external implementation | [cpp/test_facts.cpp](../../cpp/test_facts.cpp) — Facts.DeclarationAndDeterminism / Facts.MemoryKindsAddressesAndControlFlow |
| Collect the same TU with two profiles | [integration/test_offline.py](../../integration/test_offline.py) — test_dependency_shadow_cache_and_profiles |

### Import and validate existing bitcode with provenance

| Scenario | 验证入口 |
| --- | --- |
| Invalid or incompatible input has a bc extension | [cpp/test_facts.cpp](../../cpp/test_facts.cpp) — Reader.ValidInvalidVerifyAndWorkerEntry |
| Producer is unknown but the module can be read | [unit/test_pipeline.py](../../unit/test_pipeline.py) — test_import_unknown_and_verified |

### Extract structured memory and control-flow facts

| Scenario | 验证入口 |
| --- | --- |
| CAS has distinct success and failure orders | [cpp/test_facts.cpp](../../cpp/test_facts.cpp) — Facts.MemoryKindsAddressesAndControlFlow |
| Signal fence is limited to one thread | [cpp/test_facts.cpp](../../cpp/test_facts.cpp) — Facts.MemoryKindsAddressesAndControlFlow |
| Atomic operations remain inside a C++ wrapper | [integration/test_offline.py](../../integration/test_offline.py) — test_compiler_language_matrix |

### Keep IR facts when source mapping is incomplete

| Scenario | 验证入口 |
| --- | --- |
| Debug information is stripped | [integration/test_offline.py](../../integration/test_offline.py) — test_nodebug_and_incompatible_targets |
| Source content no longer matches recorded evidence | [unit/test_pipeline.py](../../unit/test_pipeline.py) — test_source_mapping |

### Bound compiler and worker execution

| Scenario | 验证入口 |
| --- | --- |
| A compiler process exceeds its timeout | [unit/test_execution.py](../../unit/test_execution.py) — test_runner_budget |

## memory-order-evidence-documentation

### Keep DevKit observations separate from validation plans

| Scenario | 验证入口 |
| --- | --- |
| No new ARM validation evidence is collected | [integration/test_documentation.py](../../integration/test_documentation.py) — test_offline_evidence_hashes_and_matrix；本次只搬迁历史证据，没有重跑 mm-check |
| Preserve the September 11 experiment evidence | [integration/test_documentation.py](../../integration/test_documentation.py) — test_offline_evidence_hashes_and_matrix |
| Interpret independent and linked bitcode results | [integration/test_documentation.py](../../integration/test_documentation.py) — test_offline_evidence_hashes_and_matrix；人工复核 DEVKIT_BC_VALIDATION 当前矩阵 |
| Compiler exit zero or scanner success is misleading | [unit/test_pipeline.py](../../unit/test_pipeline.py) — test_collect_cache_publication_and_unstable_inputs；ARM 差异仅作为证据限制 |

### Provide discoverable and consistent documentation

| Scenario | 验证入口 |
| --- | --- |
| Follow the documentation entry point | [integration/test_documentation.py](../../integration/test_documentation.py) — test_local_documentation_links |
| Development image is delivered before production consolidation | [integration/test_documentation.py](../../integration/test_documentation.py) — test_local_documentation_links；实际 Docker 构建和改动范围记录 |

## scoped-module-association

### Associate modules only within an explicit scope

| Scenario | 验证入口 |
| --- | --- |
| Only compilation commands are supplied | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_integrity_counts_status_and_no_safety |
| Two executable targets contain the same symbol | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_direct_symbols_unknown_and_invalidation |

### Resolve direct references without inventing aliases

| Scenario | 验证入口 |
| --- | --- |
| Resolve a direct call across physical source files | [integration/test_offline.py](../../integration/test_offline.py) — test_physical_tus_link_extern_static_overloads_and_lineage |
| Internal symbols share a name | [integration/test_offline.py](../../integration/test_offline.py) — test_physical_tus_link_extern_static_overloads_and_lineage |
| An indirect call has no implemented resolver | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_direct_symbols_unknown_and_invalidation |

### Link only compatible selected modules and retain lineage

| Scenario | 验证入口 |
| --- | --- |
| Scope contains incompatible target modules | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_scope_preflight_conflicts |
| Linked and original modules overlap | [integration/test_offline.py](../../integration/test_offline.py) — test_physical_tus_link_extern_static_overloads_and_lineage |

### Expose the limited association stage

| Scenario | 验证入口 |
| --- | --- |
| Target membership changes without BC changes | [unit/test_scope_report.py](../../unit/test_scope_report.py) — test_direct_symbols_unknown_and_invalidation |
| A resolved callee writes a global | [integration/test_offline.py](../../integration/test_offline.py) — test_physical_tus_link_extern_static_overloads_and_lineage |

<a id="doc-semantic-facts-acceptance"></a>

## SEMANTIC_FACTS_ACCEPTANCE

对应 change `enrich-ir-semantic-facts` 的 13 个 requirement、34 个 scenario。每项均映射到具名断言；集成不计入单元覆盖率。

测试入口：[C++ 原事实测试](../../cpp/test_facts.cpp)、[C++ 语义测试](../../cpp/test_semantic.cpp)、[Python 语义/迁移测试](../../unit/test_semantic.py)、[pipeline 测试](../../unit/test_pipeline.py)、[scope/report 测试](../../unit/test_scope_report.py)、[CLI 测试](../../unit/test_cli.py)、[quality 测试](../../unit/test_quality.py)、[真实编译](../../integration/test_offline.py)、[真实迁移](../../integration/test_semantic_migration.py)、[文档回归](../../integration/test_documentation.py)。

## Preserve typed value identities and exact constants

| Scenario | 具名测试及断言 |
| --- | --- |
| Wide integers survive JSON serialization | Semantic.CyclicPhiTypedConstantsAndOperations：i128 hex=10000000000000001 与位宽，typed 常量；Semantic.SwitchCasAggregateAndReturnChain：i128 case 引用 |
| Special values and unmodeled values remain distinct | Semantic.CyclicPhiTypedConstantsAndOperations：null/undef/poison/zero/freeze；Semantic.MissingScalableLayoutAndUnsupportedValues：浮点 unknown 原因 |
| Repeated extraction preserves references after module destruction | Facts.MemoryKindsAddressesAndControlFlow：释放 Module 后重新序列化完全一致；Semantic.BudgetsProtocolEmptyAndLifetime；Semantic.UnnamedSymbolsAndPaddingFieldOffsets：未命名身份不碰撞 |

## Export operand relations without solving paths

| Scenario | 具名测试及断言 |
| --- | --- |
| Loop phi references a backedge result | Semantic.CyclicPhiTypedConstantsAndOperations：phi→select→计算→phi 闭合、incoming 前驱、重复提取一致 |
| Select and casts distinguish signed interpretation | Semantic.CyclicPhiTypedConstantsAndOperations：sext/zext/trunc、select、icmp ult、nsw/nuw/exact；不改写常量/路径 |

## Preserve conditional control-flow and call interfaces

| Scenario | 具名测试及断言 |
| --- | --- |
| Switch cases share a successor | Semantic.SwitchCasAggregateAndReturnChain：default + 两条同目标不同 case，完整 128 位 case 引用 |
| Invoke has an exceptional successor | Semantic.CallsInvokeBundlesAndUnknowns：实参、result_ref、normal/unwind；Semantic.SwitchCasAggregateAndReturnChain：ret 引用 |
| Indirect and opaque call features are present | Semantic.CallsInvokeBundlesAndUnknowns：间接目标、bundle、ABI 原文/unknown、tail、resume 未知；Facts.MemoryKindsAddressesAndControlFlow：inline asm |

## Bound semantic graph extraction without dangling references

| Scenario | 具名测试及断言 |
| --- | --- |
| A constant exceeds the nesting limit | Semantic.BudgetsProtocolEmptyAndLifetime：注入 depth=0，聚合叶成为 constant_depth unknown、partial |
| Total graph or output budget is exhausted | Semantic.BudgetsProtocolEmptyAndLifetime：节点/引用边界成功、越界与输出超限抛错；test_reader_protocol_and_manifest：错误码保留；test_collect_partial_and_import[extraction_budget_exceeded]：独立 TU 继续、分母保留 |

## Describe memory access sizes from module layout

| Scenario | 具名测试及断言 |
| --- | --- |
| Padded structure fields are accessed | Semantic.UnnamedSymbolsAndPaddingFieldOffsets：字段 offset=4、访问 size=4；Semantic.DataLayoutRangesOffsetsAndIntrinsics：整个 padded 类型 store size=8、对齐/地址空间 |
| Layout or access size is not statically available | Semantic.MissingScalableLayoutAndUnsupportedValues：缺布局/scalable unknown；Semantic.DataLayoutRangesOffsetsAndIntrinsics：fence not_applicable、动态长度未知 |

## Preserve exact constant offsets and address-space boundaries

| Scenario | 具名测试及断言 |
| --- | --- |
| Negative or wide pointer offsets occur | Semantic.DataLayoutRangesOffsetsAndIntrinsics：-4 和 128 位 index 的 18446744073709551617，非 int64 截断 |
| Dynamic index or address-space cast occurs | Semantic.DataLayoutRangesOffsetsAndIntrinsics：dynamic_offset、addrspacecast/inttoptr unknown；Facts.MemoryKindsAddressesAndControlFlow：受限 address 不能解析动态指针 |

## Export memory operation values and initialization facts

| Scenario | 具名测试及断言 |
| --- | --- |
| CAS result is decomposed | Semantic.SwitchCasAggregateAndReturnChain：compare/new/result、extractvalue 索引、成功位 br；Facts.MemoryKindsAddressesAndControlFlow：两种 order 和 weak |
| Bulk operations have zero or unknown lengths | Semantic.DataLayoutRangesOffsetsAndIntrinsics：memcpy 已知 0、memmove 动态 unknown、memset fill=2A、独立源/目的范围 |
| Declaration and initialized definition coexist | Semantic.CyclicPhiTypedConstantsAndOperations：声明/整数/指针/零聚合/递归指针；Semantic.MissingScalableLayoutAndUnsupportedValues：不支持浮点初值 unknown |

## Extract structured memory and control-flow facts

| Scenario | 具名测试及断言 |
| --- | --- |
| CAS has distinct success and failure orders | Facts.MemoryKindsAddressesAndControlFlow：acq_rel/acquire/weak 不合并 |
| Signal fence is limited to one thread | Facts.MemoryKindsAddressesAndControlFlow：singlethread/system 分开 |
| Atomic operations remain inside a C++ wrapper | test_compiler_language_matrix 的四种 C++ 组合：显式 noinline 外层调用、形参存栈、条件、原始 monotonic/release/seq_cst 分支；callsite_specialization=false |
| Rich facts are extracted without debug information | test_nodebug_and_incompatible_targets：真实 -g0 BC 仍有 v2 values/ranges，定位 unavailable；Facts.DeclarationAndDeterminism：空事件不当安全结果 |

## Publish versioned and deterministic artifact contracts

| Scenario | 具名测试及断言 |
| --- | --- |
| A consumer receives a future schema version | test_valid_graph_and_per_kind_versions：未来版本、bool、旧版本拒绝 |
| Repeat fact extraction for the same artifact | Facts.DeclarationAndDeterminism、Semantic.CyclicPhiTypedConstantsAndOperations：精确 JSON 一致；test_real_bitcode_migration_scope_and_measurement：重读相同 BC facts 一致 |
| Old facts and unchanged manifests are consumed | test_valid_graph_and_per_kind_versions：新旧 kind 分别验证；test_import_rekey_idempotence_and_scope：v1 facts 拒绝、v1 manifest 保留 |

## Distinguish new reports from historical v1 reports

| Scenario | 具名测试及断言 |
| --- | --- |
| A historical report lacks extraction information | test_valid_graph_and_per_kind_versions：RunReport v1 拒绝，v2 缺 fact_extraction 亦拒绝，无默认升级 |

## Validate semantic references at every consumption boundary

| Scenario | 具名测试及断言 |
| --- | --- |
| An index input has a dangling or foreign value reference | test_invalid_graph_rejected：重复/悬空/跨函数、phi/CFG、不合法范围等 36 种破坏；test_import_rekey_idempotence_and_scope、test_scope_preflight_conflicts：scope 消费入口校验 |
| An unsupported node has a valid identity | test_valid_graph_and_per_kind_versions：合法 unknown 可作为实参引用；test_invalid_graph_rejected：缺原因/诊断不得伪装合法 |

## Isolate extractor generations across artifact paths

| Scenario | 具名测试及断言 |
| --- | --- |
| A worker has the right LLVM but the wrong protocol | test_metadata_handshake_and_doctor：同 LLVM 错协议、缺/坏元数据、旧 worker 拒绝；test_reader_protocol_and_manifest：读取入口检查 |
| Collection encounters an old cache generation | test_new_cache_generation_misses_old_and_keeps_old_files：旧 key miss/文件未改、新 key hit；test_policy_identity_and_truncated_worker：policy 失效；test_new_include_shadow_changes_rediscovered_identity：依赖重发现 |
| Old manifested bitcode is re-extracted | test_import_rekey_idempotence_and_scope：来源/context/profile/lineage 保留、幂等；test_real_bitcode_migration_scope_and_measurement：真实重提取、旧文件 hash 未变、显式 scope 重建 |
| Raw imports and linked modules change extractor generation | test_import_rekey_idempotence_and_scope：raw unknown/无虚构映射/祖先交叉拒绝；test_physical_tus_link_extern_static_overloads_and_lineage：真实 linked v2/全部祖先/同名局部隔离 |

## Report fact extraction completeness without semantic verdicts

| Scenario | 具名测试及断言 |
| --- | --- |
| Parsing succeeds with unsupported semantic operands | test_report_v2_denominators_and_partial：partial→退出 2、诊断保留；Semantic.MissingScalableLayoutAndUnsupportedValues：IR 合法不等于全部可解释 |
| One translation unit exceeds the extraction budget | test_collect_partial_and_import[extraction_budget_exceeded]：1/3 完整、2 失败，保留失败码；test_report_v2_denominators_and_partial：全失败→1、不缩计划分母 |
| Complete facts still do not constitute a safety scan | test_report_v2_denominators_and_partial：完整→0、doctor not_run、零分母 null、semantic/safety/findings 固定；test_integrity_counts_status_and_no_safety：原报告行为回归 |

## 共用质量规范

全部自有 C++/Python 代码（包括历史探针）按整体、各语言、逐模块检查行/分支 ≥90%；零可用分支记为 N/A，不虚报 100%。test_recursive_source_inventory_and_executable_headers 与 test_missing_report_unloaded_source_exclusions_and_invalid_counts 检查子目录、未加载源、可执行头文件和缺失报告；test_quality_orchestration_separates_profiles 检查单元/集成隔离。声明头文件仅在审核 hash 一致时豁免，无业务逻辑排除。CMake 包含全部当前自有 C++ 实现。

test_local_documentation_links 检查本地链接；test_offline_evidence_hashes_and_matrix 校验 198 个历史文件 hash 和 47 份报告；test_semantic_scenarios_have_acceptance_entries 校验本表没有漏 scenario。OpenSpec strict 校验单独执行。测试覆盖率不等于语义完备性或缺陷检测正确率。

<a id="doc-thread-and-sync-contexts-validation"></a>

## THREAD_AND_SYNC_CONTEXTS_VALIDATION

本文件对应 OpenSpec change `model-thread-and-sync-contexts`。语义正确性以具名断言为准，覆盖率只证明测试执行范围，不代表并发缺陷检测准确率。被分析夹具只 compile-only，不链接、不运行；离线验收不依赖 SSH、ARM DevKit 或网络。

## 1. Requirement 与测试映射

| OpenSpec Requirement | 主要测试/证据 |
| --- | --- |
| Validate P3 cross-layer evidence integrity | `test_thread_contracts.py::test_semantic_reference_rejections`、`test_graph_semantic_rejections`、P3 schema strict validation |
| Preserve P3 plans, unknown frontiers and completeness denominators | `test_report_counts_statuses_and_exit_codes`、`test_context_instance_and_graph_item_budgets_are_conservative` |
| Isolate P3 policy and cache identities from earlier stages | `Threads.ProtocolAndPthreadFactsAreIndependent`、`test_stable_identity_keys_and_cache` |
| Compose conditional execution order from independent evidence | `Threads.LocalFactsCoverConservativeProvenanceCallsAndControlFlow`、`test_graph_builds_contexts_instances_order_mhp_mutex_and_reads_from` |
| Derive conservative may-happen-in-parallel relations | `test_graph_builds_contexts_instances_order_mhp_mutex_and_reads_from`、`test_join_clobber_or_no_reachable_handle_stays_unknown` |
| Model ordinary mutex synchronization candidates by object | `test_graph_builds_contexts_instances_order_mhp_mutex_and_reads_from`、`test_private_finite_domain_and_budget_branches` |
| Preserve atomic reads-from candidates without inventing happens-before | `test_disjoint_atomic_objects_are_only_excluded_candidates`、三 TU 集成测试 |
| Keep thread relations separate from safety findings | 所有 report/集成断言 `safety=not_evaluated`、`findings=null` |
| Produce independent versioned thread-local facts | `Threads.ProtocolAndPthreadFactsAreIndependent`、`Threads.BatchAndWorkerRejectInvalidOrChangedInputs` |
| Recognize pthread primitives and callbacks conservatively | `Threads.SupportedNamesStillRequireEveryAbiAndCallbackCondition`、`Threads.CallbackCandidatesFollowBoundedBitcastSelectAndPhi` |
| Derive execution order from LLVM control-flow evidence | `Threads.LoopEventsAreNeverPromotedToSingleMustOrder`、`Threads.LocalFactsCoverConservativeProvenanceCallsAndControlFlow` |
| Track bounded handle and mutex provenance | `Threads.LocalFactsCoverConservativeProvenanceCallsAndControlFlow`、join/预算 Python 单测 |
| Bound local thread evidence without publishing dangling facts | `Threads.LocalAndGraphBudgetsPublishPartialFrontiers`、contract dangling endpoint tests |
| Define a strict versioned thread analysis protocol | `test_protocol_schema_roundtrip_and_bilingual_pair`、C++ protocol测试 |
| Expose explicit model-threads CLI behavior | `test_model_threads_cli_parser_execute_and_failure`、`test_p2_plan_uses_only_explicit_roots_and_adopted_callbacks`、真实三 TU 集成测试 |
| Report layered completeness and explicit denominators | `test_report_counts_statuses_and_exit_codes` |
| Provide bilingual human-facing diagnostics | `test_protocol_schema_roundtrip_and_bilingual_pair`、unknown 路径断言 |
| Cache P3 outputs with transitive dependencies | `test_stable_identity_keys_and_cache`、`test_model_threads_fresh_output_cache_miss_and_hit` |
| Never report safety findings during P3 | CLI、report 和集成断言 |
| Unit test every P3 owned executable module | 质量入口逐文件枚举 Python/C++ 和未加载源码失败测试 |
| Enforce ninety-percent P3 and project coverage gates | `test_quality.py` 的 89.99%/90% 边界与真实质量入口 |
| Exercise fixed pthread semantic fixtures independently | `test_thread_modeling.py` 三物理 TU compile-only 集成 |
| Separate reusable thread contexts from thread instances | 同入口两个 create 产生 1 context/2 child instances 断言 |
| Model conditional create and thread lifecycle events | 生命周期 kind、guard 和 callback unknown 断言 |
| Associate joins through bounded handle provenance | 唯一句柄、clobber、无路径测试 |
| Bound recursive and repeated thread creation conservatively | recursive/repeated merged instance 和 frontier 测试 |
| Require explicit scoped roots for thread analysis | 无根、非成员根、声明根和跨 TU closed scope 测试 |

## 2. Scenario 完整映射

下列 62 个 Scenario 均由上表对应的具名测试或相邻参数化 case 覆盖；保留原名便于自动检查 OpenSpec 与文档一致性。

- An order edge references another invocation
- A P2 summary is replaced after local thread extraction
- A recursive spawn reaches the instance limit
- Source mapping is unavailable but IR evidence remains usable
- Only the pthread model version changes
- P2 order exists without P3 proof
- A callee returns normally between caller effects
- Parent continues after creating a worker
- Parent code follows a proven successful join
- Join or lifecycle evidence is incomplete
- Two threads use the same supported mutex
- Threads use different mutex objects
- Lock can fail or unlock is unbalanced
- A release write may feed an acquire read
- Candidate objects or scopes are incompatible
- A fence or CAS protocol is encountered
- The graph contains no parallel pair
- A likely relaxed publication pattern is present
- Repeated extraction uses unchanged inputs
- Bitcode or a dependency changes during extraction
- A direct create call has a supported callback
- Metadata and the registered model disagree
- A similarly named wrapper is encountered
- Instructions are ordered in a non-repeating region
- A loop can reverse dynamic occurrences
- Ordering crosses a call boundary
- A handle is copied through exact storage
- A handle slot is overwritten or escapes
- A mutex initializer is not recognized
- Candidate expansion exceeds a local limit
- An analysis reference is forged or stale
- A complete v1 product set is consumed
- A future or mixed generation is supplied
- A valid request completes
- Useful results contain unknowns
- The request is invalid
- One scope member cannot be analyzed
- No candidate exists for a valid empty category
- An unresolved thread handle is reported
- A translated string changes
- A worker summary changes without caller BC changing
- A reusable context is instantiated from cache
- Analysis is complete with no unknown frontier
- A new thread-analysis source is not loaded by tests
- P2 order is accidentally reused as proof
- A module has 89.99 percent branch coverage
- All thresholds are satisfied
- The fixed multi-TU fixture is analyzed offline
- An unsupported construct is present
- The same entry is created at two callsites
- A worker function calls ordinary functions
- Create success is checked
- Create return is ignored
- A callback target cannot be resolved
- A unique worker is joined successfully
- A join handle has multiple candidates
- Join fails or is unsupported
- A loop repeatedly creates the same entry
- Recursive thread discovery reaches a fixed point
- A thread budget is exhausted
- Main and worker belong to a valid scope
- Roots are absent or profiles conflict

## 3. 固定夹具与语义断言

`tests/integration/test_thread_modeling.py` 创建三个物理 TU：main 包含两个不同 create callsite 和 join，worker 包含普通静态 mutex 与 atomic RMW，第三 TU 验证 scope 不依赖目录扫描。Clang C17 只生成 BC；测试断言 3 个实例、两个 child、生命周期、mutex/reads-from 候选、无 `.o`、无风险结论。

C++ 固定 IR 覆盖 direct/indirect/相似名称、ABI 不兼容、callback metadata、bitcast/select/phi 候选、call/invoke/no-return、直线/菱形/循环/逆文本块顺序、局部与图预算、输入 hash/format/worker transport。Python 固定图覆盖跨 TU 回调唯一绑定、上下文/实例分离、P2 效果归属、递归/循环合并、唯一/不确定 join、mutex 平衡区间、相同/不同 atomic 对象和不产生 HB。

mutex `zero-static:<sha256>` 的 sha256 输入由 worker 固定为 target triple、DataLayout 和 LLVM initializer 文本；只接受 64 位小写十六进制指纹。它是当前 target/ABI/initializer 假设证据，不是对所有 libc、robust/recursive 属性或动态初始化的证明。

## 4. 质量与复现

最终质量命令使用新的持久输出目录：

```bash
docker run --rm --network none \
  --mount type=bind,source=D:/projects/RvPort/tools/memory-order-analyzer,target=/workspace,readonly \
  --mount type=volume,source=moa-dev-output,target=/output \
  memory-order-analyzer-dev:llvm21 \
  bash -lc 'PYTHONPATH=/workspace/python python3 -m memory_order_analyzer.quality --output /output/quality-p3-final-005 --integration'
```

统计范围为 `python/memory_order_analyzer/**/*.py`、`doc/experiments/**/*.py` 和 `src` 下全部自有 C/C++ 可执行源码/头文件；测试、纯夹具、第三方和 configure 生成的协议头不计入生产源码。单元 profile 与集成 profile 分离。验收要求项目整体、Python、C++ 以及每个受影响模块的行/分支覆盖率均至少 90%。

最终复验使用 LLVM/Clang 21.1.8，结果如下：

- C++ 单元测试：56/56 通过；Python 单元测试：345/345 通过；离线集成测试：28/28 通过。
- 项目整体：行 5549/5600（99.0893%），分支 3473/3650（95.1507%）。
- Python：行 3110/3154（98.6049%），分支 1355/1408（96.2358%）。
- C++：行 2439/2446（99.7138%），分支 2118/2242（94.4692%）。

P3 核心受影响模块逐模块结果：

| 模块 | 行覆盖率 | 分支覆盖率 |
| --- | ---: | ---: |
| `model_threads.py` | 113/115（98.2609%） | 42/44（95.4545%） |
| `thread_cache.py` | 54/54（100%） | 14/14（100%） |
| `thread_contracts.py` | 148/156（94.8718%） | 88/95（92.6316%） |
| `thread_graph.py` | 402/419（95.9427%） | 200/221（90.4977%） |
| `thread_models.py` | 39/40（97.5000%） | 25/26（96.1538%） |
| `thread_report.py` | 43/43（100%） | 12/12（100%） |
| `thread_worker.py` | 56/56（100%） | 14/14（100%） |
| `thread_analysis.cpp` | 337/337（100%） | 264/282（93.6170%） |
| `thread_worker.cpp` | 96/96（100%） | 67/74（90.5405%） |
| `threads.h` | 3/3（100%） | 不适用（0 个可执行分支） |

机器可读汇总位于 `/output/quality-p3-final-005/coverage-summary.json`，Python 明细和 HTML 分别位于 `/output/quality-p3-final-005/python.json` 与 `/output/quality-p3-final-005/python-html/index.html`；C++ 原始 profile、构建产物与覆盖中间结果同在 `/output/quality-p3-final-005/`。质量入口将集成测试作为独立 profile 执行，避免把集成命中混入单元覆盖率。

为保留一条独立、可见的集成验收记录，使用同一 worker 额外复验：

```bash
docker run --rm --network none \
  --mount type=bind,source=D:/projects/RvPort/tools/memory-order-analyzer,target=/workspace,readonly \
  --mount type=volume,source=moa-dev-output,target=/output \
  memory-order-analyzer-dev:llvm21 \
  bash -lc 'cd /workspace && MOA_WORKER=/output/quality-p3-final-005/build/moa-worker PYTHONPATH=python python3 -m pytest -q -p no:cacheprovider tests/integration'
```

该命令实测 28/28 通过。所有覆盖率门槛均已达到；上述结果不改变“覆盖率不等于并发缺陷检测准确率”的边界。

<a id="doc-validation-and-scaling-validation"></a>

## VALIDATION_AND_SCALING_VALIDATION

验收日期：2026-09-18。结论：P5 验证基础设施完成质量门禁；验证结果揭示 P4 的真实能力缺口，因此不能解释为分析器或程序“安全”。

## 1. 环境与身份

- 开发容器：`memory-order-analyzer-dev:llvm21`；Ubuntu 24.04，LLVM/Clang 21.1.8，GCC 13.3.0（lock 文件记录的初始包版本为 13.2.0），CMake 3.28.3，Ninja 1.11.1，pytest 7.4.4，coverage 7.4.4。
- P5 协议 SHA-256：`8beb0544c8dc9a97a291ecf7ff601cc68cc610c6ceef5555f84a600f06e74803`；schema：`9ba2136c64fc5e1a12d6ba805102efa959865f16e62ac21b92d139b1678d59be`。
- 离线 suite 文件 SHA-256：`42a513bd8364b8b22ed1618b5599f030fcd348ca14138b817649a475fe59ad00`。
- TinyCThread revision 为 `6957fc8383d6c7db25b60b8c849b29caab1caaee`；仓内必要源码树的当前可审计 digest 为 `a14757b85a8acab53c184a65cff36974a9666bad77d3d8e1b3d1319eddb0ab24`（profile 文件随仓内快照重新校准）。

P1–P4 基线见 `tests/fixtures/validation/p1-p4-baseline.json`。P5 未修改四层 schema/协议或历史质量产物。

## 2. 精确命令

单元质量（输出必须为新目录）：

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace -e PYTHONPATH=/workspace/python \
  memory-order-analyzer-dev:llvm21 \
  python3 -m memory_order_analyzer.quality \
  --output /workspace/reports/quality-p5-20260918-final-2
```

独立语料与文档验收：

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace -e PYTHONPATH=/workspace/python \
  memory-order-analyzer-dev:llvm21 sh -lc \
  'cmake -S . -B /tmp/moa-build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ >/dev/null && \
   cmake --build /tmp/moa-build -j 4 >/dev/null && \
   MOA_WORKER=/tmp/moa-build/moa-worker python3 -m pytest -q -p no:cacheprovider \
   tests/integration/test_validation_corpus.py tests/integration/test_documentation.py \
   --basetemp=/workspace/reports/p5-offline-20260918-final-2'
```

真实工程 cold/warm 验收使用相同构建前缀，pytest 部分为：

```bash
MOA_WORKER=/tmp/moa-build/moa-worker python3 -m pytest -q -p no:cacheprovider \
  tests/integration/test_validation_real_project.py \
  --basetemp=/workspace/reports/p5-real-project-20260918-final-2
```

## 3. 固定人工真值语料

计划和执行均为 8 case / 8 profile，覆盖 C11、C17、C++17、C++20，GCC/Clang，4 个单 TU 和 4 个至少三物理 TU case，以及 correct/risk/unknown 三类。全部输入 hash、truth v1 和人工审阅身份通过；compile-only 语法检查全部成功，没有链接或执行目标。

实际 P1–P4 结果：exact match `3/8 = 37.5%`，TP=3、FP=0、strict FN=7，strict precision=`3/3 = 100%`，strict recall=`3/10 = 30%`，abstention=`8/8 = 100%`；supported-only precision/recall 分母均为 0，值为 `null`。这组数字是基线，不是为了展示高准确率。

主要缺口：当前跨 TU 风险 case 未形成候选；所有 case 因 P3/源映射部分证据而 abstain；C17 fence case 暴露已有 P4 `syncscope=""` 与 schema 不兼容并记录 failed；C++17 CAS 保持 unsupported/partial。truth 未因这些输出而修改。最终原始证据位于 `reports/p5-offline-20260918-final-2/test_fixed_corpus_runs_p1_p4_a0/corpus-evidence.json`，SHA-256 为 `e07480344f540cb8814a83ee16fff1818c98bea92ea69851602b3bada0a5f4d8`。

## 4. 真实 CMake 工程与抽样

唯一入选 TinyCThread：2 条原始编译记录、2 个配置、1 个去重 TU、4 个显式 roots、1 个纳入 TU、3 类排除项、0 缺失成员。GCC 与 Clang 分配置运行，避免把同一源码的互斥构建变体放进同一 scope。

最终持久基线：collect 6.93 s；GCC cold/warm 分别为 12.57/7.35 s、CPU 0.85/0.42 s、输出 4,998,407/4,966,495 bytes、cache 文件 0→5/5→5，semantic digest 均为 `2751c9ebfd81ffd10452d9b380d88f244a61f14f56a88351c023b9f26b338aff`；Clang 21 cold/warm 分别为 13.88/7.41 s、CPU 0.92/0.45 s、输出 4,998,427/4,966,515 bytes、cache 文件 5→10/10→10，摘要均为 `8f8486abe16847f896a7746185d8d7d8acaf0147ef814a45b5face42f16483be`。观测峰值 RSS 为 142,004,224 bytes。未执行 CMake、链接或目标程序；CMake 只在快照审核阶段生成 compile database。证据位于 `reports/p5-real-project-20260918-final-2/test_tinycthread_profile_cold_0/scale-evidence.json`，SHA-256 为 `978002cbce384b4ae92f86c0c366927a8f488f145176e242048505d65dd9f9dc`。

确定性抽样使用 seed `20260918`，从 finding/discharged/unknown/unsupported/no-candidate 五层各取一个，5/5 已人工裁决。该方法主动过采样稀有层，样本结果只适用于已裁决样本，不外推完整语料、TinyCThread、其他工程或全程序安全。

## 5. 外部后端

- GenMC：开发容器无锁定二进制/镜像，`command -v genmc` 为空，状态 `not_run`。录制输出适配器和成功/风险/空输出/崩溃/超时/截断回放测试已通过。复现探测：`docker run --rm memory-order-analyzer-dev:llvm21 sh -lc 'genmc --version'`。
- herdtools7：开发容器无 `herd7`，状态 `not_run`；litmus 只标为 approximate，不能称为源码等价。复现探测：`docker run --rm memory-order-analyzer-dev:llvm21 sh -lc 'herd7 --version'`。
- ARM DevKit：只导入 2026-09-10/11 历史 hash 证据；25.3.0 / LLVM 16.0.4 的 47 个 success 报告不是正确率 oracle。本 change 没有 SSH runner，也没有重新执行远端扫描。

后端 agree/disagree/零建议均不修改人工 truth、P4 verdict 或 `safety=not_established`。

## 6. 单元测试与覆盖率

最终质量轮执行 66 个 C++ 单元测试和 412 个 Python 单元测试，均通过。报告位置：`reports/quality-p5-20260918-final-2/coverage-summary.json` 及对应 HTML；汇总 SHA-256 为 `9096ab152626504eafefefb1b479dd93dfd5c94b8e048304c7df8ee044a2459b`。

| 范围 | 行 hit/total | 行覆盖率 | 分支 hit/total | 分支覆盖率 |
| --- | ---: | ---: | ---: | ---: |
| 整体 | 7297/7387 | 98.78% | 4396/4641 | 94.72% |
| Python | 4349/4421 | 98.37% | 1915/1996 | 95.94% |
| C++ | 2948/2966 | 99.39% | 2481/2645 | 93.80% |
| `validate_analysis.py` | 176/182 | 96.70% | 65/67 | 97.01% |
| `validation_analysis.py` | 219/223 | 98.21% | 104/108 | 96.30% |
| `validation_contracts.py` | 124/128 | 96.88% | 60/62 | 96.77% |

统计递归纳入所有项目自有 Python/C++ 可执行代码。排除仅包括测试、纯实验输入、第三方实现、生成协议头和 hash 锁定的声明头；真实工程和集成 profile 不混入单元覆盖率。

独立集成验收共 12 项：固定语料 3 项、TinyCThread 真实工程 1 项、文档/链接/hash/P1–P4 兼容 8 项，全部通过。持久目录分别为 `reports/p5-offline-20260918-final-2/`、`reports/p5-real-project-20260918-final-2/` 与 `reports/p5-doc-20260918-final-3/`。语料、真实工程和外部 backend profile 没有合并进上述单元覆盖率分母。

## 7. 扩展决策

量化基线建议：B1 CMake scope、受限 callback/pointer provenance 和 fence/RMW 为 `recommend`；`std::thread` 为 `insufficient-evidence`。所有 `human_confirmed=false`，P5 不会自动创建后续 change。双语机器记录位于 `tests/fixtures/validation/decision-baseline.json`。

最终边界：`validation matched`、高覆盖率、外部一致或 P4 `discharged` 都不等于线程安全；本验收明确是**非全程序安全结论**。

<a id="doc-cpp-thread-lifecycle-validation"></a>

## CPP_THREAD_LIFECYCLE_VALIDATION

验证日期：2026-09-20。本文只记录实际执行结果；生命周期 exact match、零 FP/FN、零 finding 或退出码 0 均不是全程序线程安全证明。

## 1. 环境与 profile provenance

- 开发镜像：`memory-order-analyzer-dev:a3`，镜像 ID `sha256:fe4fe0ab157c4db748ef67dabe2beca58c975ac40fb95f326b88e7b297be6f0a`。
- Clang/LLVM：21.1.8；target：`x86_64-pc-linux-gnu`；DataLayout：`e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128`。
- libstdc++：13.3.0，`__GLIBCXX__=20240904`，`/usr/include/c++/13/thread` SHA-256 `fea05267771743b440228a690bcb9bc12bc306589050f36c40119cc1f3315552`。
- libc++：21.1.8，`_LIBCPP_VERSION=210108`，`/usr/lib/llvm-21/include/c++/v1/thread` SHA-256 `6f34c51f960688fd3362e9a682855635a53ff4c94e5dc77ed81460bdecc6e744`。
- 开发依赖锁同时包含 `libc++-21-dev` 与 `libc++abi-21-dev`。libc++abi 在 LLVM 公共 include 根安装的兼容副本会遮蔽 libstdc++ 的 cxxabi 声明；镜像删除这两个根目录副本，保留 `include/c++/v1` canonical 头，分别验证两种标准库。

ABI probe 对构造、entry broker、join、detach 和 handle-transfer 生成三份 verified profile：libstdc++ C++17/C++20、libc++ C++20。注册项位于 `cpp-thread-profiles/`，profile/model/header/wrapper digest 进入缓存身份。

## 2. 单元与源语义验证

聚焦回归：

```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace memory-order-analyzer-dev:a3 \
  pytest -q tests/unit/test_cpp_thread_analysis.py \
            tests/unit/test_cpp_thread_contracts.py \
            tests/unit/test_cpp_thread_profiles.py \1
            tests/unit/test_cpp_thread_validation.py \0
      0      tests/unit/test_degraded_analysis.py
```

结果：聚焦 A3/A2 回归通过；最终统一入口共执行 529 个 Python 单元测试，全部通过。

```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace memory-order-analyzer-dev:a3 bash -lc \
  "cmake -S . -B /tmp/moa-a3-build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ && \
   cmake --build /tmp/moa-a3-build -j4 && \
   LLVM_PROFILE_FILE=/tmp/source.profraw /tmp/moa-a3-build/moa-unit --gtest_filter='SourceFacts.*'"
```

结果：25/25 `SourceFacts` 测试通过，包括 libstdc++ 的自由函数/lambda/成员函数/functor/move/join/detach/joinable、默认构造/临时对象/函数指针/虚调用保守路径、C pthread 不受影响，以及 libc++ inline namespace。

## 3. 四语言 truth

固定 suite 有 8 个 case；truth 与 captured logical projection 分文件保存，避免以分析输出生成期望。结果：exact `8/8`，expected=16，actual=16，FP=0，FN=0，unknown/abstention=`3/8`。

| 标准 | planned | completed | failed | unknown | abstention |
| --- | ---: | ---: | ---: | ---: | ---: |
| C11 | 1 | 1 | 0 | 0 | 0 |
| C17 | 1 | 1 | 0 | 0 | 0 |
| C++17 | 3 | 3 | 0 | 1 | 1 |
| C++20 | 3 | 3 | 0 | 2 | 2 |

C11/C17 case 验证直接 pthread 且不出现 `cpp-thread-*` 或 C++ 类型；C++17/libstdc++ 和 C++20/libc++ 真实 Clang AST compile-only 集成验证自由函数、成员函数、move、join。unknown 分别覆盖 ABI mismatch、functor overload 和 scope definition 缺失。A3 lifecycle 指标与 P4 risk TP/FP/FN 完全分开。

```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace \
  -e MOA_WORKER=/workspace/<quality>/build/moa-worker memory-order-analyzer-dev:a3 \
  pytest -q tests/integration/test_cpp_thread_lifecycle.py
```

结果：2/2 A3 独立集成测试通过。

## 4. cache、预算与性能

单元测试固定验证 cold run 为 2 misses、同请求 warm run 为 2 hits，cold/warm `semantic_digest` 相同；cache 损坏、依赖替换、key 冲突、transient/failed 发布均确定拒绝。TU、对象、实例、transition、relation、输出和墙钟边界分别断言 partial、已知事实与非空 frontier。

最终 cold/warm wall/CPU/peak RSS、输出字节和统一覆盖率数据写入 [CPP_THREAD_LIFECYCLE_ACCEPTANCE.json](CPP_THREAD_LIFECYCLE_ACCEPTANCE.json)，以机器文件为准。

## 5. 统一质量入口

最终命令必须使用全新目录：

```bash
docker run --rm -v "${PWD}:/workspace" -w /workspace memory-order-analyzer-dev:a3 \
  python3 -m memory_order_analyzer.quality \
    --output /workspace/reports/quality-a3-20260920-final --integration
```

统计包含全部 `python/memory_order_analyzer/**/*.py`、`doc/experiments/**/*.py` 和 `src` 自有 C/C++ 可执行源码/头文件。测试 harness、纯 fixture、第三方库和只生成的 protocol header 排除；自有业务、错误处理、质量逻辑不排除。单元与集成 profile 分开。

最终结果：C++ 单元 `91/91`、Python 单元 `529/529`、独立集成 `58/58`。整体行覆盖率 `10418/10577 = 98.50%`，分支覆盖率 `6195/6570 = 94.29%`；C++ 行/分支分别为 `3660/3683 = 99.38%`、`2952/3165 = 93.27%`，Python 行/分支分别为 `6758/6894 = 98.03%`、`3243/3405 = 95.24%`。全部受影响模块均通过逐模块 90% 门槛，其中最低项 `src/source_facts.cpp` 分支为 `454/502 = 90.44%`。精确 hit/total 及排除项见 acceptance 和覆盖率报告。

固定 C17 请求的 cold run 为 wall `0.073599s`、CPU `0.032255s`、peak RSS `28,995,584` bytes、输出 `1,185` bytes、cache `0 hit / 2 miss`；warm run 为 wall `0.037437s`、CPU `0.016968s`、peak RSS `29,536,256` bytes、输出 `1,185` bytes、cache `2 hit / 0 miss`。两次 `semantic_digest` 都是 `28f4fb0d1f5d0c7b68e1097fbd7dba3c03fbd47ab0491ee502e4bf23ed4c63e1`。

## 6. 边界复核

- P1–P4、A1、A2 原协议和 cache namespace 不变；A3 只新增 sidecar、graph/report 与 adapter。
- `std::thread` join 只有闭合 P3 执行顺序证据链才产生完成关系；detach、析构、joinable、源码顺序和 P2 order 不产生 HB。
- AST-only 不产生动态实例或正式风险结论。
- unknown RAII mutex 继续保留 `SynchronizationGap`。
- Windows/MSVC/clang-cl 和远程 ARM DevKit 不进入 required gate；验证无 SSH 或远程运行依赖。

<a id="doc-cpp-raii-synchronization-validation"></a>

## CPP_RAII_SYNCHRONIZATION_VALIDATION

## 1. 环境与可复现命令

验证日期为 2026-09-21，开发镜像为 `memory-order-analyzer-dev:a3`，Ubuntu 24.04，Clang/LLVM 21.1.8，GCC/G++ 13.3.0，libstdc++ `__GLIBCXX__=20240904`，libc++ `_LIBCPP_VERSION=210108`，Python 3.12.3。全部目标源码只进行 LibTooling 分析或 compile-only LLVM IR 生成；不链接、不运行目标程序，不连接 SSH/ARM DevKit，也不依赖 sibling archive。

```bash
docker run --rm --network none -v "$PWD:/workspace" -w /workspace \
  memory-order-analyzer-dev:a3 \
  python3 -m memory_order_analyzer.quality \
  --output reports/quality-a4-final-5 --integration
```

单独 A4 集成矩阵：

```bash
MOA_WORKER=/workspace/reports/quality-a4-final-5/build/moa-worker \
python3 -m pytest -q -p no:cacheprovider \
  tests/integration/test_cpp_raii_synchronization.py
```

## 2. Profile 实测

`tests/fixtures/cpp-raii-synchronization/profile_probe.cpp` 分别以 libstdc++ C++17/C++20 与 libc++ C++20 编译到 `-O0 -g -S -emit-llvm`。libstdc++ 实际出现 `_ZNSt5mutex4lockEv` / `_ZNSt5mutex6unlockEv`，libc++ 实际出现 `_ZNSt3__15mutex4lockEv` / `_ZNSt3__15mutex6unlockEv`；注册项同时锁定 target、DataLayout、ABI、异常、RTTI、header SHA-256 与 A3 lifecycle profile。集成测试重新生成 IR 并核对 wrapper，不从另一 vendor 推断。

## 3. 四语言 truth

固定语料位于 `tests/fixtures/cpp-raii-synchronization/`，覆盖 C11、C17、C++17、C++20 各 2 个计划用例。C 路径包含直接 pthread 同/不同 mutex 与无锁对照；C++ 路径包含 libstdc++ `lock_guard`/deferred `unique_lock`/`scoped_lock` 和 libc++ `lock_guard`。truth 分别计算 mutex、owner、thread/held-region、proof 与 unknown，不合并语言分母。

required gate 的固定结果记录在 [CPP_RAII_SYNCHRONIZATION_ACCEPTANCE.json](CPP_RAII_SYNCHRONIZATION_ACCEPTANCE.json)：8/8 个 truth case exact match，TP=25、FP=0、FN=0、abstention=0；C11、C17、C++17、C++20 各自 planned/completed/eligible 均为 2/2/2。真实 Clang source 提取和 libstdc++/libc++ compile-only probe 由独立集成测试覆盖。该矩阵验证受限语义，不代表全程序安全或通用 happens-before 正确性。

## 4. 回归、缓存与预算

本地锁定 `memory-model-ir-checker/samples/safe/03_pthread_mutex.cpp` 的最小副本与 SHA-256，日常测试不读取 sibling archive。完整 A4 证据存在时可在受限同 mutex 模型内消解；profile、路径、对象或线程证据不完整时保持 partial/unknown。单元测试覆盖 source-only、profile mismatch、ABI wrapper 漂移、对象歧义、unsupported tag、未闭合 region、状态/held-region 预算、损坏缓存、摘要漂移、future schema 和 0/2/1 退出码。

cold/warm 使用相同依赖与预算时 semantic digest 相同；缓存只改变 `hits/misses`。瞬态失败、timeout 和非确定 wall-clock 结果不得发布为长期缓存。

## 5. 单元覆盖率与排除项

质量入口统计所有 `python/memory_order_analyzer/*.py`、`doc/experiments/*.py` 和 `src` 下自有 C/C++ 可执行源码，未加载模块会导致失败。最终运行通过 92 个 C++ 单元测试、542 个 Python 单元测试和 62 个独立集成测试。整体 line/branch 为 11282/11463（98.42%）和 6717/7137（94.12%）；C++ 为 99.40%/93.11%，Python 为 97.94%/94.97%。最低的受影响模块 `src/source_facts.cpp` 仍达到 line 828/833（99.40%）与 branch 555/616（90.10%）。完整 hit/total、报告 SHA-256 和报告位置见 acceptance JSON。

排除项仅为测试 harness/纯 fixture、第三方依赖、生成协议头和按 hash 审核的纯声明头；没有排除自有 analyzer、错误处理、adapter、cache 或质量门禁逻辑。覆盖率只说明测试命中，不是检测准确率。

## 6. 结论边界

通过 gate 只说明：协议、profile、source/IR 候选、受限状态机、缓存/预算、四语言分母和已有回归按固定输入工作。A4 report 始终 `safety=not_established`，完整零候选、零 gap、退出 0 或受限 mutex proof 均不能解释为全程序安全。try/timed/recursive/robust mutex、condition variable、semaphore、rwlock、通用 points-to、通用 HB、fence 与 RMW/CAS 仍为明确 frontier。

## 阶段状态历史

P4 [detect-single-publication-risks] 已完成并归档。P5 `validate-and-scale-analysis` 已完成实现与质量验收、同步主规格并归档，即已完成、验证、同步并归档；结论仍为非全程序安全结论。当前状态以 OpenSpec 各 change 记录为准。
