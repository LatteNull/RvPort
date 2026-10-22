# compilation-context-ingestion Specification

## Purpose

定义编译数据库和显式翻译单元的安全摄取、C/C++ 语言选择、response file 展开、参数规范化和保守失败传播。

## Requirements

### Requirement: 请求必须选择且只选择一种编译输入
扫描器 SHALL 要求请求在 `compile_commands` 与显式 `translation_units` 之间恰好选择一种输入。所有输入路径 MUST 在读取前解析、规范化并执行项目根边界校验；未显式授权的根外路径 SHALL 被拒绝。

#### Scenario: 使用编译数据库
- **WHEN** 请求只提供有效的 `compile_commands.json`
- **THEN** 加载器读取数据库并产生候选编译记录

#### Scenario: 同时提供两种输入
- **WHEN** 请求同时提供编译数据库和显式翻译单元
- **THEN** 验证器返回 `invalid_request/input_selector_conflict` 且不读取两者

#### Scenario: 路径越界
- **WHEN** 规范化后的编译数据库、源文件或 response file 位于未授权的项目根外
- **THEN** 加载器拒绝读取并返回脱敏的双语路径边界诊断

### Requirement: 编译数据库解析不经过 shell
加载器 SHALL 支持标准 `arguments` 数组和 `command` 字符串，存在两者时 MUST 优先使用 `arguments`。`command` SHALL 按记录的平台 quoting 规则解析为参数数组，任何参数均不得通过 shell 重新解释或执行。

#### Scenario: arguments 与 command 同时存在
- **WHEN** 一条编译记录同时提供不同内容的 `arguments` 和 `command`
- **THEN** 加载器使用 `arguments` 并产生可审计的冲突诊断

#### Scenario: command 含 shell 元字符
- **WHEN** `command` 包含重定向、变量替换或命令连接字符
- **THEN** 加载器只把它们视为命令行参数或拒绝歧义记录，不执行任何附加命令

### Requirement: Response file 展开受边界与资源预算约束
加载器 SHALL 以记录目录为基准展开 response file，并 SHALL 限制递归深度、文件数量和总字节数且检测循环。展开后参数 MUST 保留原始相对顺序和来源位置。

#### Scenario: 合法嵌套 response file
- **WHEN** response file 在预算内、无循环且全部位于授权根内
- **THEN** 加载器按出现位置递归展开并记录每个参数的 provenance

#### Scenario: response file 循环引用
- **WHEN** 两个 response file 直接或间接形成循环
- **THEN** 对应翻译单元被拒绝并产生可重试性为 false 的结构化诊断

### Requirement: 只规划 C 与 C++ 翻译单元
语言判定 SHALL 优先采用最后生效的 `-x`，否则使用受支持扩展名；只允许 C、C header、C++、C++ header 并记录标准版本。非 C/C++ 条目 MUST 产生聚合的 `unsupported_language` 双语诊断，且 MUST NOT 进入 planned、completed、failed 或 unknown 分母。

#### Scenario: 混合语言编译数据库
- **WHEN** 编译数据库同时包含 C、C++、Rust、CUDA 和汇编条目
- **THEN** 扫描计划只包含 C/C++，其余条目按语言聚合为 `unsupported_language` 诊断

#### Scenario: -x 覆盖扩展名
- **WHEN** `.txt` 文件最后生效参数为 `-x c++`
- **THEN** 该文件按 C++ 翻译单元规划并记录显式语言来源

#### Scenario: 没有受支持翻译单元
- **WHEN** 选择完成后不存在任何 C/C++ 条目
- **THEN** 扫描器返回 `invalid_request/no_supported_translation_units` 且不启动前端

### Requirement: 编译上下文规范化保留语义顺序
加载器 SHALL 移除输出、链接和依赖生成等与只读语法分析冲突的参数，同时保留语言标准、target、宏、include、sysroot 和浮点语义参数的顺序、来源与最后生效值。去重 MUST 以规范化文件、工作目录、语言和语义参数摘要为键，不得只按文件名去重。

#### Scenario: 同一文件具有两个配置
- **WHEN** 同一源文件以不同宏或 target 出现两条编译记录
- **THEN** 两条记录生成不同稳定翻译单元 ID 并分别进入扫描计划

#### Scenario: 参数互相覆盖
- **WHEN** 命令中重复出现标准、target 或浮点选项
- **THEN** canonical context 同时保存有序原始语义参数和确定的最终生效值

### Requirement: 编译上下文错误按翻译单元保守传播
在请求级校验之后，单条编译记录的缺失源文件、不可解析 quoting、不受支持选项或上下文冲突 SHALL 关联到稳定翻译单元身份并传播为 failed/unknown；其他有效翻译单元 MUST 继续处理，除非达到预算或发生内部错误。

#### Scenario: 一条记录缺少源文件
- **WHEN** 多条 C/C++ 记录中一条源文件不存在而其他记录有效
- **THEN** 有效记录继续分析，缺失记录计入 failed，最终状态至少为 `partial`
### Requirement: 编译上下文必须保留旧标准和方言
扫描器 SHALL 接受并保留 C89/C90、C99、C11、C17/C18、C++98、C++03、C++11、C++14、C++17、C++20 及常见 GNU 别名，并可按锁定 Clang 能力接收 C23/C++23。输出 SHALL 区分基础标准、ISO/GNU 方言、显式参数与 compiler default，MUST NOT 把旧标准静默升级为 C17 或 C++17。

#### Scenario: C99 GNU 方言
- **WHEN** 编译记录包含 `-std=gnu99`
- **THEN** 基础标准为 `c99`、方言为 `gnu`，原始参数保持 `-std=gnu99`

#### Scenario: 无显式标准
- **WHEN** 编译记录没有 `-std`
- **THEN** 标准来源为 `compiler-default`，不得伪装成用户显式设置

### Requirement: AST 主源码归属判定必须兼容 Clang 位置字段省略
扫描器 SHALL 按 Clang 序列化顺序恢复省略的文件上下文，结合真实翻译单元和有界的物理源码字节索引恢复缺失行列；仅在文件归属可证明时继承。项目头文件 SHALL 允许产生项目事实，`includedFrom` 本身不是外部文件的判据；显式外部路径 MUST NOT 因字段省略被纳入项目 Finding。

#### Scenario: 主源码顶层声明省略 file
- **WHEN** Clang AST 中顶层函数声明仅包含 `offset`、`line` 与 `col`，且没有 `includedFrom`
- **THEN** 扫描器保留该函数及其子节点产生的项目事实

#### Scenario: 头文件声明带 includedFrom
- **WHEN** 顶层声明的位置包含 `includedFrom`，实际文件归属为项目外部或无法确定
- **THEN** 扫描器排除该声明独立产生的项目事实，不把它的偏移解释为主源码偏移
