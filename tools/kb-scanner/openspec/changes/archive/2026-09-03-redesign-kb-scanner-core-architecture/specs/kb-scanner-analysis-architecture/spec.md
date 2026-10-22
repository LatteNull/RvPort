## ADDED Requirements

### Requirement: 扫描器必须限定 C/C++ 迁移分析边界
KB Scanner SHALL 分析 C/C++ 软件从 x86 到目标 RISC-V 架构的可移植性，并 MUST NOT 将操作系统、内核、系统调用、驱动或硬件平台迁移纳入本模块的权威结论。

#### Scenario: 扫描普通 C/C++ 项目
- **WHEN** 调用方提交包含 C/C++ 源码和构建文件的项目
- **THEN** 扫描器 SHALL 对源码、构建、测试和打包层的架构依赖建立分析结果

#### Scenario: 遇到操作系统迁移内容
- **WHEN** 输入包含内核、系统调用或硬件板级适配内容
- **THEN** 扫描器 MUST NOT 把这些内容计入 C/C++ 项目迁移就绪度的确定性结论
- **AND** 扫描器 SHALL 将未负责的分析边界记录为 scope diagnostic 或外部能力引用

### Requirement: 扫描器必须执行分层分析管线
扫描器 SHALL 将工作区采集、输入前端、事实归一化、关系分析、局部检测、分类策略、项目评估和报告输出定义为独立阶段。

#### Scenario: 前端发现 x86 intrinsic
- **WHEN** C/C++ 前端发现一个由知识包确认的 x86 intrinsic 调用
- **THEN** 前端 SHALL 先产出带来源的规范化事实或观察
- **AND** 分类阶段 SHALL 结合目标可达性和策略产生 Finding
- **AND** 前端 MUST NOT 独立决定最终阻断级别

#### Scenario: 新增输入类型
- **WHEN** 后续 change 增加新的构建系统前端
- **THEN** 该前端 SHALL 通过统一事实和关系契约接入
- **AND** 报告层 MUST NOT 直接依赖该前端的私有解析对象

### Requirement: 扫描器必须保留现有 Clang/GCC x86 事实数据
重写后的扫描器 SHALL 继续使用 `clang-x86-entries.json` 和 `gcc-x86-entries.json`，并 SHALL 保留其 headers、intrinsics、builtins、vectorTypes、platformMacros 和 compilerFlags 分类内容及来源信息。

#### Scenario: 加载现有生成事实数据
- **WHEN** 扫描器加载 RISC-V porting 规则包
- **THEN** Knowledge Provider SHALL 读取现有 Clang 和 GCC JSON 文件
- **AND** 现有六类条目 SHALL 继续可供规则和检测器使用
- **AND** 重写 MUST NOT 要求先将两份文件转换为不兼容的新格式

#### Scenario: 规则引用 generatedSet
- **WHEN** 现有 YAML 规则通过 `generatedSet` 引用编译器派生集合
- **THEN** 重写后的扫描器 SHALL 保持该引用方式可用
- **AND** Clang/GCC 数据的合并与去重 MUST NOT 减少现有规则可命中的有效条目

#### Scenario: 合并重复条目
- **WHEN** 同一 x86 条目同时来自 Clang 和 GCC 数据
- **THEN** 扫描器 MAY 在运行时将其作为一个匹配项使用
- **AND** Knowledge Provider SHALL 保留该条目的来源集合
- **AND** 扫描器 MUST NOT 通过删除某一生成文件中的内容处理重复

#### Scenario: 未来重新生成事实数据
- **WHEN** 后续 change 重新采集或改变任一生成数据文件
- **THEN** 该 change SHALL 说明上游来源、生成脚本、分类差异和条目增减
- **AND** 该 change SHALL 通过现有 fixture 验证检测覆盖没有非预期退化

### Requirement: 扫描器必须保留原始证据及来源
每个可报告结论 SHALL 能追溯到一个或多个 Evidence；Evidence SHALL 包含输入位置、生产者、解析模式、知识来源和置信信息中的适用字段。

#### Scenario: Finding 被替代实现降噪
- **WHEN** 分类器确认 x86 命中存在可达的 RISC-V 或 portable 替代实现
- **THEN** 扫描器 SHALL 保留原始 x86 Evidence
- **AND** 扫描器 SHALL 记录用于降噪的替代实现 Evidence 和关系
- **AND** 扫描器 MUST NOT 通过删除原始证据实现抑制

#### Scenario: 输入无法完整解析
- **WHEN** 前端只能以文本模式或部分语法模式处理输入
- **THEN** Evidence SHALL 标明实际解析模式和相关 diagnostic
- **AND** 下游 MUST NOT 把部分解析当作完整语义证据

### Requirement: 扫描器必须使用统一关系模型表达跨输入语义
扫描器 SHALL 使用带类型的 Relation 表达宏展开、条件守卫、include、构建选择、测试覆盖、目标可达性和替代实现等跨事实连接。

#### Scenario: 宏跨文件间接触发 x86 intrinsic
- **WHEN** 一个自定义宏经由跨文件定义或展开最终引用 x86 intrinsic
- **THEN** 扫描器 SHALL 建立从使用点到宏定义再到 intrinsic 的可追溯关系链
- **AND** Finding SHALL 指向使用影响和定义源头，而不是产生互不关联的重复结论

#### Scenario: 关系无法确定
- **WHEN** 动态构建表达式或缺失输入阻止关系求值
- **THEN** 扫描器 SHALL 将关系或维度标记为 unknown/partial
- **AND** 扫描器 MUST NOT 猜测确定的目标可达性

### Requirement: 扫描器必须区分局部检测和关系分析
扫描器 SHALL 支持高确定性的 Local Detector 与需要多事实推理的 Relational Analyzer，并 SHALL 将两者的输出交给统一分类策略处理。

#### Scenario: 匹配编译器派生词典
- **WHEN** 源码包含知识包中的 x86 header、intrinsic、builtin、类型或编译参数
- **THEN** Local Detector SHALL 在不要求构建图完整的情况下产生 Observation
- **AND** 分类器 SHALL 根据可用关系补充可达性、阻断性和替代路径状态

#### Scenario: 分析源码选择
- **WHEN** 判断某架构源码是否进入目标构建需要组合变量赋值、条件和 include
- **THEN** 该判断 SHALL 由 Relational Analyzer 完成
- **AND** 单一文本命中 MUST NOT 被直接解释为最终被选源码

### Requirement: 扫描器必须规范化架构及特性知识
扫描器 SHALL 将架构 family、alias、feature 和实现角色规范化，并 SHALL 区分注释提示、模糊标识符候选和已确认代码依赖。

#### Scenario: 发现注释中的 x86 词
- **WHEN** 注释包含独立词形式的 x86、AVX 或 SSE 等架构词
- **THEN** 扫描器 SHALL 最多产生非阻断 hint
- **AND** 该 hint MUST NOT 单独证明代码存在 x86 依赖

#### Scenario: 发现模糊宏或枚举成员
- **WHEN** 代码标识符类似 `ENABLE_X86_FAST_PATH` 或 `X86_AESNI`
- **THEN** 扫描器 SHALL 产生带标识符上下文的候选 Observation
- **AND** 只有获得守卫、选择、调用或类型使用等进一步证据后才 SHALL 升级为可操作 Finding

### Requirement: 扫描器必须静态分析目标架构到产物的选择链
扫描器 SHALL 以统一选择关系静态表示当目标架构是 RISC-V 时，源码、目录、编译参数和依赖如何被选择，并 SHALL 将无法静态确定的部分保留为 unknown/partial。

#### Scenario: Makefile 根据架构变量选择源码
- **WHEN** Makefile 通过变量展开、条件或 include 选择架构相关源码
- **THEN** 扫描器 SHALL 建立 `架构选择来源 → 配置条件 → 候选产物` 的静态证据链
- **AND** 扫描器 SHALL 推导目标为 RISC-V 时选择的源码和参数

#### Scenario: 使用 uname 选择架构且存在 RISC-V 分支
- **WHEN** 构建逻辑使用 `uname -m` 选择架构相关源码
- **AND** 选择结构包含 RISC-V 分支
- **THEN** 扫描器 SHALL 将 `uname -m` 记录为架构 selector，并按 RISC-V 值分析对应分支
- **AND** 扫描器 MUST NOT 仅因使用 `uname -m` 生成 Finding
- **AND** 扫描器 MUST NOT 推导 RISC-V 会进入 x86 分支

#### Scenario: 使用 uname 选择架构但只有通用 fallback
- **WHEN** 构建逻辑使用 `uname -m` 选择架构相关源码
- **AND** 选择结构没有 RISC-V 专用分支但存在 generic、portable 或 fallback 分支
- **THEN** 扫描器 SHALL 将 x86 分支判定为对 RISC-V inactive
- **AND** 扫描器 SHALL 继续分析通用分支是否提供可移植实现

#### Scenario: 使用 uname 选择架构但缺少 RISC-V 和通用路径
- **WHEN** 构建逻辑使用 `uname -m` 选择架构相关源码
- **AND** 选择结构只有 x86 分支，没有 RISC-V、generic、portable 或 fallback 分支
- **THEN** 扫描器 SHALL 产生“缺少 RISC-V 选择路径”的迁移缺口
- **AND** 扫描器 MUST NOT 将该缺口描述为 RISC-V 错误选择了 x86 分支

#### Scenario: Autoconf 缺少 RISC-V triplet
- **WHEN** Autoconf 静态配置数据没有 riscv32/riscv64 架构识别路径
- **THEN** 扫描器 SHALL 产生可追溯的构建可移植性 Finding

### Requirement: 扫描器必须提供架构感知的测试分析
扫描器 SHALL 将测试识别为源码/构建实体的角色，并 SHALL 静态分析测试与架构实现、目标选择和覆盖之间的关系；实际测试执行结果不属于本模块。

#### Scenario: x86 测试已隔离
- **WHEN** x86 专用测试存在且不会进入 RISC-V 测试构建或执行路径
- **THEN** 扫描器 SHALL 将其分类为 `x86_test_guarded`
- **AND** 该结果 SHALL 为非阻断状态

#### Scenario: x86 测试阻塞 RISC-V
- **WHEN** 静态构建和测试选择关系表明含 x86 依赖的测试会进入 RISC-V 测试配置且没有兼容替代
- **THEN** 扫描器 SHALL 产生 `riscv_test_blocker`
- **AND** Finding SHALL 包含测试角色和目标可达性证据

#### Scenario: RISC-V 实现缺少等价测试
- **WHEN** x86 实现存在测试覆盖证据，而对应 RISC-V 实现没有可确认的测试覆盖
- **THEN** 扫描器 SHALL 产生 `riscv_test_coverage_gap`
- **AND** 在覆盖关系无法确定时 SHALL 显式报告 unknown，而不是断言缺失

### Requirement: 扫描器必须生成多维项目迁移评估
扫描器 SHALL 基于源码可达性、构建选择、架构依赖、替代实现、测试覆盖和输入完整性生成项目级 Assessment。

#### Scenario: 输出项目就绪度
- **WHEN** 扫描完成且存在足够证据
- **THEN** Assessment SHALL 从 `architecture_independent`、`x86_only`、`multiarch_without_riscv`、`partial_riscv`、`riscv_ready` 中选择有证据支持的状态
- **AND** Assessment SHALL 同时列出各维度状态、阻断项、缺口和未知项

#### Scenario: 声明项目静态 RISC-V ready
- **WHEN** Assessment 输出 `riscv_ready`
- **THEN** 该状态 SHALL 表示在当前静态输入覆盖范围内没有发现阻断迁移的选择路径或架构依赖
- **AND** 报告 SHALL 明确该状态不等价于真实 RISC-V 编译或测试成功

#### Scenario: 输入证据不足
- **WHEN** 缺少关键构建上下文或无法确认目标源码选择
- **THEN** 项目状态 SHALL 为 `unknown` 或带有明确 provisional/partial 语义
- **AND** 扫描器 MUST NOT 仅因没有发现 x86 命中而声明 `riscv_ready`

### Requirement: 扫描结果必须可复现并兼容现有输出契约
扫描器 SHALL 保持现有 `scan-result.json`、`scan-report.html` 和 `scan.log` 主输出契约，并 SHALL 在兼容位置记录扫描器、规则包、知识包、策略、扫描参数和输入覆盖诊断。

#### Scenario: 两次扫描使用不同知识包
- **WHEN** 两次扫描使用不同版本的编译器派生词典或架构知识包
- **THEN** 两份报告 SHALL 明确记录不同的知识包版本和来源
- **AND** 调用方 SHALL 能区分代码变化与知识变化造成的结果差异

#### Scenario: 重写后的扫描器输出结果
- **WHEN** 新实现完成任意阶段的内部重构
- **THEN** 扫描器 SHALL 继续输出 `schemaVersion: "1.0"`
- **AND** 输出 SHALL 保留 `tool`、`rulePack`、`project`、`summary`、`findings` 和 `diagnostics` 顶层结构
- **AND** 扫描器 MUST NOT 使用新的主 JSON 结构或专属关系结果文件替代现有结果

#### Scenario: 新分析信息需要写入结果
- **WHEN** Relation、Observation 或 Assessment 产生现有结果未明确表达的信息
- **THEN** 需要被当前后端保留的关系证据 SHALL 优先投影到现有 Finding 的 `trace`
- **AND** `build_context`、`alternative_impl`、`condition_macros` 等既有字段 SHALL 保持原名称、类型和语义
- **AND** 项目级 Assessment SHALL 投影到现有 `summary` 下的可选 `readiness` 子字段
- **AND** 必须新增字段时，该字段 SHALL 为可选增量字段
- **AND** 新增字段 MUST NOT 改变既有字段的名称、类型、必填性或语义

#### Scenario: 后端继续解析现有结果
- **WHEN** 重写后的 `scan-result.json` 被当前后端 KB scan result parser 导入
- **THEN** 后端 SHALL 无需切换 parser 或读取新的主结果文件
- **AND** 既有 finding、summary 和 artifact 导入行为 SHALL 保持兼容
- **AND** 该兼容性 SHALL 由 scanner fixture 与后端契约测试共同验证

### Requirement: 扫描器必须保留当前高价值 x86 检测资产
重写后的扫描器 SHALL 保持对当前已支持的 x86 header、intrinsic、builtin、SIMD 类型、平台宏、编译参数、汇编、CPU API、固定向量宽度、架构对齐、构建线索和 RPM 约束的等价或更强识别能力。

#### Scenario: 迁移现有 fixture
- **WHEN** 后续实现 change 将现有规则和 fixture 接入新架构
- **THEN** 当前被判定为可操作的关键 x86 样例 SHALL 继续产生等价或信息更完整的 Finding
- **AND** guarded、inactive、portable alternative 等既有降噪语义 MUST NOT 无证据退化为 blocker

### Requirement: 内存模型分析必须通过外部结果边界集成
KB Scanner MUST NOT 重复实现 RVWMO 并发语义分析；项目级报告 MAY 关联 memory-model IR checker 的版本化结果，并 SHALL 区分通过、失败和未执行。

#### Scenario: 外部内存模型结果可用
- **WHEN** 调用方提供可验证的 memory-model IR checker 产物
- **THEN** KB Scanner 报告 SHALL 引用工具版本、产物身份和摘要状态
- **AND** 项目 Assessment MAY 使用该状态作为独立维度

#### Scenario: 外部内存模型结果不可用
- **WHEN** 未提供外部产物或外部分析失败
- **THEN** 该维度 SHALL 标记为 unknown/not-run
- **AND** 扫描器 MUST NOT 将其解释为没有内存模型问题
