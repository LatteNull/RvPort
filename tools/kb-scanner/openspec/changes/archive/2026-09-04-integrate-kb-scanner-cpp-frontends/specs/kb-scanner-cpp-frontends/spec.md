## ADDED Requirements

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
