## ADDED Requirements

### Requirement: 以编译上下文驱动 C/C++ 扫描
扫描器 SHALL 仅分析 C 与 C++ 两种源语言，首期标准基线为 C11、C17、C++17 和 C++20。扫描器 SHALL 以每个 C/C++ 翻译单元的实际编译上下文消费源文件、语言标准、目标三元组、宏、包含路径和会改变浮点语义的编译选项。缺少关键上下文时，扫描器 MUST 将受影响结论标记为 `unknown` 或返回部分分析，不得假定默认编译语义并报告确定性安全结论。

#### Scenario: 完整编译数据库
- **WHEN** 请求提供可解析的 `compile_commands.json`，且翻译单元具备完整编译参数
- **THEN** 扫描器按翻译单元解析源码，并在证据中记录生效的语言标准、目标与浮点相关选项

#### Scenario: 缺少关键编译参数
- **WHEN** 翻译单元无法确定目标、宏或浮点选项，且这些信息会改变某条规则的判断
- **THEN** 扫描器将该判断标记为 `unknown`，并输出缺失上下文诊断，而不是生成确定性无风险结论

#### Scenario: 编译数据库包含非 C/C++ 条目
- **WHEN** 编译数据库同时包含 C/C++ 与其他源语言的条目
- **THEN** 扫描器仅将 C/C++ 翻译单元纳入 planned 分母，并为被排除条目输出 `unsupported_language` 信息诊断，不尝试推断其浮点语义

### Requirement: 覆盖迁移相关浮点风险类别
扫描器 SHALL 使用稳定 finding code 检测并分类以下 x86→RISC-V 迁移风险：`long double` 表示与 ABI、x87 扩展中间精度与二次舍入、FMA 收缩或展开、`-ffast-math` 及其子选项、动态舍入模式与浮点环境、隐式窄化和混合精度表达式、精确相等或不合理 epsilon 比较、重结合或归约顺序、数学库边界行为，以及 SIMD intrinsic 或架构专用数学函数。每条 finding MUST 标明规则版本和风险类别。

#### Scenario: long double 穿越 ABI 边界
- **WHEN** `long double` 值出现在外部可见函数、可变参数、持久化布局或二进制接口边界
- **THEN** 扫描器输出 `long-double-abi` finding，并说明源/目标 profile 的表示或 ABI 差异及验证建议

#### Scenario: FMA 语义可能改变结果
- **WHEN** 表达式可在一端融合为 FMA、另一端保持乘法与加法两次舍入，且编译选项未保证一致
- **THEN** 扫描器输出 `fma-contraction` finding，并记录表达式、相关编译选项和建议的双平台对比用例

#### Scenario: fast-math 改变浮点契约
- **WHEN** 编译命令启用 `-ffast-math`、`-Ofast` 或等价子选项
- **THEN** 扫描器输出项目级或翻译单元级 `unsafe-fp-optimization` finding，并列出实际生效选项及受影响语义

#### Scenario: 架构专用数学入口
- **WHEN** 源码使用 x86 SIMD intrinsic、架构专用向量数学函数或依赖特定数学库行为
- **THEN** 扫描器输出 `architecture-specific-fp-api` finding，并给出 RISC-V 替代调查和结果对比建议

### Requirement: 结论必须绑定可核验的证据
每条 finding SHALL 至少包含规范化文件路径、源码范围、相关表达式或配置项、规则命中原因、来源 profile、目标 profile、严重性、置信度、证据来源和中英文建议。没有足够证据区分风险与非风险时 MUST 保留 `unknown`，不得伪造源码位置、类型语义或架构差异。

#### Scenario: 确定性 AST 证据
- **WHEN** 规则由已解析的类型、表达式和编译参数确定性命中
- **THEN** finding 的 `evidence_origin` 为 `deterministic`，并包含可回溯的 AST/编译参数证据

#### Scenario: 启发式数值敏感区域
- **WHEN** 扫描器仅依据归约循环、差值抵消或领域线索推断数值敏感性
- **THEN** finding 的 `evidence_origin` 为 `heuristic`，置信度不得标为确定，并明确需要人工确认的判断依据

#### Scenario: AI 扩展证据
- **WHEN** 可选 AI 扩展参与判断
- **THEN** finding 的 `evidence_origin` 为 `ai`，并提供置信度、可核验证据与失败回退语义；AI 结论不得覆盖确定性事实

### Requirement: 风险分级与人工确认
扫描器 SHALL 将严重性限制为 `critical`、`high`、`medium`、`low` 和 `info`，并依据 ABI 暴露范围、结果敏感度、证据强度和影响范围计算。所有 `critical`、`high` 以及来源为 `heuristic` 或 `ai` 的结论 MUST 标记 `requires_human_confirmation=true`。

#### Scenario: 高风险结论
- **WHEN** 检测到可能改变公开 ABI、持久化数据或关键业务数值结果的差异
- **THEN** finding 至少为 `high`，要求人工确认，并给出最小化的 x86/RISC-V 对比测试建议

### Requirement: 抑制不得隐藏分析边界
扫描器 SHALL 支持按 finding code、路径和带理由的源码抑制；每次抑制 MUST 记录规则、理由和位置。无理由的通配抑制、解析失败或不支持语义 MUST NOT 被统计为“无风险”。

#### Scenario: 有理由的局部抑制
- **WHEN** 用户对特定源码范围配置有效的 finding code 与理由
- **THEN** 扫描器不发布该 finding，但在摘要中计入 suppressed 数量并保留可审计抑制记录
