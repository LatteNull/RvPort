## 1. 协议、身份与引用基础

- [x] 1.1 定义 `BoundedObjectProvenanceRequest v1`、`SourceObjectPathFacts v1`、`LLVMObjectProvenanceFacts v1`、`BoundedObjectProvenanceGraph v1` 和 `BoundedObjectProvenanceReport v1` schema，包含依赖 digest、模式、状态、预算、完整性、双语诊断和确定排序规则
- [x] 1.2 实现并单元测试 schema/引用验证、canonical identity/digest、协议版本拒绝、陈旧/悬空依赖和 P1–P4/A1–A4 不变回归
- [x] 1.3 实现并单元测试独立的 StorageInstance、SubobjectPath、ObjectInstance、byte range、union overlap group 和 invocation/lifetime identity，禁止 FieldDecl 单独成为运行时实例
- [x] 1.4 将 A5 schema、worker、Python 模块、CLI 和全部自有执行源码纳入构建、安装、静态/schema 检查及完整覆盖率源码枚举

## 2. AST 源对象路径事实

- [x] 2.1 扩展 Clang 21.1.8 worker，独立生成 `SourceObjectPathFacts`，提取 MemberExpr base、`.`/`->`、CXXThisExpr、地址/解引用、cast、conditional、参数、返回和调用路径
- [x] 2.2 使用 canonical declaration/type 与 ASTRecordLayout 记录 struct/class 字段序号、offset/size/alignment、常量数组下标、宏 spelling/expansion 和 C union overlap group
- [x] 2.3 对不完整类型、柔性数组、位域、匿名 record、union、复杂继承、宏和布局缺口实现明确 candidate/frontier，确保 AST-only 不发布 runtime alias/noalias 或消费者证明
- [x] 2.4 为 C11/C17 与 C++17/C++20 分别补充 AST 正常、嵌套、union、`this`、同 FieldDecl 不同 base、宏、错误恢复和预算单元测试

## 3. LLVM 局部 provenance 事实

- [x] 3.1 在只读 LLVM worker 中接入 DataLayout、ValueTracking、DominatorTree/LoopInfo、BasicAA/AAResults、MemorySSA 和 CaptureTracking，生成独立 `LLVMObjectProvenanceFacts`
- [x] 3.2 实现并登记 `getUnderlyingObject(s)`、constant base/offset、supported cast/GEP、returned-argument、AA MemoryLocation、clobber/dominance 和 capture 查询的输入、结果、分析节点与预算证据
- [x] 3.3 实现 constant GEP/byte range/address-space 规范化以及有限 dynamic index 边界；addrspacecast、ptr-int、overflow、unknown origin 和非兼容布局保守进入 unknown
- [x] 3.4 为 global、alloca、parameter/receiver、phi/select、多层 cast/GEP、AA 四类结果、MemoryPhi、capture 和 API/预算失败补充 C++ worker 单元测试

## 4. 有限候选与局部 pointer-field 传播

- [x] 4.1 实现并单元测试 bottom、must singleton、有限 may candidates 和 reasoned unknown lattice，保留 candidate guard、proof、opposed evidence 和依赖切片
- [x] 4.2 实现 phi/select guard 合并、同一规范对象折叠、循环固定点和候选/path/guard/work 预算，超限不得截断为假 complete
- [x] 4.3 实现私有栈槽和对象 pointer field 的 store/load 传播，仅在 exact range、唯一支配 store、无相关 clobber、未逃逸和 lifetime 有效时强更新
- [x] 4.4 为唯一 store、MemoryPhi、多 store、MayAlias/部分覆盖、unknown call、volatile/atomic pointer load、lifetime end、共享字段和 load-hop 超限补充单元测试

## 5. AST/IR 对齐与跨 TU 直接调用组合

- [x] 5.1 实现 source path 到 LLVM base/offset/range 的 cardinality-aware 对齐，校验 physical TU、profile、target、ABI、DataLayout、实体和表达式绑定并登记反对证据
- [x] 5.2 复用 A1 精确 function definition 与 P2 adopted direct-call/invocation，实现 C/C++ actual-to-formal、返回值和 C++ receiver/`this` 候选替换
- [x] 5.3 实现 direct call SCC/递归单调合并、context 预算和 expired local return；对间接/虚调用、unsupported ABI、heap return、scope 外与 weak/COMDAT 冲突保守降级
- [x] 5.4 为 C struct/union 嵌套参数/返回、C++ this/对象/mutex 字段、单/跨 TU、同名 static、无 debug、ABI/profile 冲突和递归预算补充组合层单元测试

## 6. 模式、完整性与消费者适配

- [x] 6.1 实现按 TU 的 AST+IR、IR-only、AST-only、failed 模式和失败分类，并按候选依赖切片聚合 scope 完整性、计划/完成分母及零候选原因
- [x] 6.2 实现 A4 exact-only object/mutex adapter，验证不同 storage 实例的同 FieldDecl 不合并、同一实例经直接 wrapper 保持 identity，may/unknown 继续为 `mutex-provenance-ambiguous`
- [x] 6.3 实现 P4 exact-only object adapter，保持 reads-from、SW/HB、risk/discharged、严重度、退出码和 `safety=not_established` 既有语义不变
- [x] 6.4 为无关/相关失败 TU、AST-only/IR-only、完整空候选、失败导致零候选、adapter 缺失和旧协议无 A5 请求路径补充单元与黄金回归

## 7. 预算、缓存、CLI 与报告

- [x] 7.1 实现 TU、节点、path/depth、value/candidate/guard、load hop、AA/MemorySSA/capture、call context、递归、关系、输出和时间预算及 hit/limit/frontier 传播
- [x] 7.2 实现内容寻址缓存键、依赖闭包重验、损坏/陈旧/failed/timeout 拒绝和 cold/warm semantic digest 一致性，并补充正常、边界和异常单元测试
- [x] 7.3 实现 A5 CLI 的显式 request/store/output、确定排序和 `0/2/1` 退出码，禁止使用风险码 `3`，并补充参数、引用、部分、失败和输出确定性单元测试
- [x] 7.4 实现 graph/report 完整性分母、证据链和中英双语 detail/limitation/suggestion，验证机器 identity 不受翻译影响且零 finding 不表述为安全证明

## 8. 四语言 fixture 与语义 truth

- [x] 8.1 建立独立 C11/C17 fixture 和人工 truth，覆盖 struct/union、嵌套/指针字段、多级指针、参数/返回、单/跨 TU wrapper、phi/select/cast/GEP、clobber 和降级模式
- [x] 8.2 建立独立 C++17/C++20 fixture 和人工 truth，覆盖 this、对象/指针/mutex 字段、两个实例同 FieldDecl、直接成员/自由 wrapper、参数/返回、单/跨 TU 和无 debug
- [x] 8.3 增加 AST+IR、IR-only、AST-only、failed、开放 scope、profile/ABI 失配、预算、cache corruption、CLI 退出码和双语诊断集成断言，保持 C 路径不依赖 C++ 模型
- [x] 8.4 运行并记录四语言 planned/completed/TP/FP/FN/abstention、模式完整性与 A4/P4 adapter truth，不以编译成功、AA 成功或零 finding 作为 oracle

## 9. 单元覆盖率与最终验收

- [x] 9.1 在锁定开发容器和全新输出目录运行全部 C++/Python 单元测试，确保正常、边界、异常、unknown/partial 分支均有有效断言且集成覆盖不计入单元分母
- [x] 9.2 运行覆盖率门禁并记录 hit/total、源码清单和排除理由，确认项目整体、C++、Python及每个受影响自有模块行覆盖率和分支覆盖率均至少 90%，含未加载源码和可执行头文件
- [x] 9.3 运行 OpenSpec/schema、P1–P4/A1–A4 黄金回归、四语言 provenance truth、cold/warm、性能/内存/预算、缓存和确定性门禁，任一失败时保持任务未完成
- [x] 9.4 编写 `doc/BOUNDED_OBJECT_PROVENANCE.md`、validation 文档和机器可读 acceptance JSON，记录环境、命令、版本/hash、测试数、覆盖率、truth、性能、缓存、限制和报告位置
- [x] 9.5 更新 `doc/IMPLEMENTATION_ROADMAP.md` 的 A5 实际状态与证据链接，执行文档链接/格式/证据来源一致性检查；仅在全部 required gate 通过后标记 change 实现完成并提示同步/归档
