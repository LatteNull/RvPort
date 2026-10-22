## Context

当前专项分析创建服务要求成功 x86 构建同时具有 `compile_commands.json`、`SharedLlvmBitcodeArtifactSet@2.0` manifest、bundle 和至少一个 produced record。运行时 materializer 也把三个制品视为必填，并通过 manifest 中 produced record 的源码集合裁剪编译数据库。因此：

- BC 基础设施失败时，浮点和内存序分析都无法启动；
- artifact set 为 `PARTIAL` 时，无 BC 的翻译单元不会进入 AST 分析；
- 浮点扫描器本身支持省略 `bitcode_artifact_set`，内存序统一协调器也具有 `ast-only` 模式，但后端没有暴露这些能力；
- 平台 BC schema、BC producer 和内存序 source profile 仅接受 C11、C17、C++17、C++20；producer 还会把 C89/C99 等参数改写为 C17，把其他 C++ 标准改写为 C++17；
- 浮点扫描器的生产编译计划能够保留任意 `-std=`，但现有验证基线和平台适配没有覆盖旧标准。

共享 BC 是 x86 构建的非阻断副产物，因此后续分析不能反过来把它变成不可绕过的主流程门槛。源码语言标准与分析工具链版本也必须分离：Clang 21 是解析工具，`-std=c89`、`-std=c99` 等才是被分析源码的真实语义上下文。

## Goals / Non-Goals

**Goals:**

- 只要当前源码、成功 x86 构建、真实编译数据库和对应分析工具可用，就允许创建专项分析任务。
- 对每个翻译单元独立选择 AST-only 或 AST+BC，并准确报告项目级证据模式、覆盖率和降级原因。
- 让无 BC、全部 BC 失败、部分 BC 和完整 BC 都形成稳定、可审计的任务结果。
- 保留编译记录中的真实 C/C++ 标准和 GNU/ISO 方言，支持旧标准源码，不进行语义升级或伪造。
- 保持共享 BC 协议中立，使浮点和内存序工具消费相同身份与分母。
- 使用独立单元测试覆盖正常、异常和边界路径，并满足项目整体和受影响模块行/分支覆盖率至少 90%。

**Non-Goals:**

- 不保证 Clang 兼容所有历史编译器扩展、损坏的编译数据库或非 C/C++ 语言。
- 不把 AST-only 内存序候选提升为运行时已证明风险，也不宣称完成全程序并发安全证明。
- 不在专项分析阶段重新生成 BC、安装编译器或等待 BC 生产。
- 不改变 x86 用户构建的成功判定；BC 仍是非阻断副产物。
- 不为旧任务重新执行扫描或重写不可变结果制品。

## Decisions

### 1. 将启动条件与证据能力分离

专项分析的硬前置条件为：当前源码版本、同 Context 的成功 source/x86 构建、真实且可读取的 `compile_commands.json`、可用的分析器 runtime。BC 由独立 resolver 分类，不参与任务是否可创建的最终布尔判断。

resolver 输出：

| BC 情况 | 项目分析模式 | 行为 |
|---|---|---|
| v2 manifest 与 bundle 校验成功，全部计划 TU produced | `AST_BC_COMPLETE` | 所有可规划 TU 执行 AST+BC |
| v2 制品校验成功，至少一个 TU produced，仍有 failed/missing | `AST_BC_MIXED` | produced TU 执行 AST+BC，其余可规划 TU 执行 AST-only |
| manifest/bundle 缺失、BC 状态 FAILED/UNSUPPORTED/NOT_ATTEMPTED、produced=0 | `AST_ONLY` | 不 materialize BC，仅执行 AST |
| manifest/bundle 损坏、摘要或源码身份不匹配 | `AST_ONLY` | 禁止消费该 BC，记录不可重试的 BC 降级诊断后继续 AST |

选择降级而非阻断，是因为不消费无法验证的 BC 不会污染 AST 证据；诊断和覆盖分母仍必须公开，不能将其描述为完整分析。

### 2. 以完整编译数据库规划 AST，以 manifest 关联可选 BC

materializer 首先独立获取源码和 `compile_commands.json`，从全部合法 C/C++ compile entry 建立 TU 分母。BC resolver 再按源码相对路径、physical TU ID、context ID、compile record digest 和源码摘要关联 produced records。

不得再用 produced record 列表裁剪编译数据库。无法唯一关联的 BC 只对相应 TU 禁用 IR；该 TU 仍可执行 AST。manifest 中存在但编译数据库不存在的 record 作为审计诊断，不进入源码计划。

### 3. 两个工具采用各自原生的 AST-only 入口

浮点扫描请求在 `AST_ONLY` 模式省略 `bitcode_artifact_set`；混合和完整模式提供只包含已验证成员及完整失败分母的适配 manifest。浮点扫描器继续先生成全部 AST facts，再仅为已关联成员提取 LLVM facts。

内存序 adapter 在所有模式下都从编译数据库生成可信 `SourceSemanticRequest`。无 BC 的 record 以缺失 IR 证据进入统一 bundle，协调器据此产生 `ast-only` TU mode、source candidate、frontier 和 evidence break；有 BC 的 record 使用 `ast-ir`。Java 不接管工具内部阶段编排。

### 4. 运行记录显式保存证据模式

`specialized_analysis_runs.artifact_set_id` 改为可空，并增加或等价稳定持久化以下运行快照：

- `analysis_mode`：`AST_ONLY`、`AST_BC_MIXED`、`AST_BC_COMPLETE`；
- `bc_status`：构建侧 BC 状态或 `INVALID`/`MISSING`；
- `bc_planned_count`、`bc_usable_count`、`bc_failed_count`；
- 双语或稳定原因码形式的 degradation diagnostics。

任务输入中的 manifest、bundle 和 artifact-set ID 改为同进同出的可选组合，禁止出现仅提供其中一部分的状态。列表、详情、latest、readiness 和结果摘要使用同一投影。

### 5. 语言标准采用“基础标准 + 原始方言”模型

共享协议版本化扩展每个 record 的语言上下文：

- `language`：`c` 或 `c++`；
- `standard`：规范化基础标准，例如 `c89`、`c99`、`c11`、`c17`、`c23`、`c++98`、`c++03`、`c++11`、`c++14`、`c++17`、`c++20`、`c++23`；
- `dialect`：实际参数语义，例如 `iso9899:1990`、`gnu89`、`gnu99`、`gnu++03`；
- `standard_source`：`explicit` 或 `compiler-default`；
- `standard_option`：存在时保留脱敏后的原始 `-std=` 值。

别名只做等价规范化，例如 C90/ISO 1990 可映射到基础标准 C89，C18 可映射到 C17；GNU 方言必须通过 `dialect` 保留，不能降成纯 ISO 标准。没有 `-std` 时不得猜测为 C17/C++17，而应记录 `compiler-default`，并保留编译器身份供复现。

Clang 工具链版本不限制源码标准。工具根据真实参数重放 AST；某条规则依赖后续标准能力时按 TU 标记不适用或 unknown，而不是拒绝整个任务。

### 6. 协议版本化而不是原地扩大旧枚举

共享 BC manifest 和内存序生产协议需要次版本或新主版本演进，消费者在支持新版本前必须明确拒绝，而不能误读。后端同时读取现有 v2 完整 BC 记录和新协议记录；旧记录按其原始四标准语义消费。新生产任务只写新版本。

浮点扫描器生产请求 schema 已允许不提供 BC，语言标准主要来自编译参数；本次补充协议投影与验证语料。内存序工具需同步扩展生产 schema、source profile、统一分析 schema 和规则适用性，但 validation report 中固定的历史四语言基线不应被伪装为新标准已验证，需新增独立旧标准分母。

### 7. 质量验证使用离线 fixture 与 mock 连接

后端单元测试 mock repository、对象存储、进程、任务和 artifact connection 的返回值，不连接 PostgreSQL、RabbitMQ、MinIO、SSH 或 Docker。两个工具使用本地固定 compile database、源码、manifest 和最小 BC fixture，覆盖：

- 完整 BC、部分 BC、零 BC、缺失制品、损坏/身份不匹配制品；
- C89/C90/C99 及 GNU 方言、C++98/C++03、现有四标准、无 `-std`、未知标准；
- PARTIAL 中无 BC TU 仍进入 AST；
- 单 TU 不支持不阻断其他 TU；
- AST-only 结果不被提升为完整 IR 结论。

覆盖率统计必须纳入未被测试加载的项目自有生产源码，并将其按 0 命中计入分母，防止未执行模块从报告中消失而虚高覆盖率；测试代码、fixture、第三方依赖和生成代码不进入覆盖率分母。后端 Maven/JaCoCo、浮点扫描器 pytest coverage、内存序分析器 Python/C++ coverage 均执行项目整体和受影响模块门禁；行覆盖率和工具可用的分支覆盖率均至少 90%。

## Risks / Trade-offs

- [AST-only 结论能力弱于 AST+BC] → API 和报告显式展示模式、BC 覆盖分母、frontier 与证据断点，禁止使用“完整”措辞。
- [旧标准和 GNU 扩展扩大解析边界] → 保留原始方言，按 TU 隔离失败，新增真实 Clang fixture；不通过删除参数强行解析。
- [内存序协议中多处四标准枚举导致修改面较大] → 统一语言标准 value object/validator，再让 schema 和各阶段复用，避免继续散落白名单。
- [损坏 BC 被降级后可能掩盖基础设施故障] → 分析可以继续，但运行摘要、task log 和 readiness capability 必须返回稳定降级原因；运维仍可据此修复 BC。
- [数据库字段演进影响历史记录] → 新字段允许空值，旧记录按 artifact-set 和结果摘要尽力投影为 legacy mode，不重写历史制品。
- [Clang 新版本并不兼容全部历史编译器行为] → 明确区分“语言标准可解析”和“厂商扩展完全兼容”，无法重放时按单 TU unknown/unsupported 处理。

## Migration Plan

1. 先增加兼容性数据库变更和响应字段，使旧应用代码仍能读写现有记录。
2. 发布共享 BC 新协议及 producer；保持后端读取既有 v2 的能力。
3. 扩展内存序和浮点工具的标准处理、AST-only/混合测试，再更新 worker 镜像中的工具。
4. 更新后端 resolver、adapter、创建校验和 API 投影，启用新分析模式。
5. 运行后端及两个工具的单元测试、覆盖率和离线协议集成测试，再用固定 E2E fixture 验证完整、部分和无 BC 三条路径。

回滚时可回退应用和 worker 镜像；数据库新增可空字段保留。新协议制品不可由旧消费者使用，但不会影响原始 x86 构建结果，回滚后可重新生成旧兼容 BC 或仅查询既有任务。

## Open Questions

无。初始实现以 C89/C90、C99、C11、C17/C18、C++98/C++03、C++11、C++14、C++17、C++20 及对应常见 GNU 方言为必测范围；C23/C++23 按当前 Clang 能力接受并审计，但不在首轮规则准确率承诺范围内。
