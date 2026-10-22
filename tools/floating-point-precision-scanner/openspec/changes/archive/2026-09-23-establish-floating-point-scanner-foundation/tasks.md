## 1. 工程与可复现环境

- [x] 1.1 建立 `src/floating_point_precision_scanner/`、`tests/unit/`、`tests/integration/`、`tests/fixtures/`、`schemas/` 和 `profiles/` 目录，配置 Python 3.11+ 包元数据及 `fp-precision-scanner` 入口；不得创建具体风险规则实现。
- [x] 1.2 建立锁定的 Linux/amd64 开发容器与依赖清单，固定 Clang/LLVM 21.1.8、Python、jsonschema、pytest 和 coverage.py，并提供依赖/许可证清单校验。
- [x] 1.3 配置格式化、静态检查、类型检查与统一测试命令，确保所有命令从本工具独立根目录可重复执行且不依赖公网。

## 2. 版本化协议与领域模型

- [x] 2.1 编写 Draft 2020-12 的 scan request/result、canonical facts 和 profile JSON Schema，设置固定 `$id`、kind、独立版本、必填字段及 `additionalProperties: false`。
- [x] 2.2 实现 schema registry、版本兼容检查、跨文档引用校验和不可变规范化领域模型，安全聚合多个输入错误。
- [x] 2.3 实现双语 diagnostic 模型、模板渲染、聚合计数、代表位置和默认脱敏，所有用户可见消息与建议同时具备中文/英文字段。
- [x] 2.4 实现 canonical JSON、SHA-256 语义摘要、稳定翻译单元/fact/finding ID 和通用稳定排序工具，排除绝对根、临时路径、时间戳、PID、locale 与调度顺序。
- [x] 2.5 为 2.1–2.4 同步编写正常、边界和异常路径单元测试，包括不兼容主版本、未知/缺失字段、双语缺失、摘要稳定性、ID 碰撞隔离与脱敏断言。

## 3. x86/RISC-V Profile Registry

- [x] 3.1 按 profile schema 创建带字段级来源、维护审批信息和显式 unknown 的 x86_64 Linux GNU ABI 与 riscv64 LP64D Linux GNU ABI Clang 21.1.8 profile 数据。
- [x] 3.2 实现 profile 加载、schema/交叉字段校验、固定版本解析、canonical 指纹、确定性 list/show 以及 source/target 独立绑定。
- [x] 3.3 实现 profile 与编译上下文的 target、ABI、编译器版本冲突检测，确定冲突在分析前失败且 unknown 不被宿主默认值补齐。
- [x] 3.4 为 profile 正常加载、稳定枚举、未知字段、来源缺失、版本错误、冲突、显式 unknown 和不同加载路径相同指纹编写单元测试。

## 4. 编译上下文摄取

- [x] 4.1 实现 `compile_commands.json` 与显式翻译单元二选一校验、路径规范化和读取前项目根边界检查。
- [x] 4.2 实现 `arguments` 优先、POSIX/Windows `command` quoting 的无 shell 解析、工作目录解析和歧义/恶意元字符处理。
- [x] 4.3 实现 response file 的有序展开、provenance、根边界、递归深度/文件数/字节预算和循环检测。
- [x] 4.4 实现最后生效 `-x` 优先的语言识别，只规划 C/C++，聚合 `unsupported_language` 双语诊断，并在无受支持翻译单元时返回 `invalid_request/no_supported_translation_units`。
- [x] 4.5 实现分析参数净化与 canonical compile context，保留标准、target、宏、include、sysroot、浮点选项的原始语义顺序、provenance 和最后生效值，并按语义上下文生成稳定 TU ID。
- [x] 4.6 为 4.1–4.5 编写正常、边界和异常路径单元测试，覆盖 C11/C17/C++17/C++20、混合语言、`-x` 覆盖扩展名、同文件多配置、重复覆盖参数、路径越界、缺失文件、response file 循环/超限和 shell 元字符不执行。

## 5. Clang 前端与 Canonical Facts

- [x] 5.1 定义可注入的进程执行端口，实现明确路径 Clang 21.1.8 的版本验证、受预算约束的调用、stdout/stderr 限制和安全诊断；禁止搜索 PATH 回退。
- [x] 5.2 实现从 canonical compile context 构造只读 Clang AST JSON/目标宏查询命令，移除输出、依赖生成与链接副作用，同时保留语义参数顺序。
- [x] 5.3 实现 Clang 21 JSON mapper，把浮点类型、字面量、算术/比较表达式、显式/隐式转换、函数/内建调用和浮点相关选项转换为版本化 facts，规则层不得接收原始节点。
- [x] 5.4 实现仓库相对 spelling/expansion/声明位置与宏 provenance；缺失位置、未知节点/类型/选项必须产生显式 unknown/unsupported，不得伪造默认事实。
- [x] 5.5 实现 fact/bundle 稳定 ID、排序、语义摘要和 schema 校验，以及单 TU 失败隔离、planned/completed/failed/unknown 计数输入。
- [x] 5.6 用固定 Clang JSON fixture/oracle 为 5.1–5.5 编写正常、边界和异常路径单元测试，覆盖四种语言标准、宏位置、unknown/unsupported、超时、非零退出、无效/截断 JSON、超限 stderr、缺编译器和版本不匹配。
- [x] 5.7 在锁定容器中新增真实 Clang 21.1.8 集成 fixture，验证最小 C11/C17/C++17/C++20 翻译单元和 x86/RISC-V target facts；集成测试不得替代 5.6 的单元测试。

## 6. 应用编排、CLI 与输出

- [x] 6.1 实现扫描应用服务，依次执行请求验证、profile 绑定、编译上下文摄取、逐 TU facts 提取和结果聚合；P1 强制 `findings=[]`、`analysis_scope=facts_only`、`enabled_rule_count=0`。
- [x] 6.2 实现 planned/completed/failed/unknown 分母和 `complete`、`invalid_request`、`failed`、`partial`、`internal_error` 状态机，不得用 finding 数量改变状态。
- [x] 6.3 实现 UTF-8/LF 的确定性结果序列化、facts/diagnostics/locations 稳定排序、同目录临时文件、flush/fsync 和原子 replace，替换失败必须保留既有有效结果。
- [x] 6.4 实现 `scan`、`validate-request`、`profiles list|show` 和 `version` CLI 薄适配器及固定退出码 0/2/3/4/5；非空规则请求返回 `rules_not_available`。
- [x] 6.5 为 6.1–6.4 编写正常、边界和异常路径单元测试，覆盖空 findings 语义、全部/部分/全部失败、无效请求、未分类异常、确定性重复运行、写入/fsync/replace 故障、既有结果保护和每个退出码。

## 7. 单元测试覆盖率与质量门禁

- [x] 7.1 配置 coverage.py `branch = true` 且 source 指向完整 `src/floating_point_precision_scanner`，确保未被测试导入的项目源码仍进入分母；逐项记录所有有限排除模式及理由。
- [x] 7.2 实现并单元测试覆盖率门禁读取器，在同一次 coverage JSON 上分别检查项目整体和受影响模块的原始行/分支百分比，四项均以未四舍五入值执行 `>= 90%` 门槛并在不足时非零退出。
- [x] 7.3 审核全部项目自有可执行代码均有正常、边界和异常路径的有效断言单元测试；不得以集成测试、编译成功、静态检查、缩小 source 或排除业务逻辑补足门槛。
- [x] 7.4 运行完整单元测试与覆盖率命令，确认项目整体及受影响模块行覆盖率、分支覆盖率分别至少 90%，生成 `coverage.json`、`coverage.xml` 和 `htmlcov/`。
- [x] 7.5 记录实际命令、测试通过/失败数量、四项未四舍五入覆盖率、完整统计源码范围、排除项及理由和报告路径；任一测试失败或覆盖率不足时保持本组任务未完成。

## 8. 文档、契约验证与交付

- [x] 8.1 更新 README/使用文档，说明仅支持 C/C++、四个 CLI 命令、请求/结果示例、profile 选择、facts-only 限制、状态/退出码和容器化 Clang 集成方式。
- [x] 8.2 添加 schema 示例与 consumer contract tests，验证示例文档、双语字段、空 findings metadata、稳定顺序和所有失败状态均符合 schema。
- [x] 8.3 执行格式化、静态检查、类型检查、全部单元测试、双 90% 覆盖率门禁、锁定 Clang 集成测试和 `openspec validate establish-floating-point-scanner-foundation --strict --no-interactive`，保存可审计结果。
- [x] 8.4 对照 proposal、design、四个 delta specs 和既有 I/O/失败/质量 specs 完成验收复核，确认没有具体浮点风险规则、非 C/C++ 分析或未授权主服务集成进入本变更。
