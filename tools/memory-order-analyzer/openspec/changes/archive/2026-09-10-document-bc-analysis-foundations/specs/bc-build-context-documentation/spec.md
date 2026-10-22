## ADDED Requirements

### Requirement: Explain BC generation prerequisites and stages

文档 SHALL 说明 BC 生成需要预处理、语义检查与 IR 生成，不要求最终可执行程序链接或运行；SHALL 区分翻译单元、源码文件与头文件，并列出生成文件、声明、工具链和 SDK 等输入前提。

#### Scenario: Analyze without producing an executable

- **WHEN** 读者希望只生成分析用 BC
- **THEN** 文档给出停止于 LLVM IR 的命令示意，并说明依然必须通过前端编译，头文件通常随包含它的 TU 处理

#### Scenario: Required generated header is missing

- **WHEN** 构建配置引用尚未生成的头文件
- **THEN** 文档说明需先补齐必要的配置/生成步骤，不能将缺失头文件与允许保留的外部函数声明混为一谈

### Requirement: Document production compiler adaptation limits

文档 SHALL 区分生产编译器与分析 Clang，按保留、转换、移除和不支持分类说明参数适配，覆盖语言标准、宏、目标/ABI、sysroot、包含路径、工作目录、response file 和隐式环境；SHALL 说明预定义宏和编译器扩展可能造成语义偏差。

#### Scenario: Replay a GCC or MSVC compilation with Clang

- **WHEN** 原始命令来自非 Clang 工具链
- **THEN** 文档要求说明适配依据、缺失信息和不支持项，明确成功生成 BC 不证明与生产编译器语义完全等价

### Requirement: Define compilation database capabilities and gaps

文档 SHALL 解释 `directory`、`file`、`arguments`/`command`、可选 `output` 的作用，明确数据库不单独提供实际头文件依赖、完整目标/链接图、调用图或线程关系，并给出相应的补充信息来源。

#### Scenario: Only compile_commands.json is available

- **WHEN** 输入只有编译数据库和源码
- **THEN** 文档说明可以重建逐 TU 编译上下文，但不能据此宣称掌握完整程序边界；列出预处理依赖采集和构建目标/链接记录等补充途径

### Requirement: Preserve configuration-specific translation unit identity

文档 SHALL 给出 TU 配置身份和构建快照的概念示例，记录源路径、有效命令、工具链、目标、宏、包含路径、工作目录与构建变体，并区分身份、内容哈希和目标成员关系；SHALL 解释头文件内容及配置变化对缓存有效性的影响。

#### Scenario: One source has multiple compile commands

- **WHEN** 相同源码路径在不同宏、目标或编译选项下出现多次
- **THEN** 文档示例保留不同配置的 TU/BC 记录，不按路径覆盖，也不把可选 output 当作完整目标归属证明
