## 1. 基线、协议与兼容边界

- [x] 1.1 记录实施前 P1–P4、A1、A2 schema/协议、CLI、固定 truth、缓存和报告黄金摘要，增加未请求 A3 时结果不变的回归断言。
- [x] 1.2 定义 `CppThreadLifecycleRequest v1`、`CppThreadLocalFacts v1`、`CppThreadLifecycleGraph v1`、`CppThreadLifecycleReport v1` 和公共引用/完整性/预算字段的 JSON Schema。
- [x] 1.3 增加 A3 协议数据类、canonical serialization/digest、严格 unknown-field/version/reference/profile 校验和中英文错误代码。
- [x] 1.4 定义显式 scope/root、P1/P2/P3/A1/A2 依赖、标准库模型选择和分层预算的请求验证规则，拒绝混合 profile 与替换依赖。
- [x] 1.5 为合法、未来版本、未知字段、悬空/调包依赖、重复身份、混合 target/profile 和预算非法输入补充协议单元测试。
- [x] 1.6 将所有新增 C++/Python/schema/runner 模块纳入构建、安装、源码枚举和缺失 coverage 报告即失败的质量入口。
- [x] 1.7 固定旧缓存 namespace 与 A3 新 namespace 的隔离规则，验证缺少 A3 产物不会被解释为无 C++ 线程。
- [x] 1.8 校验 OpenSpec delta 与实现协议命名、版本、退出语义和既有 P1–A2/P4 不变边界一致。

## 2. 标准库 profile 与开发环境

- [x] 2.1 定义 `CppThreadLibraryProfile v1`、模型注册项、采用结果和 profile gap schema，覆盖 vendor/version、C++ ABI、target、DataLayout、异常/RTTI、线程后端、头文件与 wrapper digest。
- [x] 2.2 扩展 GCC/Clang C++ compilation profile 探测并记录生产/分析标准库、driver 默认、sysroot/resource-dir 和可复现 fingerprint；保持 C11/C17 profile 不依赖 C++ 字段。
- [x] 2.3 在 `Dockerfile.dev` 与依赖锁中加入可离线验证的 libstdc++ 和 libc++ 开发组件，不修改生产 Dockerfile，并记录镜像/包版本。
- [x] 2.4 在锁定开发镜像实测至少一个 libstdc++ profile 的构造、entry broker、join、detach 和 handle-transfer ABI，生成有 provenance 的注册项。
- [x] 2.5 在锁定开发镜像实测至少一个 libc++ profile 的对应 ABI 路径并生成独立注册项；环境不可用时保留 required gate 未完成。
- [x] 2.6 实现逐项 profile 采用和 wrapper signature/layout/calling-convention 校验，禁止名称近似或 vendor 相同但 digest 漂移时采用。
- [x] 2.7 实现标准库系统边界角色归约与底层 pthread broker 标记，防止同一 create/join 被 A3 和用户 pthread 模型双重计数。
- [x] 2.8 为两个 vendor 的匹配、版本/target/ABI/配置/wrapper 漂移、未知调用逃逸、注册项更新和 cache 失效补充单元测试。

## 3. C++ 源语义与跨 TU callable

- [x] 3.1 扩展 source worker 的 A3 sidecar 提取，记录 `std::thread` 构造、move、join、detach、joinable、析构、线程对象和异常/控制上下文，不修改 `SourceSemanticFacts v1` 原义。
- [x] 3.2 提取自由函数、lambda closure/call operator/capture、成员函数/receiver 和简单 functor `operator()` 的 canonical entity、模板 specialization 与实参关系。
- [x] 3.3 明确并实现首版 callable 边界：唯一非虚目标、有限 capture/receiver；重载未消解、虚调用、复杂 `std::bind`、通用函数指针和对象逃逸进入 unknown。
- [x] 3.4 扩展 ProgramEntityIndex adapter 解析跨 TU callable declaration/definition、inline/template/COMDAT、internal linkage 与系统外部边界，不按名称补选定义。
- [x] 3.5 为自由函数、lambda、成员函数、functor、跨 TU、同名 static、ODR/COMDAT、definition 缺失和候选超限补充 C++ source/entity 单元测试。
- [x] 3.6 增加 AST-only `std::thread` source candidate，断言只输出 source-only/unknown 且不生成 ThreadInstance、start/join、MHP、RF/SW/HB 或风险结论。
- [x] 3.7 回归 C11/C17 pthread、C linkage、struct/union、宏和 C atomic 提取，证明 A3 source 路径未加载 C++ AST/标准库模型。

## 4. IR 局部事实与 Source/IR 绑定

- [x] 4.1 扩展 LLVM thread worker 的 A3 sidecar，提取 wrapper 调用、参数角色、calling convention、返回/异常出口、对象/native-handle token、move 与 join/detach 候选。
- [x] 4.2 实现 construct-attempt、entry-broker、join-attempt、detach-attempt、handle-transfer 等规范化角色与原始 IR/分析证据登记。
- [x] 4.3 实现线程对象和 handle 的受限 load/store/cast/phi/select provenance，禁止共享/逃逸/未知调用或候选超限时产生唯一所有权。
- [x] 4.4 扩展 SourceIRBinding A3 sidecar，将构造、对象操作、callable/receiver/capture 与 wrapper/call/value/token 按 exact/candidate/ambiguous/unresolved 及基数绑定。
- [x] 4.5 支持无 debug 时基于 caller/entity/ABI/object 的精确或候选绑定，并在 callsite 仍多义时保持 partial，不以行号或符号名强行 exact。
- [x] 4.6 实现标准库 broker 内底层 pthread 调用去重与来源冲突检测；不确定归属时同时保留候选和 gap。
- [x] 4.7 为 wrapper 一对多展开、无 debug、异常出口、phi/select、多对象、ABI mismatch、伪造/陈旧引用和用户自定义同名 wrapper 补充 C++ 单元测试。

## 5. 线程对象状态机与生命周期图

- [x] 5.1 实现 `empty`、`construction-pending`、`joinable`、`joined`、`detached`、`moved-from`、`failed`、`terminated-path`、`unknown` 状态格及确定合并/排序。
- [x] 5.2 实现构造成功、抛出/失败、正常/异常出口和 callback 启动的 guarded 状态转移，禁止仅凭构造语句生成 thread-start。
- [x] 5.3 实现 move construction 的对象/handle/实例 lineage 转移与源 moved-from 状态。
- [x] 5.4 实现 move assignment 的空目标、目标可能 joinable、self move、覆盖、phi/select 和异常/terminate 保守语义。
- [x] 5.5 实现 joinable 查询 guard、join/detach 正常与异常/错误路径、重复操作和 moved-from 操作的状态转移。
- [x] 5.6 实现析构时 empty/joined/detached/moved-from 与可能 joinable 的区分；joinable 析构只产生 terminate/unknown，不生成隐式 join/detach。
- [x] 5.7 实现 callback/参数/profile/scope 相关 ThreadContext 与 root/父实例/构造调用/对象 lineage/guard 相关 ThreadInstance，禁止缓存实例串用。
- [x] 5.8 实现循环、递归/互递归构造的 merged/repeated 实例桶、cardinality、自并行语义、固定点与非空 frontier。
- [x] 5.9 为每个状态转移、非法/未知合并、同 callable 多构造点、重复实例、递归和各类预算耗尽补充状态机与图单元测试。

## 6. P3 关系组合与 A2 降级传播

- [x] 6.1 实现 A3 graph 到既有 P3 thread identity 的显式 adapter，只引用 `ThreadContextGraph v1` 并保持 P3 JSON/缓存原义不变。
- [x] 6.2 仅在 callback、构造成功、对象/handle、worker exit、join 成功和父后继执行顺序完整时组合 worker-exit → join-complete → parent-successor 条件关系。
- [x] 6.3 实现 detach 后保持 may-parallel、joinable/析构/源码顺序/P2 order 不产生完成边，以及失败 join 不消解 MHP 的负向规则。
- [x] 6.4 生成标准库 profile、ABI wrapper、callable、object/handle/move、构造/join/detach 结果、异常、scope 和预算分类的结构化 A3 gap。
- [x] 6.5 扩展 A2 依赖切片纳入 A3 TU/entity/object/call/thread/path/protocol 依赖：相关 gap 降级，已证明无关 gap 仅影响顶层完整性。
- [x] 6.6 验证未知 RAII mutex 继续产生 SynchronizationGap，已解析 `std::thread` 生命周期不得被误用为互斥、SW/HB 或 P4 discharge。
- [x] 6.7 为完整 join、detach、异常 join、moved-from、相关/无关 gap、C pthread 与 C++ broker 共存及旧 P4 候选组合补充单元和适配回归。

## 7. CLI、缓存、报告与双语诊断

- [x] 7.1 实现 `model-cpp-thread-lifecycle` CLI 的 request/artifact-store/output/source-worker/ir-worker 参数、空输出目录约束和 0/2/1 退出码。
- [x] 7.2 实现 source/profile/local-facts/binding/graph/report 分层缓存，key 包含 schema/policy、全部依赖、标准库 profile/model、工具链和预算类别。
- [x] 7.3 防止 transient timeout/crash 和 partial wall-clock 结果作为长期语义缓存命中，并实现损坏/替换 cache 的确定拒绝。
- [x] 7.4 实现稳定排序、canonical semantic digest 和 cold/warm 语义一致性比较。
- [x] 7.5 实现 `CppThreadLifecycleReport v1` 的 TU、profile、callable、对象、context/instance、关系、gap/frontier、预算、缓存和既有 P3 引用字段。
- [x] 7.6 为所有 failure/gap/unknown 提供稳定 code、中文 detail/suggestion 和英文 detail_en/suggestion_en，并加入 schema 与断言。
- [x] 7.7 为合法 complete、partial/unknown、所有计划失败、输出冲突、缓存损坏、未来 schema、profile mismatch 和双语字段补充 CLI/report/cache 单元测试。

## 8. 四语言语料与语义 truth

- [x] 8.1 建立 C++17 libstdc++ 单 TU/跨 TU 自由函数、lambda、成员函数和 functor fixture，人工裁决 callback、对象、实例与生命周期 truth。
- [x] 8.2 建立 C++20 libc++ 对等 fixture，并确保 truth 与 vendor-specific wrapper 证据分层，不按另一 vendor 结果推断。
- [x] 8.3 增加 move construction/assignment、joinable、join、detach、析构、构造失败/异常和重复操作的正反/unknown fixture。
- [x] 8.4 增加无 debug、开放 scope、definition 缺失、ABI/profile mismatch、wrapper 漂移、对象逃逸、循环/递归和预算 fixture。
- [x] 8.5 固定 C11/C17 直接 pthread create/join 单 TU/跨 TU 正常、失败和 unknown 回归，不加载 C++ 模型。
- [x] 8.6 实现生命周期 truth 比较器，分别统计 callable、instance、start/join/detach relation 的 expected/actual、exact、FP/FN 和 unknown。
- [x] 8.7 分别报告 C11、C17、C++17、C++20 的 planned/completed/failed/unknown/abstention，不用合并分母掩盖任一语言缺口。
- [x] 8.8 保持 A3 lifecycle 指标与既有 P4 risk TP/FP/FN 独立，增加禁止从 exact match 或零 finding 推导全程序安全的文档/报告断言。

## 9. 单元覆盖率、离线集成与性能验收

- [x] 9.1 为所有新增/修改/复用 C++ 模块补齐正常、边界、异常、unknown 单元测试，并验证未调用源码和可执行头文件进入分母。
- [x] 9.2 为所有新增/修改/复用 Python 模块补齐协议、profile、binding、状态机、graph、adapter、cache、CLI、report 和质量门禁单元测试。
- [x] 9.3 扩展质量脚本逐模块检查，实际测试 89.99%、90%、缺失报告、未加载模块和分支不足边界。
- [x] 9.4 在锁定开发容器的全新目录运行完整 C++ 与 Python 单元测试，验证项目整体、C++、Python 和每个受影响模块行覆盖率、分支覆盖率均至少 90%。
- [x] 9.5 独立运行四语言离线语义矩阵、libstdc++/libc++ profile、旧 P1–A2/P4、C pthread 和 unknown RAII 回归，不把集成 profile 合入单元覆盖率。
- [x] 9.6 运行固定 cold/warm 请求，记录 wall/CPU/peak RSS/输出大小、cache hit/miss 和相同 semantic digest；语义漂移或瞬态缓存复用必须失败。
- [x] 9.7 运行节点、候选、实例、递归、输出和墙钟预算边界，断言保留 hit/total、已知事实和非空 frontier，退出码为 partial。
- [x] 9.8 审核第三方、生成物和纯 fixture 排除项，确保项目自有业务/错误处理/质量逻辑没有因难测被排除。

## 10. 文档、验收记录与交付

- [x] 10.1 编写 `doc/CPP_THREAD_LIFECYCLE.md`，说明架构、协议、CLI、标准库支持矩阵、callable/对象状态机、证据链、退出码和明确边界。
- [x] 10.2 编写 `doc/CPP_THREAD_LIFECYCLE_VALIDATION.md`，记录实际容器命令、工具/标准库 fingerprint、测试数、四语言分母、truth、性能、缓存和 line/branch hit/total。
- [x] 10.3 生成机器可读 acceptance JSON，包含依赖 hash、profile/model、required gate、模块覆盖率、truth、cold/warm、排除项和报告位置。
- [x] 10.4 更新 `doc/IMPLEMENTATION_ROADMAP.md`、`doc/README.md`、项目 README 与 OpenSpec context，标明 A3 实际状态和 A4/A5/A6 后续依赖，不提前宣称完成。
- [x] 10.5 增加文档链接、机器清单/schema、支持矩阵与“非安全证明”措辞的自动化测试。
- [x] 10.6 在全新报告目录执行最终统一质量入口与独立集成，保存精确命令和结果；任一测试、truth、profile 或 90% 门槛失败时保持任务未完成。
- [x] 10.7 执行 `openspec validate --all --strict`、schema/协议校验和 `git diff --check`，确认 change 仅修改本项目且未引入远程运行依赖。
- [x] 10.8 复核全部任务、proposal/design/spec 一致性和最终 evidence provenance；只有 required gate 全部通过后才允许提示 sync/archive。
