## Context

P0 已建立 C/C++ 浮点精度扫描器的总体设计、I/O 契约、失败语义和质量门禁，但当前目录尚无生产代码。P1 需要提供后续规则共同依赖的最小运行时：把编译数据库或显式翻译单元转换为稳定的编译上下文，使用固定版本的 Clang 得到类型化信息，再归一化为与 Clang 原始节点解耦的 canonical floating-point facts。

本工具只分析 C11、C17、C++17、C++20。工程可能是多语言工程，但非 C/C++ 条目只能被审计性排除，不能送入前端，也不能进入 planned 分母。本变更必须复用 `scanner-io-contract`、`scanner-failure-semantics` 和 `scanner-quality-gates` 的既有契约，不以实现便利改变状态、退出码或质量要求。

开发基线与相邻工具保持一致：Linux/amd64 锁定环境、Python 3.11+、Clang/LLVM 21.1.8。当前 Windows 宿主机未安装 Clang，因此 Clang 集成验证在锁定容器中执行；纯单元测试不依赖宿主机 Clang。

## Goals / Non-Goals

**Goals:**

- 建立职责分离、可单元测试的 Python 包与最小 CLI。
- 落地请求、结果、canonical facts 和 profile 的版本化 JSON Schema。
- 正确加载 `compile_commands.json` 或显式翻译单元，只规划 C/C++。
- 建立 x86/RISC-V profile registry，并使未知事实保持显式 unknown。
- 从锁定 Clang 输出提取、归一化和稳定序列化浮点相关事实。
- 提供双语诊断、稳定 ID、确定性排序、原子写出和完整状态/退出码。
- 让全部项目自有源码及每个受影响模块的行、分支覆盖率均可重复验证且至少为 90%。

**Non-Goals:**

- 不实现或启用任何浮点风险检测规则，结果中的 `findings` 固定为空。
- 不执行或交叉编译目标程序，不进行 x86/RISC-V 动态差分。
- 不分析 Rust、Go、CUDA、汇编或其他非 C/C++ 语言。
- 不接入 RvPort 主服务、CI 风险策略、AI evidence adapter 或自动修复。
- 不承诺兼容未锁定的 Clang 主版本，也不从宿主机推断缺失 profile 值。

## Decisions

### 1. 使用 Python 控制平面和端口/适配器结构

生产包采用 `src/floating_point_precision_scanner/` 布局，按 `cli`、`protocol`、`compilation`、`profiles`、`frontend`、`facts`、`diagnostics`、`aggregation`、`output` 分层。核心层只接收显式数据模型和端口，不直接读取环境变量、当前时间或全局文件系统；文件系统、进程执行和原子替换由适配器注入。

选择 Python 是因为本阶段主要工作是协议校验、编译上下文归一化、Clang JSON 转换和确定性序列化，可用严格单元测试覆盖异常分支。替代方案是直接使用 C++ LibTooling；其类型访问更强，但会把 ABI/链接和测试复杂度提前带入基础框架。若后续规则证明 Clang JSON 缺少必要语义，可在不改变 canonical facts 契约的前提下新增 LibTooling 适配器。

### 2. CLI 薄层只编排用例

安装入口名为 `fp-precision-scanner`，提供：

- `scan --request <request.json> --output <result.json>`：执行扫描并按状态返回 0/2/3/4/5；
- `validate-request --request <request.json>`：只做 schema 与静态语义校验；
- `profiles list|show <profile-id>`：输出 registry 信息；
- `version`：输出工具、协议、facts 和 Clang 兼容版本。

CLI 不包含业务判断。`scan` 即使没有具体规则也要完成所有翻译单元的 facts 提取；全部成功时输出 `complete` 和空 `findings`，部分/全部失败时遵循既有保守状态。替代方案是只提供单一命令，但独立验证和 profile 查询能显著降低集成诊断成本。

### 3. 协议使用 JSON Schema Draft 2020-12 并分开版本

在 `schemas/v1/` 保存 scan request/result，在 `schemas/facts/v1/` 和 `schemas/profiles/v1/` 保存 facts/profile schema。所有 schema 使用固定 `$id`、`additionalProperties: false`，主版本不兼容时拒绝；工具版本、结果协议版本、facts 版本和 profile 版本分别演进，避免把内部事实变化误当成外部结果协议兼容。

请求通过 `input.compile_commands` 或 `input.translation_units` 二选一选择输入。结果遵循现有双语字段和状态契约；P1 仍实现 finding ID 生成器并用合成候选对象测试，但不会发布实际 finding。

### 4. 通过进程边界调用锁定的 Clang 21.1.8

前端适配器调用明确路径的 Clang 21.1.8，不搜索或回退到任意宿主编译器。每个翻译单元执行语法/AST JSON 提取，并通过预处理器宏或显式查询收集目标相关的可验证事实。原始命令先移除输出、依赖生成、链接等与只读分析冲突的参数，再保留标准、宏、include、target 和浮点语义相关参数；原始顺序及最终生效值均被记录。

选择 Clang JSON 进程边界而非 Python libclang，是为了隔离动态库 ABI 并允许在单元测试中注入固定 stdout/stderr/退出码。canonical mapper 是唯一理解 Clang 21 JSON 形状的模块。遇到未知节点、缺字段或不受支持选项时输出 unknown/diagnostic，禁止猜测。

### 5. 编译上下文先规范化，再选择语言

`compile_commands.json` 同时支持 `arguments` 和 `command`，优先使用 `arguments`；`command` 通过与记录平台一致的、受测试的命令行解析器处理，不经 shell 执行。相对 `directory`、`file`、include 和 response file 路径均相对记录目录解析，再校验项目根边界。response file 有深度、文件数和总字节预算，并检测循环。

语言判定优先使用最后生效的 `-x`，其次使用扩展名；只接受 `c`、`c-header`、`c++`、`c++-header` 及约定的 C/C++ 扩展名。非 C/C++ 条目产生聚合的 `unsupported_language` 双语诊断，但不进入 planned；去重键为规范化文件、工作目录、语言和语义参数摘要。若无受支持翻译单元，返回 `invalid_request/no_supported_translation_units`。

### 6. Profile 是数据，不是代码默认值

profile registry 从仓库内版本化 JSON 加载，P1 提供 x86_64 Linux GNU ABI 与 RISC-V 64 LP64D Linux GNU ABI 的 Clang 21 profile。每个 profile 包含标识、版本、target triple、ABI、编译器约束、三种基本浮点类型、求值方式、FMA/contraction、特殊值与浮点环境能力、数学库标识、字段级来源和 unknown 标记。

registry 在加载时做 schema 与交叉字段校验，使用 RFC 8785 风格的 canonical JSON（项目内实现限定子集）计算 SHA-256 指纹。请求必须显式给出 source/target profile；profile 不存在、版本不兼容或与翻译单元显式 target 冲突时，在分析前返回 `invalid_request`。不使用宿主机值补空。

### 7. Canonical facts 是规则层唯一输入

每个翻译单元产生 `FloatingPointFactBundle`，包含：

- facts/schema/producer/profile 版本与翻译单元标识；
- 规范化编译上下文及其语义摘要；
- 浮点类型、字面量、算术/比较表达式、隐式与显式转换、函数/内建调用；
- 拼写位置、展开位置、相关声明位置和宏来源；
- target/标准/浮点相关编译选项及其 provenance；
- unknown、unsupported 与前端诊断。

facts 使用带 `fact_kind` 的判别联合，集合按 `(normalized_path, line, column, fact_kind, semantic_fingerprint)` 排序。稳定标识通过 schema/version、仓库相对 POSIX 路径、语义位置和规范化语义载荷计算 SHA-256；绝对根目录、临时目录、时间戳、进程 ID 和并发完成顺序不参与摘要。路径大小写规则由请求平台显式决定，不依赖当前系统 locale。

### 8. 状态聚合与原子输出复用既有契约

聚合器以 planned/completed/failed/unknown 为唯一状态依据：全部 planned 成功为 `complete`；至少一项成功且有未完成项为 `partial`；无任何可用结果为 `failed`；分析前错误为 `invalid_request`；未分类异常为 `internal_error`。风险数量不参与退出码。

所有 diagnostics 和 facts 先稳定去重、排序，再生成 UTF-8、LF、固定缩进且键顺序稳定的 JSON。输出先写同目录唯一临时文件，flush/fsync 后使用原子 replace；目录 fsync 在平台支持时执行。替换失败时保留既有正式结果并清理本次临时文件。默认诊断只暴露仓库相对路径和脱敏摘要。

### 9. 单元测试与覆盖率是同一实现任务的一部分

单元测试使用 pytest，进程、文件系统故障点、时钟和 ID 摘要输入均可注入。Clang mapper 使用仓库内固定 JSON fixture/oracle，覆盖 C11、C17、C++17、C++20、宏、unknown 节点和解析失败；真正调用 Clang 21 的用例单独标为 integration，不能替代单元测试。

coverage.py 开启 branch coverage，并通过 `source = src/floating_point_precision_scanner` 把未导入源码计入分母。门禁脚本读取单次 coverage JSON，分别检查项目整体和受影响模块；四个百分比均以未四舍五入值比较 `>= 90`。允许排除的只有 `if TYPE_CHECKING`、不可达防御断言或纯生成文件，且每项必须在配置旁写明理由；CLI、错误路径、协议、profiles、facts 和输出逻辑不得排除。报告固定生成 XML、JSON 与 HTML。

## Risks / Trade-offs

- [Clang AST JSON 不是稳定公共 API] → 锁定 21.1.8，把解析集中在单一适配器，并用完整 fixture/oracle 与兼容性失败诊断保护。
- [命令行与 response file 在不同平台语义不同] → 记录平台类型，使用显式解析器与预算，不经 shell，并对 Windows/POSIX quoting 分别单测。
- [x86/RISC-V profile 数据错误会污染所有后续规则] → 要求字段级来源、schema/交叉校验、指纹和评审；未知值宁可保持 unknown。
- [Python 归一化大型 AST 可能占用较多内存] → 先提供预算和逐 TU 处理边界；若实测超限，再在独立 change 中引入流式解析，不改变 facts 契约。
- [P1 空 findings 容易被误解为“无风险”] → metadata 明确 `enabled_rule_count=0`、`analysis_scope=facts_only`，CLI 诊断说明尚未执行风险规则。
- [Windows 宿主缺少 Clang] → 单元测试完全可离线运行；集成与验收使用锁定 Linux 容器，不静默改用其他 Clang。

## Migration Plan

1. 建立包、schema、profiles、测试与锁定开发环境；CLI 尚未接入 RvPort。
2. 先实现纯数据与验证层，再实现编译上下文、Clang 适配器、facts、聚合与输出。
3. 运行全部单元测试、受影响模块门禁和锁定 Clang 集成 fixture；只有四项覆盖率均达标才完成 P1。
4. 将本变更的 delta specs 同步到主 specs 后归档；P2 规则 change 只依赖公开 schema/facts，不依赖 Clang 原始 JSON。
5. 回滚时移除尚未被主服务引用的包入口和生成物即可；不得保留与 schema/profile 版本不匹配的输出。

## Open Questions

- profile 字段来源和后续发布审批人的组织归属需在进入 RvPort 主服务前确定；P1 先把来源与审批字段设为必填。
- canonical facts 是否需要长期支持跨 Clang 主版本读取，将根据 P2/P3 规则开发反馈另立 change；P1 只保证 Clang 21.1.8。
- 大型工程的性能预算默认值需用真实迁移项目测量后确定；P1 只实现显式预算与保守失败语义。
