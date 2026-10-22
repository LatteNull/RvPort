## MODIFIED Requirements

### Requirement: 内存序分析必须使用统一项目入口
Worker SHALL 根据完整 `compile_commands.json` 为所有合法 C/C++ 翻译单元准备可信源码输入，并在共享 BC 可用时将其适配为工具外部 bundle；Worker SHALL 只调用 `memory_order_analyzer analyze-project`，不得由 Java 编排工具内部分析阶段。共享 BC SHALL 是可选增强证据而不是任务创建的硬前置条件。

#### Scenario: 使用完整 BC 运行全部 Scope
- **WHEN** 当前源码版本具有成功 x86 构建、真实 compile database 且全部计划翻译单元具有可用 BC record
- **THEN** 后端 SHALL 以 `scope_selection=all`、`source_assistance=auto` 和固定 policy 创建统一请求
- **AND** 所有可分析翻译单元模式 SHALL 为 `ast-ir`
- **AND** 工具 SHALL 自行编排内部阶段和内部 ArtifactKey

#### Scenario: 无 BC 时运行 AST-only
- **WHEN** 当前源码版本具有成功 x86 构建和真实 compile database，但没有可用 BC record
- **THEN** 后端 SHALL 为合法翻译单元生成 SourceSemanticRequest 并创建统一分析请求
- **AND** 翻译单元模式 SHALL 为 `ast-only`
- **AND** 工具 SHALL 将仅有源码证据的结论保存为 source candidate、unknown 或 frontier
- **AND** MUST NOT 将其提升为已经证明的 runtime risk 或全程序安全结论

#### Scenario: 部分 BC 使用混合证据
- **WHEN** 仅部分翻译单元具有校验成功的 BC
- **THEN** 具有 BC 和源码证据的翻译单元 SHALL 使用 `ast-ir`
- **AND** 仅具有源码证据的翻译单元 SHALL 使用 `ast-only`
- **AND** 单个翻译单元缺少 BC MUST NOT 阻断其他翻译单元或整个任务

#### Scenario: 平台身份与工具身份隔离
- **WHEN** adapter 转换平台 record、源码请求和 scope
- **THEN** adapter SHALL 保留源码、编译、producer、target、ABI、profile、语言标准、方言、分母和 scope 语义
- **AND** MUST NOT 把平台 artifact key 冒充为分析器内部 ArtifactKey

#### Scenario: 旧语言标准和方言按真实上下文分析
- **WHEN** compile database 指定 C89/C90、C99、C++98/C++03 或相应 GNU 方言
- **THEN** source profile SHALL 保留真实标准与方言并使用锁定 Clang 重放 AST
- **AND** MUST NOT 回退为 C17 或 C++17 标签
- **AND** 依赖较新语言能力的规则 SHALL 对该翻译单元标记不适用或 unknown，而不是拒绝整个项目

#### Scenario: 开放 Scope
- **WHEN** scope 声明 `closed=false`
- **THEN** 后端 SHALL 允许工具运行
- **AND** 最终 partial/frontier 语义 SHALL 由统一报告决定，不得伪造闭合范围
