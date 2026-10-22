## ADDED Requirements

### Requirement: C/C++ 前端必须支持基础解析和可选语义增强
扫描器 SHALL 使用能够处理不完整项目的基础 C/C++ 语法前端，并 SHALL 在存在充分 compilation context 时使用经过验证的 Clang 能力补充宏、include 和语义 Evidence；增强前端不得替代基础覆盖。

#### Scenario: 项目没有 compile_commands
- **WHEN** 输入包含 C/C++ 文件但没有可用的 `compile_commands.json`
- **THEN** 基础前端 SHALL 继续产生可追溯的语法和预处理器 Evidence
- **AND** 需要完整编译上下文的关系 SHALL 标记为 partial/unknown

#### Scenario: Clang 增强成功
- **WHEN** translation unit 具有有效 compilation context 且 Clang 能完成分析
- **THEN** scanner SHALL 将宏定义、展开、include 或语义结果作为带 producer 和版本信息的增强 Evidence
- **AND** scanner SHALL 与基础前端事实去重但保留来源集合

#### Scenario: Clang 增强失败
- **WHEN** 缺失头文件、参数不兼容或单个 translation unit 无法由 Clang 完成分析
- **THEN** scanner SHALL 记录降级 diagnostic 并继续使用基础前端结果
- **AND** scanner MUST NOT 因增强失败而终止整个项目扫描或声明缺失关系为确定事实

### Requirement: 基础设施技术必须经过复用优先验证
对于语法解析、图存储、模型校验、路径过滤和标准构建元数据，scanner SHALL 先验证维护中的成熟技术，并 SHALL 仅在候选无法满足准确性、安全性、兼容性或资源约束时实现替代基础设施。

#### Scenario: 候选技术满足验收条件
- **WHEN** 容器 spike 证明候选库满足代表性 fixture、许可证、可复现构建和资源要求
- **THEN** 后续实现 SHALL 通过 scanner 自有 adapter/protocol 复用该技术
- **AND** scanner MUST NOT 无理由重新实现同等通用能力

#### Scenario: 候选技术不满足验收条件
- **WHEN** 候选库无法保留必要 Evidence、会执行不可信代码、破坏现有输出或超出明确资源预算
- **THEN** change SHALL 记录拒绝证据、受影响场景和替代边界
- **AND** 自研实现 SHALL 仅覆盖已确认缺口而不是复制完整外部工具

### Requirement: 默认构建和打包分析必须无副作用
扫描器 SHALL 通过纯解析或有界静态求值分析 Makefile、Autoconf、RPM、CMake 和 compilation database，并 MUST NOT 在默认扫描中执行输入项目声明的 shell、M4、RPM、CMake、plugin 或 response-file 副作用。

#### Scenario: Makefile 包含 shell 求值
- **WHEN** Makefile 使用 `$(shell ...)`、`!=` 或其他外部命令求值
- **THEN** scanner SHALL 保留表达式位置和上下文 Evidence
- **AND** 结果 SHALL 为 unsupported/unknown 或基于其他静态证据的部分结论
- **AND** scanner MUST NOT 执行该命令获得变量值

#### Scenario: Autoconf 或 RPM 包含可执行宏
- **WHEN** M4/RPM 输入包含 `syscmd`、`esyscmd`、shell expansion、Lua、include 或同等可执行构造
- **THEN** scanner SHALL 禁止在默认静态扫描路径中完整展开该构造
- **AND** scanner SHALL 输出稳定 diagnostic 而不是静默忽略或猜测结果

#### Scenario: compilation command 请求加载插件
- **WHEN** `compile_commands.json` 包含编译器插件、任意 response file 或其他未允许参数
- **THEN** Clang adapter SHALL 拒绝或移除该参数并记录 diagnostic
- **AND** scanner MUST NOT 加载项目提供的可执行插件

### Requirement: 图存储实现必须可替换并由基准验证
Evidence Graph SHALL 通过 scanner 自有 `GraphStore` 契约访问；具体图库 MUST NOT 泄漏到 frontend、analyzer、classifier 或 report 接口，并 SHALL 通过容器内基准证明适用性。

#### Scenario: 使用成熟内存图库
- **WHEN** 首个 GraphStore adapter 使用 NetworkX MultiDiGraph 或其他候选库
- **THEN** Entity 稳定 ID、Relation 类型、Evidence provenance 和 proof path SHALL 保持 scanner 领域语义
- **AND** 候选库私有节点或边类型 MUST NOT 出现在兼容报告中

#### Scenario: 图库超过资源预算
- **WHEN** 代表性项目基准表明当前 adapter 超出已批准的时间或内存预算
- **THEN** scanner SHALL 能替换 GraphStore 实现而不改变 frontend、analyzer 或 `scan-result.json`

### Requirement: 技术增强必须保持现有知识和报告兼容
任何新 parser、图库或模型库 SHALL 继续加载现有 Clang/GCC 生成数据、YAML 规则和 `generatedSet`，并 SHALL 将新 Evidence/Relation/Assessment 投影到现有结果兼容位置。

#### Scenario: 新技术处理现有 fixture
- **WHEN** 新 frontend 或 GraphStore 运行当前 x86 检测 fixture
- **THEN** 既有关键 rule ID、Finding 分类和阻断状态 SHALL 不发生非预期退化
- **AND** `clang-x86-entries.json` 和 `gcc-x86-entries.json` 的内容 SHALL 保持不变

#### Scenario: 输出增强分析结果
- **WHEN** 新技术产生 parser provenance、关系证明或项目评估
- **THEN** 后端需要保留的关系信息 SHALL 投影到 Finding `trace`
- **AND** 项目静态评估 SHALL 投影到可选 `summary.readiness`
- **AND** `schemaVersion: "1.0"` 和三个现有 artifact SHALL 保持不变
