## 1. 基线、协议与兼容边界

- [x] 1.1 记录实施前 P1–P4、A1–A3 schema/协议、CLI、缓存、四语言 truth 和报告黄金摘要，增加未请求 A4 时结果不变的回归断言。
- [x] 1.2 定义 `CppRaiiSynchronizationRequest v1`、`CppRaiiLocalFacts v1`、`CppRaiiSynchronizationGraph v1`、`CppRaiiSynchronizationReport v1` 及公共引用、节点、完整性和预算 JSON Schema。
- [x] 1.3 实现 A4 协议数据类、canonical serialization/digest、严格 version/unknown-field/reference/profile 校验和稳定中英文错误代码。
- [x] 1.4 定义显式 scope、P1/P3/A1/A2/A3/可选 P4 依赖、标准库同步模型选择和分层预算的请求规则，拒绝调包、悬空与混合 profile。
- [x] 1.5 为合法、未来版本、未知字段、重复 identity、依赖摘要漂移、非法预算、混合 target/profile 和缺失 A4 产物语义补充协议单元测试。
- [x] 1.6 建立原始 AST/IR 节点、A4 分析节点、mutex/owner/proof 实例的独立 identity 与引用验证，禁止跨命名空间冒充。
- [x] 1.7 将所有新增 C++/Python/schema/runner 模块纳入构建、安装、源码枚举和缺失 coverage 报告即失败的质量入口。
- [x] 1.8 校验 OpenSpec delta 与实现协议命名、版本、退出码及 P1–A3/P4 不变边界一致。

## 2. 标准库同步 profile 与开发环境

- [x] 2.1 定义 `CppRaiiSynchronizationProfile v1`、同步摘要注册项、采用结果和 profile gap schema，覆盖 compiler/standard/vendor/version/ABI/target/DataLayout/异常/RTTI/header/wrapper/model fingerprint。
- [x] 2.2 扩展 GCC/Clang C++ compilation profile 探测并记录 A4 identity 与缓存摘要，保持 C11/C17 profile 不加载 C++ 标准库字段。
- [x] 2.3 审核 `Dockerfile.dev` 与锁定依赖是否具备 required libstdc++/libc++ mutex/异常 probe；仅补开发镜像缺口，不修改生产 Dockerfile。
- [x] 2.4 在锁定开发镜像实际编译并提取至少一个 libstdc++ C++17/C++20 mutex/`lock_guard`/`unique_lock`/`scoped_lock` probe，记录 wrapper 与 cleanup provenance。
- [x] 2.5 在锁定开发镜像对至少一个 libc++ profile 完成等价实测和独立注册；环境不可用时保持 required gate 未完成。
- [x] 2.6 实现逐项 profile eligibility、系统边界、wrapper signature/layout/calling-convention/异常出口校验，禁止 vendor 相同或名称相似时近似采用。
- [x] 2.7 将 A4 profile 与 A3 共同编译 fingerprint 显式关联但独立版本化，验证 A3 eligible/A4 mismatch 时生命周期保留而同步降级。
- [x] 2.8 为两个 vendor 的匹配、版本/target/ABI/异常配置/header/wrapper 漂移、用户同名 helper、注册更新和 cache 失效补充单元测试。

## 3. C/C++ 源语义与跨 TU 实体

- [x] 3.1 扩展 source worker 的 A4 sidecar，记录 `std::mutex` 对象/字段和 RAII owner 的 canonical entity/type、构造/析构、move、显式 lock/unlock、owns-lock、lifetime 与 cleanup 候选。
- [x] 3.2 明确 `lock_guard`、受限 `unique_lock`/`scoped_lock` 的源级支持形状，并将 adopt/try/release/swap、try/timed/recursive/robust 或复杂 ownership 记录为稳定 unknown/frontier。
- [x] 3.3 保存模板实例、隐式析构、异常 cleanup、宏 spelling/expansion、对象/参数/字段路径及 profile identity，禁止从 AST scope 单独生成 acquire/release 或 HB。
- [x] 3.4 扩展 ProgramEntityIndex adapter，精确解析跨 TU 用户 mutex wrapper/RAII helper、全局/静态对象、常量字段、linkage/ODR/COMDAT 与系统外部边界。
- [x] 3.5 实现 C++ wrapper declaration/definition 唯一化、参数化 mutex 绑定和同名/weak/缺失 definition 的 conservative frontier，不扫描目录补选实体。
- [x] 3.6 为全局 mutex、结构体/对象字段、同名 static、跨 TU wrapper、隐式析构、move、恢复 AST、scope 外 definition 和候选超限补充 source/entity 单元测试。
- [x] 3.7 增加 AST-only mutex/RAII source candidate，断言只输出 source-only/unknown 且不生成动态 owner、held-region、SW/HB、risk 或 discharged。
- [x] 3.8 回归 C11/C17 的 C linkage、直接 pthread mutex、跨 TU wrapper、struct/union 字段和宏事实，证明 C 路径不依赖 C++ AST/profile。

## 4. LLVM 局部事实与 Source/IR 绑定

- [x] 4.1 扩展 LLVM thread worker 的 A4 sidecar，提取 mutex wrapper call/invoke、参数对象、返回状态、构造/析构/move、owner token、normal/exception successor 和 cleanup 候选。
- [x] 4.2 实现 profile 驱动的 lock/unlock/construct/destruct/transfer 角色识别与原始 IR/分析证据登记，不修改既有 P3 pthread facts。
- [x] 4.3 实现 mutex/owner 的受限 load/store/cast/GEP/phi/select/参数/返回 provenance，保留有限 may 集合并禁止候选超限时产生唯一身份。
- [x] 4.4 扩展 SourceIRBinding A4 sidecar，将 mutex/owner 操作、字段、wrapper、CFG 与 cleanup 按 exact/candidate/ambiguous/unresolved 及绑定基数连接。
- [x] 4.5 支持无 debug 时依据 caller/entity/ABI/object/CFG 的 IR 级绑定，并在多义时保留 partial，不以行号、mangled name 或类型强行 exact。
- [x] 4.6 实现系统 wrapper 与用户 wrapper 的归属冲突检测及底层 pthread 候选去重；不确定时保留双方候选和 gap。
- [x] 4.7 为 invoke/landingpad/cleanup/resume、正常/异常双析构、wrapper 一对多、字段 GEP、phi/select、ABI mismatch、伪造/陈旧引用补充 C++ worker/binding 单元测试。
- [x] 4.8 回归直接 C pthread lock/unlock 的 IR 事实、对象、失败路径和无 debug 行为，确认 A4 不覆盖或重复既有 P3 事件。

## 5. Mutex、owner 状态机与 held-region

- [x] 5.1 实现 `uninitialized`、`owns`、`deferred`、`moved-from`、`released`、`unknown` 状态格、guard、合并顺序与稳定序列化。
- [x] 5.2 实现 `lock_guard` 构造成功/失败、正常/异常析构和访问包含关系；任何未闭合出口不得产生 must-held proof。
- [x] 5.3 实现 `unique_lock` 默认立即加锁、`defer_lock` 后唯一成功 lock、owns-lock guard、显式 unlock 和析构的受限状态转换。
- [x] 5.4 实现 `unique_lock` move construction/assignment 的 ownership token 转移、moved-from 禁止 release、目标已有 ownership 和 self-move 的保守语义。
- [x] 5.5 实现固定小规模 `scoped_lock` 的 mutex 集合 identity、全部成功 acquire、逆序 release 与任一元素未知时整体 proof 降级。
- [x] 5.6 实现 `MutexInstance` 与 `RaiiOwnerInstance` 分离、全局/静态/参数/返回/常量字段对象 identity，以及 may-alias 禁止提升 must-same-mutex。
- [x] 5.7 从状态转换、CFG/cleanup 和绑定生成 acquire/release attempt、成功事件、held-region、访问 containment 与非空 frontier。
- [x] 5.8 为构造抛出、提前返回、异常 cleanup、move、重复 lock/unlock、adopt/try/release/swap、不同 mutex、字段歧义和各预算耗尽补充状态机单元测试。

## 6. 跨调用摘要与受限同步证明

- [x] 6.1 定义参数化 A4 wrapper 摘要，描述 mutex 参数、owner 状态、acquire/release、异常出口、访问 containment、未知 effect 和证据引用。
- [x] 6.2 实现确定直接调用与跨 TU wrapper 的调用点实例化、对象/guard 重绑定、返回 owner 传播和调用上下文 identity。
- [x] 6.3 实现递归/互递归 wrapper 的 SCC/有界迭代、may/must 合并和未收敛 partial，禁止空摘要冒充无锁。
- [x] 6.4 实现受限 mutex proof gate：同一普通非 robust mutex、成功 acquire、成对 release、闭合 held-region、明确线程实例与候选相关完整性。
- [x] 6.5 实现 unlock→后续成功 lock 的条件化同步候选和同 mutex 临界区互斥，不计算通用 HB 传递闭包。
- [x] 6.6 禁止 AST scope、源码顺序、P2 order、P3 reads-from、A3 join/detach、函数/类型名或单个 lock presence 单独产生 SB/SW/HB/互斥。
- [x] 6.7 为同/不同 mutex、may-alias、缺失 release、失败 lock、异常路径、跨 TU 参数、递归未收敛和 unknown kind 补充摘要/proof 单元测试。
- [x] 6.8 固定首版不支持的 recursive/robust/try/timed mutex、condition variable、semaphore、rwlock 和自定义同步代码及中英文 frontier。

## 7. P3、A3、A2 与 P4 组合

- [x] 7.1 实现 A4 graph 对 P3/A3 `ThreadContext`/`ThreadInstance`、MHP 和生命周期的只读 adapter，保持旧 graph、identity、join/detach 和缓存语义不变。
- [x] 7.2 将 owner/held-region 与明确线程实例绑定，循环/递归 merged/repeated 实例保留 may/cardinality，不以一次临界区覆盖全部动态实例。
- [x] 7.3 扩展 A2 候选依赖切片，按 TU/entity/object/call/thread/path/profile/protocol 将 A4 proof 与 `SynchronizationGap` 精确关联。
- [x] 7.4 只有同候选完整 A4 proof 才关闭 `unmodeled-raii-lifetime`、mutex/wrapper gap；无关、may、AST-only 或 partial proof 必须保留原 gap。
- [x] 7.5 实现 P4 对完整 A4 mutex proof 的显式消费，保持 `SinglePublicationProtocolGraph`、finding/discharged/unknown、safety 与 0/3/2/1 语义不变。
- [x] 7.6 禁止 A4 mutex proof 替代 atomic RF、modification order、release sequence、fence 或 relaxed publication 证明。
- [x] 7.7 为完整/partial RAII、无关 mutex、不同线程、A3 join/detach、C pthread 与 C++ RAII 共存、正式风险加相关 gap 补充 adapter 单元测试。
- [x] 7.8 将锁定 `safe/03_pthread_mutex.cpp` 在完整证据时从 A2 unknown 变为受限模型消解，并保留 profile/path/object 不完整时的 unknown 反例。

## 8. CLI、缓存、预算与双语报告

- [x] 8.1 实现独立 A4 CLI 的 request/artifact-store/output/source-worker/IR-worker 参数、空输出目录约束和 0/2/1 退出码，禁止 A4 自身返回风险码 3。
- [x] 8.2 实现 source/profile/local-facts/binding/summary/graph/report 分层缓存，key 包含 schema/model、全部依赖、toolchain/profile、预算类别和实现 identity。
- [x] 8.3 防止 transient timeout/crash、partial wall-clock 和 profile mismatch 结果成为长期语义缓存命中，并确定拒绝损坏/替换 cache。
- [x] 8.4 实现 TU、节点、profile、mutex/owner、wrapper、上下文、状态转换、held-region、relation、递归、输出和时间预算及 hit/limit/frontier 传播。
- [x] 8.5 实现稳定排序、canonical semantic digest 和相同依赖下 cold/warm 语义一致性比较。
- [x] 8.6 实现 A4 report 的 profile、mutex、owner、thread、held-region、proof、gap/frontier、预算、缓存和 P3/A3/P4 引用字段。
- [x] 8.7 为全部 failure/gap/unknown/proof 提供稳定 code、中文 detail/limitation/suggestion 和英文对应字段，机器 identity 与翻译分离。
- [x] 8.8 为 complete-zero-candidate、完整 proof、partial/unknown、全部失败、输出冲突、缓存损坏、future schema、profile mismatch 和双语字段补充 CLI/report/cache 单元测试。

## 9. 四语言 truth、单元覆盖率与离线验收

- [x] 9.1 建立 C11/C17 直接 pthread mutex 的单 TU、物理跨 TU wrapper、全局/struct/union 字段、同/不同 mutex、未知 kind 和无锁正反例 truth。
- [x] 9.2 建立 C++17 libstdc++ 的 `mutex`/`lock_guard`、受限 `unique_lock/scoped_lock`、move、异常、字段、跨 TU、无 debug 和开放 scope truth。
- [x] 9.3 建立 C++20 libc++ 对等 truth，并将 vendor-specific wrapper/profile 证据与语义期望分层，禁止由另一 vendor 推断。
- [x] 9.4 锁定归档 `safe/03_pthread_mutex.cpp` 的本地最小副本、来源 hash、capability 和人工 truth；日常测试不读取 sibling archive。
- [x] 9.5 增加 profile/ABI mismatch、wrapper 漂移、definition 缺失、对象歧义、try/timed/recursive/robust、自定义同步和预算 unknown fixture。
- [x] 9.6 实现 A4 truth 比较器，分别统计 mutex/owner/thread/held-region/proof 的 expected/actual/exact、TP/FP/FN、strict 指标和 abstention。
- [x] 9.7 分别报告 C11、C17、C++17、C++20 planned/completed/eligible/failed/unknown，禁止合并分母掩盖任一语言或 vendor 缺口。
- [x] 9.8 为全部新增/修改/复用 C++ 和 Python 模块补齐正常、边界、异常、unknown 单元测试，验证未加载源码和可执行头文件进入覆盖分母。
- [x] 9.9 扩展质量门禁并实际测试 89.99%、90%、缺失报告、未加载模块和分支不足，要求整体、C++、Python 和逐受影响模块 line/branch 均至少 90%。
- [x] 9.10 在锁定开发容器全新目录运行单元覆盖率、四语言离线 truth、实际 libstdc++/libc++ profile、P1–A3/P4 回归、cold/warm、预算、性能与内存验收。

## 10. 文档、证据与最终交付

- [x] 10.1 编写 `doc/CPP_RAII_SYNCHRONIZATION.md`，说明架构、协议、CLI、profile 支持矩阵、mutex/owner 状态机、证明链、退出码和明确非目标。
- [x] 10.2 编写 `doc/CPP_RAII_SYNCHRONIZATION_VALIDATION.md`，记录实际容器命令、工具/标准库 fingerprint、测试数、四语言分母、truth、性能、缓存和 line/branch hit/total。
- [x] 10.3 生成机器可读 acceptance JSON，包含依赖 hash、profile/model、required gate、模块覆盖率、truth、cold/warm、预算、排除项和报告位置。
- [x] 10.4 更新项目 README、`doc/README.md`、`doc/IMPLEMENTATION_ROADMAP.md` 与 OpenSpec context，标明 A4 实际状态及 A5/A6/B1/B2 后续边界，不提前宣称完成。
- [x] 10.5 增加文档链接、支持矩阵、协议/schema、双语字段、退出码与“受限模型不是安全证明”措辞的自动化测试。
- [x] 10.6 审核第三方、生成物和纯 fixture 的覆盖率排除理由，确认项目自有业务、错误处理、adapter 和质量逻辑未因难测被排除。
- [x] 10.7 在全新报告目录执行最终统一质量入口与独立集成；任一测试、truth、profile 或整体/语言/模块 90% 门槛失败时保持任务未完成。
- [x] 10.8 执行 `openspec validate --all --strict`、schema/协议校验和 `git diff --check`，确认 change 仅修改本项目且没有远程运行或生产 Dockerfile 依赖。
- [x] 10.9 复核 proposal/design/spec/tasks 一致性、全部任务状态和 evidence provenance；只有 required gate 全部通过后才允许提示 sync/archive。
