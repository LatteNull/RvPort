# KB Scanner C/C++ Frontends Specification

## Purpose

定义 KB Scanner 正式 C/C++ workspace、Tree-sitter baseline、可选 libclang enrichment、compilation database 与参数安全合同，使前端能够产生稳定、可追溯的 core Evidence，同时保持 legacy CLI、知识事实和报告兼容边界。

## Requirements

### Requirement: C/C++ Workspace 必须安全且确定地发现输入
扫描器 SHALL 通过正式 Workspace Collector 发现受支持的 C/C++ 源文件、头文件和测试源码，SHALL 遵守现有 language、exclude 和 exclude-path 输入边界，并 MUST NOT 跟随逃逸 workspace 的路径或把机器绝对路径写入稳定身份。

#### Scenario: 扫描项目目录
- **WHEN** 输入目录包含受支持的 C/C++ 文件以及被排除目录和其他语言文件
- **THEN** collector SHALL 只返回过滤后受支持文件的 POSIX 风格项目相对路径
- **AND** 返回顺序 SHALL 在相同输入上保持确定

#### Scenario: 扫描单个源码文件
- **WHEN** CLI 输入指向一个受支持的 C/C++ 文件
- **THEN** workspace root SHALL 使用该文件的父目录
- **AND** snapshot SHALL 只包含该文件的相对路径

#### Scenario: 路径逃逸 workspace
- **WHEN** symlink 或规范化路径指向 workspace 外部
- **THEN** collector MUST NOT 读取该目标作为项目源码
- **AND** scanner SHALL 产生结构化 Diagnostic 而不是把绝对路径写入 Entity 或 Evidence ID

### Requirement: Tree-sitter 必须提供全部 C/C++ 文件的基础 Evidence
正式 C/C++ Frontend SHALL 对每个可读输入运行 Tree-sitter C 或 C++ grammar，SHALL 提取带 source span 的预处理、include、宏、调用、类型、模板、constexpr、inline asm 和按配置启用的 comment Evidence，并 MUST NOT 执行预处理器或项目代码。

#### Scenario: 没有 compilation database
- **WHEN** workspace 包含 C/C++ 文件但 ScanContext 没有 compilation context
- **THEN** Frontend SHALL 仍产生 source file Entity 和 Tree-sitter baseline Evidence
- **AND** Clang 才能确认的语义 SHALL 保持缺失或 unknown，不得解释为没有迁移问题

#### Scenario: 解析 C 与 C++ 构造
- **WHEN** C/C++ 输入包含条件预处理、宏、函数调用、类型、模板、`if constexpr` 或 inline asm
- **THEN** Frontend SHALL 为适用构造产生稳定 kind/value 和项目相对 SourceSpan
- **AND** Evidence SHALL 标记实际 grammar producer、版本、parse mode 和 confidence

#### Scenario: 注释线索关闭
- **WHEN** ScanContext 的 comment hint 选项关闭
- **THEN** Frontend MUST NOT 产生 comment Evidence
- **AND** 其他语法 Evidence SHALL 不受影响

### Requirement: 歧义头文件语言选择必须可解释且可重复
对于无法由后缀或直接 compilation context 唯一确定为 C/C++ 的头文件，Frontend SHALL 使用固定 grammar 候选和错误评分策略选择 baseline，并 SHALL 记录所选语言及其推断来源。

#### Scenario: 头文件缺少直接语言上下文
- **WHEN** `.h` 或 `.inc` 文件没有直接 compilation entry
- **THEN** Frontend SHALL 按固定顺序尝试适用的 C 与 C++ grammar
- **AND** 相同文件内容和版本 SHALL 选择相同结果并产生相同 Evidence 身份

#### Scenario: 两种 grammar 都不能完整解析
- **WHEN** C 与 C++ grammar 均返回 ERROR 或 MISSING 节点
- **THEN** Frontend SHALL 保留错误更少结果中可恢复的 Evidence
- **AND** 对应文件 SHALL 产生 partial Diagnostic 而不是终止项目 Frontend

### Requirement: Frontend Evidence 必须使用 core 合同和稳定 provenance
正式 Frontend SHALL 只返回 core `Entity`、`Evidence`、结构化 `Diagnostic` 和 `StageResult[FrontendSnapshot]`，MUST NOT 暴露 Tree-sitter Node/Tree、Clang Cursor/TranslationUnit、technology spike DTO 或 legacy DTO。

#### Scenario: 基础前端产生事实
- **WHEN** Tree-sitter 从项目源码发现一个语法事实
- **THEN** Evidence SHALL 引用有效 source file Entity，并包含项目相对 SourceSpan、producer/version、parse mode 和 confidence
- **AND** ID SHALL 由规范化领域身份材料生成完整小写 SHA-256

#### Scenario: 相同输入重复分析
- **WHEN** 相同 scanner/parser 版本、源码、workspace 和 compilation context 重复运行 Frontend
- **THEN** Entity/Evidence ID、排序和 Diagnostic 顺序 SHALL 保持一致
- **AND** 身份材料 MUST NOT 包含绝对目录、随机值、对象地址或时间

### Requirement: Compilation database 必须纯读取并直接产生 core context
正式 compilation database reader SHALL 在不执行 command 的前提下解析 JSON entry，并 SHALL 直接产生 core `CompilationUnitContext` 和结构化 Diagnostic；它 MUST NOT 使用或返回 legacy `CompileCommandContext`。

#### Scenario: 同一源码具有多个 command entry
- **WHEN** `compile_commands.json` 为同一 source file 提供不同 defines 或参数的多个 entry
- **THEN** reader SHALL 保留每个有效 entry 及其稳定 context identity
- **AND** Frontend SHALL 能分别保留不同 compilation context 下的 provenance

#### Scenario: compilation database 部分无效
- **WHEN** 一部分 entry 缺少 file、无法解析或逃逸允许的项目范围
- **THEN** reader SHALL 为无效 entry 产生 Diagnostic 并继续返回其他有效 entry
- **AND** scanner MUST NOT 执行原始 command 来推断缺失信息

#### Scenario: compilation database 不存在或整体无效
- **WHEN** 没有可用 compilation context
- **THEN** Frontend SHALL 继续运行 Tree-sitter baseline
- **AND** 需要 compilation context 的增强状态 SHALL 为 unavailable/partial，而不是成功确认 RISC-V ready

### Requirement: Clang 增强必须安全、可选且逐 TU 降级
存在有效 compilation context 时，Frontend SHALL 使用版本匹配的 libclang detailed preprocessing record 补充项目源码中的宏定义、宏展开、include 和稳定可得的语义 Evidence；Clang 增强 MUST NOT 替代 Tree-sitter baseline。

#### Scenario: Clang 增强成功
- **WHEN** translation unit 的安全参数足以让 libclang 完成解析
- **THEN** Frontend SHALL 产生带 Clang producer/version 和 compilation context identity 的增强 Evidence
- **AND** Evidence location SHALL 限于 workspace 内项目源码

#### Scenario: 单个 translation unit 失败
- **WHEN** 缺失头文件、参数不兼容或 libclang diagnostic 使一个 TU 无法完整分析
- **THEN** Frontend SHALL 记录该 TU 的 partial Diagnostic 并继续其他 TU
- **AND** 已产生的 Tree-sitter Evidence MUST NOT 被删除

#### Scenario: 文件没有 compilation context
- **WHEN** workspace 文件没有匹配的 command entry
- **THEN** Frontend SHALL 不调用 Clang 处理该文件
- **AND** 该文件 SHALL 继续保留 baseline Evidence

### Requirement: Clang 参数必须遵循纯解析 allowlist
Clang adapter SHALL 只接受经过审计的语言、宏、include、target、sysroot 和目标特性解析参数，MUST 拒绝 plugin、response file、PCH/module、输出产物、透传及其他未允许参数，并 MUST NOT 启动 compiler executable。

#### Scenario: command 包含可执行扩展
- **WHEN** compilation entry 包含 `-Xclang`、plugin、load 或 response-file 参数
- **THEN** adapter SHALL 拒绝相关参数并产生带 entry identity 的 Diagnostic
- **AND** 相关 plugin、response file 或命令 MUST NOT 被加载或执行

#### Scenario: command 请求加载缓存或写文件
- **WHEN** compilation entry 包含 PCH/module/module-map、`-o`、dependency、diagnostic、trace 或 save-temps 参数
- **THEN** adapter SHALL 从传给 libclang 的参数中移除整个参数组
- **AND** marker 文件和 workspace 内容 SHALL 保持不变

#### Scenario: command 同时包含安全与不安全参数
- **WHEN** compilation entry 的语言、define/include 参数有效但同时存在被拒绝参数
- **THEN** adapter MAY 使用剩余安全子集进行 enrichment
- **AND** StageResult SHALL 保留拒绝 Diagnostic，不得把清洗过程静默视为完整 context

### Requirement: 不同 Frontend producer 的证据不得在本阶段丢失
Frontend SHALL 保留 Tree-sitter 和 Clang 各自的 Evidence 身份，只 SHALL 去除同一 producer 和同一 compilation context 内的完全重复项；跨 producer 的关联或合并必须留给后续 Normalizer。

#### Scenario: 两个 producer 发现同一事实
- **WHEN** Tree-sitter 与 Clang 在同一项目相对 span 发现相同 kind/value
- **THEN** FrontendSnapshot SHALL 保留两个 producer-specific Evidence
- **AND** 两条 Evidence SHALL 各自可追溯到 parser 版本和 parse mode

#### Scenario: 同一 producer 重复报告事实
- **WHEN** 单次 adapter 遍历重复产生完全相同的 source、span、kind、value 和 context
- **THEN** Frontend SHALL 确定性去除该重复项
- **AND** 输出排序 SHALL 不依赖 parser 对象遍历的非确定顺序

### Requirement: Frontend 不得承担检测、可达性或报告职责
正式 C/C++ Frontend SHALL 只恢复源码和 compilation context 中可观察的事实，MUST NOT 加载 x86 知识集、生成最终 Finding、判断 RISC-V 分支可达性、声明 readiness 或写入正式 artifact。

#### Scenario: 源码包含 x86 宏或 intrinsic
- **WHEN** Frontend 遇到 `__x86_64__`、SSE/AVX intrinsic 或相关注释
- **THEN** Frontend SHALL 只产生对应语法、标识符或 comment Evidence
- **AND** blocking、inactive、hint 或 portability gap 分类 SHALL 留给后续 Detector/Classifier

#### Scenario: 源码包含架构 selector
- **WHEN** C/C++ 条件分支包含 RISC-V、x86、generic 或 fallback selector
- **THEN** Frontend SHALL 保留各分支和条件文本而不求值目标可达性
- **AND** scanner MUST NOT 在本阶段建模交叉编译环境选错分支

### Requirement: 正式 Frontend 必须在独立容器中保持兼容边界
Frontend 实现和测试 SHALL 只使用独立 `kb-scanner-test` 容器中的锁定 Tree-sitter 与 Clang 依赖；本 change MUST NOT 修改生产镜像、根 Compose、旧结果结构或既有知识数据。

#### Scenario: 验证正式 Frontend
- **WHEN** 开发者运行本 change 的正式测试
- **THEN** 全部 parser、降级、安全和兼容测试 SHALL 通过 `compose.test.yml` 执行
- **AND** 宿主机 MUST NOT 安装或执行 scanner Python/Clang 依赖

#### Scenario: 回归默认 CLI
- **WHEN** 新 Frontend 已作为 staged 可注入组件存在
- **THEN** 当前默认 CLI SHALL 继续产生 `schemaVersion: "1.0"`、现有顶层字段和三个 artifact
- **AND** Clang/GCC 事实文件、YAML、`generatedSet` 和现有 Finding 语义 SHALL 保持不变

### Requirement: 正式 C/C++ Frontend 必须具有逐模块隔离单元测试
正式 C/C++ frontend 的 vocabulary、workspace、compilation database、Clang arguments、Tree-sitter adapter、Clang adapter 和 composite frontend SHALL 各自具有可独立运行的单元测试，测试 SHALL 隔离文件系统、parser、libclang 和下游阶段边界，并 MUST NOT 以真实集成测试数量代替模块级断言。

#### Scenario: 纯转换与确定性逻辑
- **WHEN** 单元测试验证 Evidence/Entity 构造、排序、路径规范化、参数分类或 context identity
- **THEN** 测试 SHALL 直接断言有效、边界和无效输入的返回值、稳定身份及 Diagnostic
- **AND** 测试 MUST NOT 要求真实 Tree-sitter parse、libclang translation unit、compiler executable 或项目命令

#### Scenario: Adapter 异常和降级路径
- **WHEN** Tree-sitter 或 Clang 初始化、解析、游标访问、位置转换或输入读取发生异常
- **THEN** 单元测试 SHALL 通过 mock/fake 精确触发对应分支并断言 complete/partial/unavailable/failed 状态
- **AND** 测试 SHALL 验证可恢复 Evidence、其他文件或其他 compilation context 不被删除

#### Scenario: Composite Frontend 聚合结果
- **WHEN** fake adapters 返回 complete、partial、unavailable、failed、重复 Diagnostic 或非法 Evidence 引用的组合
- **THEN** 单元测试 SHALL 验证状态传播、Diagnostic 稳定去重、Entity/Evidence 引用完整性和 producer/context 保留
- **AND** Frontend MUST NOT 因测试便利而引入 legacy DTO、全局 registry 或隐式 parser 状态

### Requirement: Frontend 测试层级与覆盖度必须可审计
测试仓库 SHALL 明确区分 frontend unit、parser/component、staged integration 和 compatibility contract 层级，SHALL 为每个正式 frontend 模块维护测试映射，并 SHALL 在独立测试容器中对隔离单元测试执行可重复的行与分支覆盖度门槛。

#### Scenario: 检查测试清单
- **WHEN** 新增、删除或重命名 `kb_scanner/frontends/cpp` 正式模块
- **THEN** 测试清单 SHALL 映射对应单元测试和适用的组件/集成测试
- **AND** 缺失模块映射 SHALL 使测试容器失败，而不是只更新总测试数量

#### Scenario: 运行隔离单元测试覆盖度
- **WHEN** `kb-scanner-test` 容器执行正式验证
- **THEN** 容器 SHALL 单独运行 frontend unit suite 并报告目标包的行覆盖率和分支覆盖率
- **AND** 任一覆盖率低于仓库中固定门槛 SHALL 产生非零退出码

#### Scenario: 运行完整回归
- **WHEN** frontend unit suite 和覆盖门槛通过
- **THEN** 同一独立测试环境 SHALL 继续运行既有 parser/component、libclang integration、staged integration 和 legacy compatibility tests
- **AND** 测试输出 SHALL 分别显示单元覆盖结果与完整测试结果，不得只报告一个合并数量

### Requirement: 单元测试加固不得改变扫描兼容与执行边界
本 change SHALL 保持正式 frontend 的外部行为、默认 legacy CLI、现有报告合同和知识事实资产不变；为测试隔离增加的 seam MUST 是显式、局部且行为保持不变的依赖注入，所有新增测试依赖 MUST 仅存在于独立 `kb-scanner-test` 容器。

#### Scenario: 增加可测试性 seam
- **WHEN** 难以在不加载真实 parser 或 libclang 的情况下触发异常分支
- **THEN** 实现 MAY 增加构造参数、私有 loader 或 protocol 形式的显式 seam
- **AND** 默认构造行为、core 返回类型、Evidence identity、Diagnostic 和排序 MUST 保持不变

#### Scenario: 验证兼容资产
- **WHEN** 单元测试加固完成并运行完整回归
- **THEN** `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义和 `scan-result.json`、`scan-report.html`、`scan.log` SHALL 保持不变
- **AND** Clang/GCC 两份事实 JSON 的内容、六类计数、source、SHA-256 及 YAML `generatedSet` 引用 SHALL 保持不变

#### Scenario: 保持静态分析和容器边界
- **WHEN** 测试构造 compilation command、危险参数或 C/C++ fixture
- **THEN** scanner 和测试 MUST NOT 执行 compiler、构建、配置、plugin、response file、项目测试或真实 RISC-V 编译
- **AND** 测试依赖 MUST NOT 安装到宿主机、生产镜像或根 Compose 服务

### Requirement: Tree-sitter 源位置必须只由稳定字节偏移计算
正式 C/C++ Frontend SHALL 为每个源文件从原始 bytes 一次构建可复用的位置索引，并 SHALL 仅使用 Tree-sitter Node 的 `start_byte`/`end_byte` 计算 SourceLocation、SourceSpan、枚举 guard metadata 与 partial-parse Diagnostic 位置。生产扫描路径 MUST NOT 读取 `start_point` 或 `end_point`，行号和列号 SHALL 保持 1-based，列号 SHALL 表示 UTF-8 字节列。

#### Scenario: 普通节点与超长单行节点定位
- **WHEN** Tree-sitter 节点位于普通或超长单行源码中
- **THEN** Frontend SHALL 由 byte offset 得到确定的起止行列并产生 Evidence
- **AND** fake Node 的 Point getter 即使抛出异常也 MUST NOT 被访问

#### Scenario: 多行与多字节源码定位
- **WHEN** 源码包含 LF、CRLF、UTF-8 多字节字符、空行或 EOF 边界
- **THEN** SourceSpan SHALL 使用 `\n` 建立行边界并按原始 bytes 计算 1-based 列号
- **AND** 相同 bytes 与 byte range SHALL 始终得到相同位置

#### Scenario: 错误恢复节点定位
- **WHEN** grammar 返回具有合法 byte range 的 ERROR 或 MISSING node
- **THEN** Frontend SHALL 由 byte offset 产生 partial Diagnostic 和可恢复 Evidence 的位置
- **AND** 它 MUST NOT 读取 Point 或因错误节点终止整个扫描进程

#### Scenario: 无效字节范围
- **WHEN** adapter 收到负数、逆序或超出 source 长度的 byte range
- **THEN** Frontend SHALL 产生结构化 Diagnostic 或受控失败
- **AND** 它 MUST NOT 静默截断为看似有效的位置或导致原生进程崩溃

### Requirement: Tree-sitter 原生对象必须限制在单文件解析会话内
Tree-sitter adapter SHALL 在单个 parse candidate 的全部遍历期间保持 Tree 有效，但 MUST NOT 将 Parser、Tree 或 Node 写入 FrontendSnapshot、Evidence、Diagnostic、跨阶段 DTO 或 adapter 外缓存。跨遍历保存的数据 SHALL 是 Python 自有的字符串、整数、byte range、稳定 ID 或其不可变集合。

#### Scenario: 枚举分析需要多次遍历
- **WHEN** enum declaration pass 与 reference pass 需要检查同一语法树
- **THEN** adapter SHALL 在 Tree 存活时从 root 重新遍历或消费轻量快照
- **AND** 它 MUST NOT 为后续阶段持有整棵树的 Node tuple

#### Scenario: 文件分析结束
- **WHEN** parse candidate 已转换成 Evidence 与 Diagnostic
- **THEN** 返回值 SHALL 只包含 core 合同和 Python 自有基础数据
- **AND** 任何下游对象 MUST NOT 依赖原生 Node 生命周期

### Requirement: C/C++ Frontend 必须提供可定位的 declaration attribute Evidence
正式 Tree-sitter C/C++ Frontend SHALL 为可稳定识别的 GNU、MSVC 或 C++ declaration/target/vector-size attribute 产生有界、带项目相对 SourceSpan 的 `declaration_attribute` Evidence，并 MUST NOT 在 Frontend 中判断其架构影响、严重程度或阻断状态。

#### Scenario: 声明包含 x86 target attribute
- **WHEN** C/C++ 声明包含可由 grammar 定位的 target、target_clones、vector_size 或同类 attribute
- **THEN** Frontend SHALL 产生包含语法文本、node type、language、producer/version、parse mode 和 confidence 的 declaration attribute Evidence
- **AND** Local Detector SHALL 能在不重新读取源码的情况下消费该 Evidence

#### Scenario: attribute 节点不完整
- **WHEN** parser 恢复出 attribute 但对应语法树包含 ERROR 或 MISSING
- **THEN** Frontend SHALL 保留可定位的 partial Evidence 并降低 confidence
- **AND** 缺失内容 MUST NOT 被补猜为特定 x86 target 或固定向量宽度

#### Scenario: 普通声明没有架构 attribute
- **WHEN** declaration 不包含可稳定识别的 attribute 节点
- **THEN** Frontend MUST NOT 为了 Local Detector 方便而生成整文件或所有 identifier 的宽泛 Evidence

#### Scenario: 超长单行语法节点需要稳定 SourceSpan
- **WHEN** Tree-sitter 节点跨越普通或超长源码行，且原生 Point 字段读取可能破坏进程内存
- **THEN** Frontend SHALL 只从节点的 start/end byte offset 和该文件的位置索引构造 SourceLocation
- **AND** SourceSpan SHALL 保持确定且生产路径 MUST NOT 读取 start/end Point

### Requirement: C/C++ Frontend 必须结构化保留宏参数与 replacement token
正式 Tree-sitter C/C++ Frontend SHALL 在保留现有 `macro_definition.value` 和 `macro_expansion.value` 兼容语义的同时，为函数式宏参数和 replacement body 中有意义的 token 产生带精确项目相对 SourceSpan、所属 definition Evidence ID、稳定序号和 token role 的 scanner-owned Evidence；macro definition MUST NOT 被表达为 call expression 或 macro invocation。

#### Scenario: 解析函数式宏定义
- **WHEN** `preproc_function_def` 包含参数列表和 replacement body
- **THEN** Frontend SHALL 产生一个 `macro_definition`、逐参数 `macro_parameter` 和逐 token `macro_replacement_token` Evidence
- **AND** 附属 Evidence SHALL 可由 definition Evidence ID 确定性关联并保持源码顺序

#### Scenario: replacement body 调用 intrinsic
- **WHEN** 函数式宏 replacement 中出现形如 identifier 后接调用括号的 intrinsic 引用
- **THEN** identifier token SHALL 具有独立 SourceSpan 和 token role
- **AND** Frontend MUST NOT 把宏定义节点本身计为 call expression

#### Scenario: 宏使用出现在定义之外
- **WHEN** 已知宏名称在非 definition ancestor 的源码位置被使用
- **THEN** Frontend SHALL 继续产生独立 `macro_expansion` Evidence
- **AND** definition、replacement token 与 expansion 的 Evidence kind 和 ID SHALL 互不混淆

#### Scenario: replacement 使用不支持的预处理语义
- **WHEN** replacement 包含 token pasting、stringification、可变参数或 parser 恢复节点
- **THEN** Frontend SHALL 保留能够准确定位的原始 token 并产生 partial Diagnostic 或 metadata
- **AND** Frontend MUST NOT 猜测完整展开结果

### Requirement: 宏结构化 Evidence 必须由 Normalizer 无损承接
CppEvidenceNormalizer SHALL 将 `macro_parameter` 和 `macro_replacement_token` 转换为稳定 `macro_parameter` 与 `macro_replacement` NormalizedFact，并 SHALL 保留原 definition Evidence 引用、token 序号、role、producer、compilation context、confidence 和 SourceSpan。

#### Scenario: 两个 producer 提供同一 replacement token
- **WHEN** Tree-sitter 与 Clang 对同一 definition、位置和 canonical token 提供 Evidence
- **THEN** Normalizer SHALL 合并为一个稳定事实并保留全部 Evidence/producer provenance
- **AND** 可选 Clang 是否存在 MUST NOT 改变该事实的语义 identity

#### Scenario: replacement Evidence 引用未知 definition
- **WHEN** 一个 macro parameter/replacement Evidence 引用 FrontendSnapshot 中不存在的 definition Evidence ID
- **THEN** Normalizer SHALL 返回 failed Diagnostic
- **AND** 无效事实 MUST NOT 进入 NormalizedSnapshot

### Requirement: C/C++ Frontend 必须提供有界且可定位的 enum 语义 Evidence
正式 Tree-sitter C/C++ Frontend SHALL 为 enum/enum class 声明、单个枚举成员声明、可由语法和局部符号绑定的枚举成员引用产生项目相对、精确 token span 的 scanner-owned Evidence。Frontend SHALL 仅在 `if`、`if constexpr`、`switch`/`case` guard 内存在上述 enum member reference 时产生与引用显式关联的 condition Evidence，MUST NOT 将所有 condition clause 或 case statement 宽泛转换为 selection Evidence。可选 Clang enrichment SHALL 在 compilation context 可用时使用 compiler cursor reference 补充跨文件 binding；Frontend MUST NOT 为此生成所有 identifier Evidence、读取 knowledge 或判断迁移影响。

#### Scenario: C++ scoped enum 用于 if constexpr
- **WHEN** C++ 源码声明 `enum class Backend { scalar, avx2 }` 并在 `if constexpr` 中引用 `Backend::avx2`
- **THEN** Frontend SHALL 分别产生 enum declaration、两个 member declaration、精确的 member reference 和 condition Evidence
- **AND** reference SHALL 可追溯到唯一 declaration，condition SHALL 引用该 reference，且每个对象保留自己的 byte-derived token span、producer、language 和 binding status

#### Scenario: C enum 用于 switch case
- **WHEN** C 源码声明 enum member 并在 switch/case 中使用该成员
- **THEN** Frontend SHALL 产生 unscoped member declaration/reference Evidence，并标记 `switch_case` reference context
- **AND** 它 MUST NOT 把同名普通变量、函数调用或字符串解释为 enum reference

#### Scenario: 普通 case 与条件不产生选择 Evidence
- **WHEN** 源码包含 `case '0'`、`case 0`、没有可验证 enum declaration binding 的状态常量或不引用枚举成员的普通 if
- **THEN** Frontend MUST NOT 为这些节点产生 `selection_condition` 或 `constexpr_condition` Evidence
- **AND** 这些节点 MUST NOT 进入架构枚举证据链

#### Scenario: 枚举引用跨文件或重名
- **WHEN** Tree-sitter 基线看到跨文件或多个非限定同名 member，且无法建立唯一 declaration binding
- **THEN** Frontend SHALL 保留可定位 reference candidate 并标记 partial/ambiguous 及全部可验证候选
- **AND** 它 MUST NOT 按文件或遍历顺序选择一个 declaration

#### Scenario: Clang 提供枚举语义绑定
- **WHEN** compilation context 可用且 Clang cursor 将 `DECL_REF_EXPR` 解析到 `ENUM_CONSTANT_DECL`
- **THEN** Clang enrichment SHALL 产生带 compilation context 和 declaration identity 的高置信 member reference Evidence
- **AND** Clang 不可用或 TU 有错误时 SHALL 降级为已有 Tree-sitter Evidence，而不是丢弃或伪造绑定

#### Scenario: 普通代码不产生 identifier sweep
- **WHEN** 普通声明、变量、注释或字符串包含 x86/AVX 样式文本但不位于 enum declaration/reference 语义中
- **THEN** enum Frontend MUST NOT 为其产生 enum Evidence
- **AND** 现有 comment hint 与其他结构 Evidence SHALL 继续走各自独立路径

#### Scenario: 枚举或条件语法不完整
- **WHEN** parser recovery 得到缺失 member、condition 或无法闭合的 enum 节点
- **THEN** Frontend SHALL 保留能够准确定位的局部 Evidence并降低 confidence、产生结构化 Diagnostic
- **AND** 缺失名称、声明绑定或条件值 MUST NOT 被补猜

### Requirement: Inline asm Evidence 必须以完整最外层语句为边界
正式 Tree-sitter C/C++ Frontend SHALL 为每条可定位的 inline asm 源码语句最多产生一个 `inline_asm` Evidence，value 和 SourceSpan SHALL 覆盖完整最外层 asm 构造。具有 inline asm ancestor 的 qualifier、input/output operand、clobber、constraint 或其他嵌套 asm node MUST NOT 独立产生 `inline_asm` Evidence。

#### Scenario: GNU asm 包含多个 operand
- **WHEN** 一条 GNU asm 同时包含 `volatile`、输出 operand、输入 operand 和 clobber
- **THEN** Frontend SHALL 产生一个覆盖完整语句的 `inline_asm` Evidence
- **AND** `__asm__`、`volatile`、constraint 和单个 operand MUST NOT 形成额外 inline asm Evidence

#### Scenario: 同一行包含两条独立 asm
- **WHEN** 同一源码行存在两个具有不同 byte span 的独立 asm 语句
- **THEN** Frontend SHALL 为两个最外层语句分别产生 Evidence
- **AND** 去重 MUST NOT 只按行号或文本合并它们

#### Scenario: asm 节点发生错误恢复
- **WHEN** grammar 返回可定位但包含 ERROR/MISSING 的最外层 asm 构造
- **THEN** Frontend SHALL 保留至多一个 partial Evidence 并产生结构化 Diagnostic
- **AND** 它 MUST NOT 恢复对所有名称包含 `asm` 的节点进行宽泛遍历

### Requirement: Declaration attribute Evidence 必须保留属性语义边界
Frontend SHALL 只把 grammar 明确认定的完整 declaration attribute 构造表达为 `declaration_attribute` Evidence，并 SHALL 保留完整属性文本和 byte-derived SourceSpan；它 MUST NOT 为属性名称、参数或嵌套表达式分别生成同 kind Evidence。Frontend 不负责判断属性是否与 x86 有关。

#### Scenario: target attribute 包含 feature
- **WHEN** 声明包含 `target("avx2")` 或等价完整 target attribute
- **THEN** Frontend SHALL 产生一个完整 declaration attribute Evidence
- **AND** feature token SHALL 由后续 Detector 在该 Evidence 内匹配

#### Scenario: 通用 no_sanitize attribute
- **WHEN** 声明包含 `no_sanitize("memory")`
- **THEN** Frontend MAY 产生一个语法正确的完整 declaration attribute Evidence
- **AND** 它 MUST NOT 在 Frontend 被标记为架构候选或 x86 依赖

### Requirement: 前端必须提供有界函数身份和属性归属而不破坏原始事实

C/C++ Frontend SHALL 在现有授权输入和解析生命周期内恢复相关非模板自由函数的声明/定义描述、限定作用域、签名形状、linkage、属性 owner、真实 body 范围及配置来源。完整 declaration_attribute Evidence 的值、位置和原有身份 SHALL 保留；新增结构 MUST NOT 将普通 identifier 或所有普通函数转为迁移问题。

#### Scenario: 属性位于不同合法语法位置
- **WHEN** target/target_clones 属性在返回类型前、声明符后或标准属性列表中且 grammar 能准确识别
- **THEN** SHALL 按语法结构绑定实际函数并保留名称、属性、声明及定义各自位置
- **AND** MUST NOT 按最近文本、相同行号或裸函数名猜测归属

#### Scenario: 可选 Clang 增强冲突
- **WHEN** Clang 在安全 compilation context 中提供语义声明关联，或该关联与基线冲突/解析失败
- **THEN** SHALL 保留来源及配置；成功时补充唯一绑定，失败或冲突时保留 baseline 与 partial/ambiguous
- **AND** MUST NOT 强制 compilation database、静默覆盖其他版本，或将绝对路径 USR 写入稳定身份

#### Scenario: 原生节点错误恢复
- **WHEN** 函数或属性区域出现 ERROR/MISSING、UTF-8、CRLF 或多语言候选解析
- **THEN** SHALL 在 Tree 存活时仅提取受控标量并由 byte index 构造位置，保留可定位事实及错误范围
- **AND** MUST NOT 使用 start/end Point、跨生命周期缓存 Node/Cursor 或伪造完整函数体

### Requirement: 函数结构归一化必须校验引用并隔离版本配置

Normalizer SHALL 校验函数 owner、属性、声明/定义/body 关联的有效性，合并相同语义事实的 producer provenance，并保持不同作用域、版本属性及 compilation configuration 独立。没有多版本构造的已有事实身份 SHALL 保持。

#### Scenario: 重复 producer 和非法 owner
- **WHEN** 两个 producer 提供同一有效结构，或输入引用不存在的 owner
- **THEN** 前者 SHALL 确定性合并且保留来源，后者 SHALL 产生明确合同 Diagnostic 并拒绝无效引用
- **AND** MUST NOT 因值相同跨配置/版本吞并或丢弃原始属性事实

### Requirement: 前端必须提供候选相关使用结构并保留原事实

C/C++ Frontend SHALL 为用途分析提供可定位的声明/引用绑定、读写、简单赋值、比较、控制体、调用参数和逃逸记录。普通无属性函数 SHALL 可被分析；原宏/枚举/函数多版本 Evidence 的值、身份和位置 MUST NOT 被用途标签重写。

#### Scenario: 普通函数中使用局部枚举

- **WHEN** 无 target 属性的函数包含候选枚举及其比较、赋值和后续使用
- **THEN** Frontend SHALL 提供同作用域、真实字节范围的使用记录与完整性信息
- **AND** 不得因函数多版本 inventory 的属性快速路径而漏掉该需求

#### Scenario: 重名或不完整语法

- **WHEN** 同名声明遮蔽、Clang/语法绑定冲突、模板依赖、ERROR/MISSING 或不支持结构影响当前使用范围
- **THEN** SHALL 保留可定位记录并显式 unknown/partial，不按名称任意绑定
- **AND** 无关范围的独立完整记录 SHALL 保留，原 fact 不被删除

#### Scenario: 普通枚举函数不消耗候选用途记录预算

- **WHEN** 文件包含大量非候选枚举或宏，但只有少数函数包含正式知识匹配得到的候选 fact
- **THEN** 默认管线 SHALL 先用正式归一化及候选需求规则选择锚点，仅提取候选所在函数的完整用途记录
- **AND** SHALL 复用本次语法树而不逐 Finding 重解析；不相关函数不生成 usage_scope，不消耗全扫描 usage record 额度，原始事实仍全部保留

### Requirement: 使用结构必须保持原生安全与规范化引用完整性

Frontend SHALL 在 native tree 生命周期内一次提取标量记录，使用既有 SourceByteIndex 而非原生 Point；Node/Tree/Cursor MUST NOT 进入 snapshot。Normalizer SHALL 校验声明、owner、使用端点、span 和配置来源并保留不同配置。

#### Scenario: UTF-8 和多个配置

- **WHEN** 同一文件含 UTF-8/CRLF，且有不同 compile context 或未知基线配置
- **THEN** SHALL 输出精确位置、独立绑定与完整性，不合并成虚假的完整配置
- **AND** 增补语义不得改变已有事实哈希或引入机器根路径身份

#### Scenario: 无效 owner 或原生范围

- **WHEN** 新使用记录引用不存在的声明或不合法范围
- **THEN** Normalizer SHALL 拒绝该记录并产生诊断，不能生成完整用途证明
- **AND** 原生崩溃回归、未释放对象检查及预算反例 SHALL 纳入组件与隔离测试

### Requirement: 宏作用分析输入必须保留调用实参与有序预处理事件
Frontend SHALL 为受支持宏调用采集固定实参 token、序号、形参/定义引用及真实 SourceSpan，并保留 define/undef、include、if/elif/else/endif 的有序结构和完整性；所有记录 SHALL 是 scanner-owned 纯数据，不携带 Node/Tree/Cursor。原 Evidence SHALL 保留，无法绑定的调用 MUST NOT 因项目中同名宏存在而被确认为宏展开。

#### Scenario: 固定实参嵌套传递
- **WHEN** `OUTER(f,x)` 的定义将固定参数传到 `INNER(f,x)`，调用实参为标识符或受支持整数/括号包装
- **THEN** frontend SHALL 提供可独立定位的调用实参、形参、replacement 参数引用和嵌套调用记录
- **AND** 记录 SHALL 不把参数替换结果伪造成原文件中的连续源码

#### Scenario: 宏定义来自头文件
- **WHEN** 调用文件没有本地同名宏定义，但包含可见的本地头文件
- **THEN** frontend SHALL 保留可供下游解析该调用的原始记录，不因本文件宏名集合不包含该名字而漏掉调用
- **AND** 最终宏/普通函数区分 SHALL 由可见性及调用时状态证明

#### Scenario: 不支持的参数语义
- **WHEN** 出现变参、token pasting、stringification、无法确认边界的模板逗号或畸形实参
- **THEN** frontend SHALL 保留原始事实和可定位的不支持原因，不生成 complete 参数替换证明
- **AND** scanner MUST NOT 执行预处理器来补齐本轮缺失语义

### Requirement: 宏事件采集必须安全有界并隔离 producer 配置
事件及 token SHALL 在原生对象有效期内转为稳定标量，保留 producer、TU/configuration 和解析完整性；未配置 Tree-sitter 素材 MUST NOT 冒充任意 Clang configuration 的完整语义。路径、语法、token 或事件预算异常 SHALL 保留 partial/unknown，而不是终止整个项目或解释为无风险。

#### Scenario: 同一头文件具有相反配置
- **WHEN** 两个 TU 对同一头文件使用不同宏定义
- **THEN** 原始源码位置 SHALL 可以共享，但配置增强与后续绑定引用 SHALL 可区分
- **AND** 不同 producer 的冲突 SHALL 不以扫描顺序静默覆盖

#### Scenario: 采集异常和位置边界
- **WHEN** 输入含 UTF-8、CRLF、空实参、语法错误或超过事件/token 预算
- **THEN** frontend SHALL 保持合法的项目相对位置和稳定断点，原生对象不得存入 snapshot
- **AND** 采集模块及两类 adapter 接线 SHALL 具有 fake 原生边界的隔离单元测试，真实 parser 组件测试另行统计
