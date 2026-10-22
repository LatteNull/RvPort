## Context

`demo-test1` 的真实分析 `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a` 暴露了三条彼此独立、但最终都表现为证据不足的链路缺陷：

1. 构建运行已经发布 `SharedLlvmBitcodeArtifactSet@2.0`，4 个 produced BC 与 bundle 完整匹配，但当前 Java 模型读取旧 manifest 后注入 `dialect`、`standard_source`、`standard_option` 三个空字段，再按新版对象重算 canonical digest，导致全部 BC 被判为 `INVALID`。
2. 测试翻译单元中的 Clang `<scratch space>` 被解析为项目 `build/` 下的真实文件，1222 个系统声明进入 source facts，其中 208 个系统 `long double` 函数被当成项目 ABI 边界，超过 128 条 provenance 上限。
3. conversion mapper 通过类型文本是否包含 `float`/`double` 判断浮点转换，函数指针、浮点指针和 `std::array<float, N>` 因而进入标量精度规则。三个翻译单元的转换端点类型均存在，但 6、23、50 个非标量候选使整个 TU 返回 `conversion_type_unknown`。

当前系统的安全降级本身是正确的：不可验证的 BC 不应交给扫描器，缺少决定性证据时也不应伪造结论。本设计修复的是“可信输入被错误拒绝”和“无关节点被错误视为阻断证据”，而不是取消校验、扩大预算或放宽 unknown 语义。

约束如下：

- OpenSpec source of truth 仅为 `backend/openspec`；工具目录内已有 specs/docs 作为实现时必须同步的交付物，不建立第二个 change。
- 不修改 frontend 或其他分析工具，不重写历史 result/artifact。
- 外部结果继续使用现有 KB Scanner v2 结构。
- source-preserving BC 只证明其声明的能力，不能冒充 build-faithful IR。
- 实现和测试在 Linux Docker 中验收，独立单测 mock SSH、对象存储、数据库、进程和其他外部服务。

## Goals / Non-Goals

**Goals:**

- 使 schema 2.0 与 2.1 manifest 按各自原始字段集合通过相同 canonical identity 算法验证，同时继续拒绝真实篡改和未知版本。
- 保留 BC 校验失败的最接近根因，并让运行摘要明确区分 producer partial、consumer validation invalid 和 scanner/LLVM worker failure。
- 统一项目翻译单元口径，分离 raw command、C/C++ candidate、项目 TU、produced/failed/missing/excluded 数量。
- 只让真实项目 C/C++ 节点形成 canonical source facts；虚拟文件、系统声明和构建探针不得污染规则候选或项目覆盖分母。
- 以 canonical scalar type 驱动 conversion facts，并把 unknown/unsupported 限定到真正受影响的候选和规则依赖。
- 让 `long-double-abi` 使用真实项目边界、去重声明和有界直接证据，不通过提高协议上限解决问题。
- 通过 facts producer/schema 升级安全失效旧缓存，保持确定性、原子输出、双语诊断和历史不可变。
- 以单元测试、覆盖率、validation corpus、固定 benchmark 和 `demo-test1` 真实 API 前后对照证明修复。

**Non-Goals:**

- 不新增第十一类浮点规则，不改变业务容差，不实现动态差分执行或 AI 判断。
- 不生成新的 build-faithful BC，不把 `-O0` source-preserving BC解释为生产优化结果。
- 不取消 AST-only、`PARTIAL`、unknown 或 evidence budget，不把结果强制改为 `COMPLETE`。
- 不修改 KB Scanner v2 顶层结果协议，不迁移或补写历史扫描结果。
- 不改变 frontend 展示，不修复 memory-order 或其他专项分析工具。

## Decisions

### 1. Canonical digest 对原始 schema 表示计算

后端先把 manifest 解析为受限 `JsonNode`，完成大小、深度、字段类型和 schema 版本检查，再同时建立：

- 用于身份验证的原始 schema 表示；
- 用于后续语义校验和 adapter 的强类型模型。

schema 2.0 record digest 只包含 2.0 定义的字段；schema 2.1 digest 包含 2.1 定义的 `dialect`、`standard_source`、`standard_option`。缺失字段与显式 `null` 不得在版本之间互相伪装。manifest、record、scope 和 artifact-set identity 均使用同一版本描述表，Java 测试向量必须与 Python producer 一致。

选择原始 schema 表示而不是通过 Jackson `NON_NULL` 全局配置解决，是因为全局忽略空值会改变其他协议的身份语义，也无法区分“旧版本不存在字段”和“新版本非法地提供 null”。未知 schema 继续明确拒绝，不进行猜测迁移。

### 2. 校验失败使用结构化阶段和原因，不携带不安全原文

BC 校验路径引入内部结构化失败对象，至少包含：

- `stage`：manifest parse、schema、identity、bundle layout、member digest、source/compile binding 或 materialization；
- 稳定 `reasonCode`；
- schema、producer/toolchain、artifact-set/stored-artifact 安全身份和预期/实际摘要的短安全表示；
- `retryable`、中文/英文消息和建议。

运行时捕获后将其写入任务事件、运行摘要和 request/result 的降级信息；绝对路径、对象 key、凭据、源码和堆栈不进入默认输出。不可识别异常仍映射为通用内部错误，但必须保留失败阶段，不能冒充 LLVM worker 失败。

替代方案是继续只返回 `BITCODE_WORKER_VALIDATION_FAILED` 并依赖日志排查。该方案无法区分 manifest 兼容、bundle 损坏和 worker 错误，已被本次真实记录证明不可审计，因此不采用。

### 3. 分母由统一翻译单元规划结果产生

后端构建/分析共享一个确定性的 compile-entry 分类结果，分别记录：

- `rawCommandCount`：原始 compile database 行数；
- `cCppCandidateCount`：语法上属于 C/C++ 编译的条目数；
- `projectTranslationUnitCount`：进入项目 AST 计划的唯一 TU/context 数；
- `produced/failed/missing`：与项目 TU 对应的 BC 状态；
- `excludedCount` 及稳定原因：非 C/C++、重复上下文、CMake/compiler probe、构建系统内部文件、根外路径等。

BC manifest 可以继续保存生产侧完整记录，但浮点分析覆盖率以项目 TU 计划为分母，并通过 source path、physical TU、context 和 compile-record digest 关联 produced 成员。不能再对 raw command count 与 manifest planned count 取最大值。

生成源码不能仅因位于 build 目录就一律忽略；只有能够证明为构建探针或基础设施内部文件的条目才排除。无法分类但属于项目构建的 C/C++ 条目进入显式 unknown/excluded 审计，不能静默消失。

### 4. 源文件归属使用物理来源分类，不使用路径字符串偶然性

位置归一化先识别 Clang 虚拟来源：`<scratch space>`、`<built-in>`、`<command line>` 和等价 sentinel 永远不是项目物理文件，也不得相对于 compile directory 拼接。对于 spelling/expansion、`includedFrom` 和 file-elision，归属按下列顺序确定：

1. 可验证的物理 spelling/expansion 文件；
2. 已证明的父节点物理来源继承；
3. 顶层 main-file 省略规则；
4. 无法证明时为 unknown，不默认归入 main file。

项目根外系统声明不形成独立 source facts。若项目调用规则需要外部 API 身份，只从项目调用节点生成有界 external declaration summary，并明确其来源，不遍历导入整个系统声明子树。

### 5. Canonical scalar type 是 conversion 的唯一类型入口

新增统一类型归一化器，输入 Clang type object，输出 `floating`、`integer`、`other` 或 `unknown` 以及 canonical spelling、原始 spelling、脱糖来源和必要属性。它优先使用 `desugaredQualType`，只移除最外层 cv/restrict 修饰，不通过子字符串判断标量。

conversion fact 仅在 cast kind 表示数值转换，且目标为浮点标量、源为浮点或整数标量时建立；显式浮点到整数等其他已声明规则需要的转换按对应方向建模。pointer、function、member pointer、array、record/container 和未完成包装类型不进入 mixed-precision 标量候选。

若 cast kind 明确表示数值转换但某一端确实无法恢复，mapper 生成带候选身份和影响规则的 unknown conversion，而不是伪造类型。facts payload 保存 canonical 与原始/脱糖 provenance，便于审计 typedef、`auto`、宏和模板实例。

### 6. Unknown 与 unsupported 按规则依赖和候选传播

结构性 AST 节点分为：

- 已由子 facts 完整表达的 transparent/handled 节点，例如数组下标、初始化包装和赋值外壳；
- 与启用规则无关的非阻断 unsupported；
- 缺失某条规则所需语义的 blocking unknown。

blocking 记录必须包含受影响的 fact kind/rule dependency、候选或 scope 和稳定 reason。规则只消费与自身 dependency descriptor 相交的 blocking 记录。

mixed-precision 逐候选计算：确定损失可以形成 matched，不因同 TU 另一个无关 cast 失效；真正不可判定的数值转换保持 candidate-local unknown。若结果需要 TU 聚合，聚合摘要必须同时保留 matched、not-matched、unknown 分母和直接证据，不能用一个布尔 unknown 覆盖全部候选。

### 7. Long-double ABI 只处理声明边界并使用有界直接证据

候选必须同时满足：

- `fact_kind=type` 且 canonical type 确认包含 `long double`；
- origin 是真实项目物理文件；
- boundary kind 属于公开参数/返回、变参、外部记录布局、持久化或二进制边界；
- 声明身份去重后仍有效。

规则按稳定 declaration/boundary key 评估，finding 只引用该结论直接依赖的声明和两个 profile。多个边界使用已有 occurrence/aggregation 语义或稳定分组，不把整个 TU 的全部 type facts加入一条 evidence list。合法直接证据仍超过协议上限时继续使用现有 frontier/partial 语义，不提高 128 上限、不静默截断。

修正后的候选范围会改变判断语义和稳定 ID，因此 `long-double-abi` 与 `mixed-precision-conversion` 的 rule implementation version 必须按 registry 兼容规则提升；历史结果和旧 ID 保持不变。

### 8. Facts schema/producer 升级并安全失效旧缓存

canonical type provenance、origin 分类和 candidate-local blocking 信息属于 facts 语义变化，因此提升 facts schema 和 producer/mapper version。缓存 key 继续包含 schema、producer、Clang/LLVM、源码、编译上下文和 profile digest；旧缓存读取时产生受控 miss 并重新计算，不复制、就地修改或当作损坏输入。

冷缓存与热缓存必须产生相同 assessment、finding、diagnostic、稳定 ID、排序和 semantic digest。缓存迁移不改变 KB Scanner v2 输出版本。

### 9. 验收以真实状态而不是预设 COMPLETE 为准

先执行 backend 与 scanner 独立单测和覆盖率，再运行现有 validation corpus 与固定 benchmark，最后通过真实 API 以同 project/source/build 重新创建浮点分析。前后审计分别保存，至少对比：

- BC capability、manifest 校验和 AST/IR 层分母；
- long-double、mixed-precision、unsupported diagnostics；
- reduction finding 的 ID、位置、证据来源和人工确认字段；
- result schema、引用闭包、路径脱敏、稳定排序和退出码。

修复后预期三个项目 TU 均可使用有效 source-preserving BC，系统不再因系统声明报告 long-double，不再因非标量 cast 报 conversion type unknown；但 source-preserving 无法证明 build-faithful lowering 时，相关规则仍可合法返回 unknown/heuristic，最终状态由真实结果决定。

## Risks / Trade-offs

- [Risk] 版本感知摘要逻辑接受被伪造成旧版本的恶意字段组合 → schema 先严格限制版本允许字段，再计算 identity；增加跨语言有效/篡改测试向量。
- [Risk] 构建探针过滤误伤项目生成源码 → 只排除可证明的构建基础设施记录，保留分类原因和原始分母；模糊条目不静默删除。
- [Risk] 更严格项目边界漏掉项目宏或头文件事实 → 同时测试 main file、项目头、项目宏 spelling/expansion、系统宏和虚拟位置，无法证明时保守 unknown。
- [Risk] candidate-local assessment 增加结果数量或改变 ID → 提升规则实现版本，使用稳定候选键和聚合预算，保持历史结果不可变。
- [Risk] facts schema bump 降低首次运行缓存命中率 → 接受一次冷重算，验证后续热缓存等价，不做不安全的缓存原地升级。
- [Risk] 真实 BC 恢复后暴露新的合法 IR unknown → 保留 profile/capability 边界并在前后报告中单独说明，不以强制 COMPLETE 作为验收目标。
- [Risk] 后端详细诊断泄露路径或对象存储信息 → 只持久化安全身份和摘要，路径/异常原文经过既有脱敏与长度预算。

## Migration Plan

1. 先增加 schema 2.0/2.1 identity fixtures、结构化失败类型和分母模型测试，再修改后端校验与 capability resolver。
2. 升级 scanner facts schema/producer 和缓存身份，随后实现虚拟位置过滤、canonical scalar type 和 candidate-local unknown。
3. 调整 long-double/mixed-precision 规则版本及直接证据，并更新 v2 contract fixtures、validation oracle、工具主 specs/docs/roadmap。
4. 在 Linux Docker 中运行 backend、Python/C++ scanner 的单元测试、整体与受影响模块覆盖率、validation corpus、benchmark 和严格 OpenSpec 校验。
5. 部署后以原 project/source/build 创建新的浮点分析；历史 analysis 和制品只读保留，修复前后审计写入新的验证目录。
6. 若新版出现回归，回滚应用版本即可；旧缓存因版本键不同不会污染回滚版本，历史结果无需数据回滚。

## Open Questions

无阻断性开放问题。实现阶段必须以现有 schema 文件和 registry 的版本策略确定具体新 facts/rule version，不得在不提升版本的情况下改变稳定身份语义。
