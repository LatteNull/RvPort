## 1. 协议、证据审计与契约

- [x] 1.1 审计 P1/A1/P2/P3/A3 现有产物能否无损提供 source/IR 创建调用、callback、ABI/profile、handle/success 与 adopted-call 证据，形成字段来源表；若 required 字段缺失，仅设计并实现 R1 独立补充事实 kind，不修改旧协议
- [x] 1.2 新增 R1 协议清单和严格 JSON Schema，覆盖 `ExecutionRootDiscoveryRequest`、`ThreadCreationSiteIndex`、`ExecutionRootIndex`、`RootDrivenAnalysisPlan`、`RootDrivenAnalysisReport`、预算、引用、双语诊断和确定排序
- [x] 1.3 实现 Python 契约、canonical identity/digest、跨 kind 引用和悬空/未来版本/重复 ID/计数校验，为正常与损坏输入补充单元测试
- [x] 1.4 将新协议接入构建/质量源码枚举；若 1.1 需要 worker 补充事实，加入协议协商、批处理、输出限制和对应 C++ 正反单元测试

## 2. AST 与 BC 线程创建候选

- [x] 2.1 实现 A1 source facts 到 pthread source candidate 的适配，保留物理 TU、profile、callsite、callback entity、参数、宏范围、支持/反对证据及失败分类
- [x] 2.2 实现 P3 LLVM local facts 到 pthread IR candidate 的适配，保留 call/ref、callback SSA candidates、ABI/linkage、handle、success guard、callback metadata 与 no-debug 状态
- [x] 2.3 实现 A3 source/IR/lifecycle/profile 到 `std::thread` candidate 的适配，严格验证 vendor/version/ABI/target/wrapper digest，不进行名称相似匹配
- [x] 2.4 实现 AST 与 IR 候选并集、稳定 callsite/SourceIRBinding 对齐、去重和 opposed evidence，分类 `dual-exact`、`ir-exact`、`source-candidate`、`ambiguous`、`unsupported`、`failed`
- [x] 2.5 为单侧候选、直接 pthread、callback 冲突、多候选、profile 漂移、优化/no-debug、损坏引用和零候选补充候选发现与分类单元测试

## 3. ExecutionRoot 索引

- [x] 3.1 实现显式 program/exported/framework root seed 的实体、scope、profile 和 external-parent 校验，不从名称、目录或全部 external symbols自动扩展
- [x] 3.2 实现请求显式启用的唯一 `main` 发现，拒绝开放 scope、定义歧义、ABI/profile 冲突和仅声明输入
- [x] 3.3 将 exact pthread 与已验证 A3 `std::thread` 创建点转换为正式 root，将其他分类转换为候选/frontier；分离可复用 context 与 callsite/创建实例身份
- [x] 3.4 保持 C11/C17 C linkage/pthread 路径不依赖 C++ AST或标准库 profile，并明确拒绝 Windows、MSVC、clang-cl 和不支持语言 profile
- [x] 3.5 为显式根、唯一/重复 main、无 main 库、多 exported roots、同 callback 多 callsites、AST-only 和 unsupported framework root 补充索引单元测试

## 4. Root 驱动可达规划

- [x] 4.1 实现 scope 内轻量全局视图，记录全部 members/TUs/profiles/失败与 demanded/observed-but-not-demanded 基础事实，不宣称 P1 已懒提取
- [x] 4.2 实现从正式 roots 沿 P1/A1 唯一直接绑定、P2 adopted direct calls、版本化 wrapper 和 exact spawn edge 的确定固定点扩展
- [x] 4.3 实现 function/context/TU/call-edge demand、抽象参数、root lineage 和调用/创建来源身份，保持同函数不同 roots/callsites/instances 隔离
- [x] 4.4 实现间接/虚调用、开放边界、歧义 definition/wrapper、递归 SCC、重复创建和 path/context/root 预算的保守合并及非空 frontier
- [x] 4.5 为跨 TU wrapper、嵌套线程创建、递归/循环、间接调用、scope 外定义、预算边界和无关失败 TU 补充 planner 单元测试

## 5. P2/P3/A3 统一编排与完整性

- [x] 5.1 从正式 roots 生成 P2 `mode=roots` 请求和 P3 roots 请求，验证绝不回退 `all-defined`，并按 plan identity 引用或运行独立子输出
- [x] 5.2 将 A3 exact callable 作为效果 root并引用生命周期 overlay，保持其不被伪装为 P3 原生 pthread create
- [x] 5.3 对账 R1 计划与 P2/P3/A3 实际 roots、callbacks、contexts、instances 和 digest，去重一致证据并为集合差异生成 `plan-observation-mismatch`
- [x] 5.4 实现按 root 依赖切片传播的 creation/root/reachability/downstream completeness，使无关失败可局部隔离而相关 AST-only/failed/budget 必须降级
- [x] 5.5 为 P2/P3 子运行失败、计划扩大/缩小、旧缓存替换、候选相关与无关缺口、零分母和完整零创建点补充编排单元测试

## 6. 缓存、CLI 与报告

- [x] 6.1 实现 `execution-root-driven-analysis-v1` 分层缓存，key 覆盖 schema/实现、LLVM/Clang、scope/profile、全部依赖、root seeds、model/wrapper、预算和内容摘要
- [x] 6.2 实现损坏、陈旧、failed、timeout、wall-clock partial 和 dependency/profile 漂移拒绝逻辑，验证 cold/warm semantic digest 一致且命中计数不参与语义摘要
- [x] 6.3 实现 `plan-execution-roots` CLI、全新输出目录保护、请求快照、创建点/root 索引、计划、P2/P3 子输出引用及确定排序报告
- [x] 6.4 实现 creation/root/reachability/downstream 分母、frontier、root coverage、reachable coverage、`safety=not_evaluated`、`findings=null` 和 0/2/1 退出码
- [x] 6.5 为所有用户可见 detail/limitation/suggestion 提供中文和英文字段，并为参数错误、输出已存在、全部不可用、partial 与 complete CLI 路径补充单元测试

## 7. 四语言离线语义验证

- [x] 7.1 增加独立 C11/C17 fixture 与 truth，覆盖显式/main roots、直接 pthread、跨 TU C wrapper、IR-only/no-debug、AST-only、callback 冲突和开放 scope，且不依赖 C++ profile
- [x] 7.2 增加独立 C++17/C++20 fixture 与 truth，覆盖 pthread、自由函数、lambda、成员函数、functor、跨 TU wrapper、已验证 libstdc++/libc++ `std::thread` 和 profile mismatch
- [x] 7.3 增加库 exported/framework 显式 roots、同 callback 多 callsites、嵌套创建、间接调用、递归/循环、预算、损坏缓存和 plan-observation mismatch 集成场景
- [x] 7.4 实现四语言 validation suite/truth/report，分别记录 planned/completed、source/IR/aligned、各分类、formal/candidate roots、reachable coverage 和 frontier，不合并掩盖单语言缺口
- [x] 7.5 运行并固定 P1–P4/A1–A5 golden 回归，证明没有 R1 请求时旧 CLI、schema、缓存、finding/discharged、退出码和报告语义不变

## 8. 文档与路线图

- [x] 8.1 编写 `doc/EXECUTION_ROOT_DRIVEN_ANALYSIS.md`，说明全局轻量索引、AST/BC 候选并集、exact 采用、ExecutionRoot、可达计划、CLI、缓存、完整性和非安全边界
- [x] 8.2 更新项目 README 和 CLI 文档，给出从 collect/scope/source evidence 到 R1 计划的推荐流程，并明确旧 P4 路径仍兼容、R1 不执行风险评价
- [x] 8.3 更新 `doc/IMPLEMENTATION_ROADMAP.md`，修正 A5 已于 2026-09-22 同步归档，新增 R1 当前 change、R2 `ConcurrentAccessCandidateGraph` 和 R3 按函数懒提取，保持 A6 fence/RMW 与 B1/B2 为独立 change
- [x] 8.4 编写 R1 validation 文档和机器可读 acceptance JSON，校验文档链接、协议/命令/字段一致性及证据来源，不把 BC 成功、exit 0、零创建点或零 finding 表述为安全

## 9. 单元覆盖率与最终验收

- [x] 9.1 在锁定开发容器和全新输出目录运行全部 C++/Python 单元测试，确认正常、边界、异常、unknown/partial 分支均有有效断言且集成覆盖不计入单元分母
- [x] 9.2 运行覆盖率门禁并记录 hit/total、完整源码清单和排除理由，确认项目整体、C++、Python及每个受影响自有模块行覆盖率和分支覆盖率均至少 90%，含未加载源码和可执行头文件
- [x] 9.3 运行严格 OpenSpec/schema、四语言 R1 truth、P1–P4/A1–A5 回归、cold/warm、性能/内存/预算、缓存、确定性和文档门禁；任一 required gate 失败时保持任务未完成
- [x] 9.4 审核 acceptance 中的精确命令、环境、LLVM/Clang/profile/version/hash、测试数、覆盖率、各语言分母、root/reachable coverage、frontier、缓存、性能和报告位置
- [x] 9.5 仅在全部 required gate 实际通过且新输出目录证据齐全后标记 change 实现完成，并提示同步主规格和归档；不得用历史 DevKit、旧覆盖率或零风险结果替代本次验收
