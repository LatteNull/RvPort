## ADDED Requirements

### Requirement: 局部风险与影响完整性必须独立判定
Classification SHALL 分开表达已确认执行架构依赖、目标可达性、结论完整性和迁移优先级。完整互斥排除 SHALL 保持 guarded_inactive；未排除的确认 intrinsic/向量类型/x86 指令或参数/精确知识专用头文件 SHALL 支持 high 风险，即使目标影响仍 unknown/partial。纯架构候选 SHALL 保持未决而非确认为依赖；unknown MUST NOT 自动表示低风险或 complete。Classification MUST NOT 改写或丢弃原始事实。

#### Scenario: 专用头文件内容未解析
- **WHEN** immintrin.h 已精确命中 x86 知识，但 include 内容或目标选择尚未解析
- **THEN** 已确认架构依赖 SHALL 保留，局部风险 SHALL 为 high，适用性缺失 SHALL 明确 partial/unknown 且不宣称 blocking
- **AND** 无关 unresolved include 不得抹掉此知识匹配或其他独立完整 proof

#### Scenario: 架构名称和注释
- **WHEN** 只有宏/枚举/identifier 候选，或只有注释线索
- **THEN** 未决候选 SHALL 为 medium 待核查且 unknown/ambiguous，纯注释 SHALL 保持 info
- **AND** MUST NOT 因同名或附近存在 x86 实现将其直接升级为 blocker

#### Scenario: 排除证据完整
- **WHEN** 当前 occurrence/configuration 的完整 proof 证明 x86 路径被目标互斥排除
- **THEN** SHALL 保持 low/inactive 且非 actionable、非 blocking
- **AND** 不得用项目配置提前失败代替此排除证明

### Requirement: 显式配置拒绝只有闭合且必需才构成阻断
Classifier SHALL 对具有完整入口、目标条件、执行顺序、终止依据和必需范围的 CMake 拒绝 proof 给出该范围 blocking_issue/high；其他 missing_riscv_selection_path、软依赖和可选模块 MUST NOT 被一律升级。Assessment SHALL 按 proof 范围汇总，不以 high 数量替代 blocker/readiness 证明，不因缺失证明推断 ready。

#### Scenario: 必需入口拒绝目标
- **WHEN** 完整 CMake proof 表明项目必需入口对 RISC-V 到达 FATAL_ERROR
- **THEN** Classifier SHALL 产生 complete 的配置阻断，Assessment SHALL 记录其配置范围及依据
- **AND** 结论 SHALL 声明静态配置拒绝，不宣称执行过编译

#### Scenario: 高风险但未证明必选
- **WHEN** 局部 AVX 执行依赖确认而 target/source 关系未闭合
- **THEN** SHALL 保持 high 和可核查处理的 actionable，同时 blocking=false，status 为 partial/unknown
- **AND** summary MUST NOT 将其单凭 severity 计为已确认阻断
