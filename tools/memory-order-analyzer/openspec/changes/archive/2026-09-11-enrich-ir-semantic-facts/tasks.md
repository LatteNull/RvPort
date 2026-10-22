## 1. 契约、版本与验收骨架

- [x] 1.1 在本项目核对 P1 边界、现有源码/构建/覆盖清单及锁定镜像；记录实施前基线，保留用户其他改动、旧缓存和历史证据。
- [x] 1.2 定义 ModuleFacts v2 的值、类型、条件边、调用、范围、初始化及 extraction 字段；添加有效/无效 JSON 单元夹具，明确 unknown/not_applicable/void/declaration 语义。
- [x] 1.3 将 contracts 改为按 kind 校验（ModuleFacts=2、RunReport=2），增加旧 facts/report 及未来版本拒绝、其他 v1 契约继续可读的单元测试；旧报告不补造提取状态。
- [x] 1.4 建立单一 extractor/protocol/policy 元数据来源和 C++/Python 一致性检查，固定 0.2.0、v2 与预算；补充元数据不一致/缺失单元测试。
- [x] 1.5 创建 doc/SEMANTIC_FACTS_ACCEPTANCE.md，将所有增量 requirement/scenario 映射到计划测试及断言目标，保留现有质量规范的完整验收要求。

## 2. 值节点与操作数关系

- [x] 2.1 实现两遍身份登记、模块局部值表和所需根闭包，处理参数/指令/常量/返回、循环引用与类型身份；单元测试重复提取、同名实体及循环 phi。
- [x] 2.2 实现精确整数位宽/位模式、null/undef/poison/freeze 和 unsupported 节点；单元测试超过 64 位常量、类型差异及未知不填零。
- [x] 2.3 实现 phi/select/cast/icmp/GEP/整数运算和相关 flags 的原始关系，以及 aggregate extract/insert；逐类单元测试前驱、操作数顺序、signed/unsigned 解释和 CAS 结果使用。
- [x] 2.4 实现全局整数/零/指针/有界聚合初始化及声明无初值的区分；单元测试递归/深层类型与不支持初始化形式，不推断动态初始化已执行。
- [x] 2.5 为新 JSON 字段和节点补充 Module 释放后序列化的生命周期回归，确保字符串拥有存储且相同输入确定性输出。

## 3. 控制流和调用接口

- [x] 3.1 在保留旧 successors 的基础上实现条件 br、switch case/default 和后继序号；单元测试同目标不同 case、精确 case 值、ret/void/unreachable。
- [x] 3.2 实现函数参数/返回接口、call/invoke 目标值、有序实参、结果/void、类型/调用约定与 normal/unwind；单元测试直接/间接、vararg、返回链和异常后继。
- [x] 3.3 为 ABI 属性、tail、operand bundles 和未支持 terminator 定义结构输出或显式 unknown；单元测试这些信息不能静默消失，不新增调用点/路径求解。

## 4. 内存操作数与 DataLayout 范围

- [x] 4.1 实现存储字节数、对齐和地址空间的 tagged 范围；单元测试带 padding 的类型、固定/可伸缩大小、缺布局、fence not_applicable。
- [x] 4.2 实现常量 GEP 精确偏移与原始索引/类型/flags，保留动态 GEP、addrspacecast/inttoptr 边界；单元测试负偏移、宽偏移、未知地址及不误报同对象。
- [x] 4.3 补齐 load/store/RMW/CAS 的值与结果引用，保留全部既有原子属性；单元测试 compare/new/旧值/成功位及结果控制分支。
- [x] 4.4 补齐 memcpy/memmove 的源/目的范围与长度、memset 填充值；单元测试独立地址空间/对齐、零长度和动态未知长度。

## 5. 预算与事实消费校验

- [x] 5.1 实现值节点/操作数引用/深度/输出预算和 visited 防循环，支持测试注入小预算；单元测试边界、depth partial 和总预算失败不发布残缺 facts。
- [x] 5.2 实现 extraction 状态、根/节点/unknown 计数及按 ID 定位的诊断；单元测试 unknown、无所需根、无 debug 和支持范围内 complete 的区别。
- [x] 5.3 实现独立引用校验并接入 worker 输出及磁盘 index/link 消费；单元测试重复/悬空/跨函数引用、phi/CFG 不一致与合法 unknown 引用。
- [x] 5.4 贯通 extraction_budget_exceeded、协议错误及原 timed_out/parse/verify 错误分类；单元测试部分 TU 保留、全失败和输出上限，防止将截断 JSON 当成功结果。

## 6. 协议、产物迁移与完整性报告

- [x] 6.1 增加 worker 机器协议查询并保留 --version，doctor/读取入口验证 LLVM、facts/extractor/policy；补充旧 worker、同 LLVM 不同协议和缺字段单元测试。
- [x] 6.2 统一 collect/cache 的提取身份，更新键与元数据；单元测试旧代 miss、新代命中、policy 变化、配置/profile 隔离及依赖重发现不退化。
- [x] 6.3 实现无 manifest 和有旧/当前 manifest 的 import 重提取身份策略，保留 provenance/context/profile/inputs/lineage；单元测试 hash 错误、重复导入幂等和旧文件不覆盖。
- [x] 6.4 更新 index/link 的版本与身份检查、linked v2 重读取和祖先集合；单元测试混代拒绝、新旧重键祖先重叠、重复强定义及显式 scope 不被自动替换。
- [x] 6.5 在报告中提供重键来源映射和 scope 更新依据；单元测试 unknown 来源不升级、无来源不猜映射以及 manifest 来源保持。
- [x] 6.6 增加 RunReport v2 必填 fact_extraction 汇总并保持原字段语义；单元测试新旧版本边界、0/2/1、全计划分母、零分母、doctor not_run、语义分析/安全/findings 固定值及能力开关。

## 7. 独立集成与全量质量门槛

- [x] 7.1 增加 GCC/Clang × C11/C17/C++17/C++20 compile-only 集成，核对 v2 引用和范围；补充多物理 TU 调用接口、无 debug 和 profile 隔离，不运行被分析程序。
- [x] 7.2 用当前锁定标准库构建 O0 atomic 包装集成样例，断言实参/形参/局部存储/条件/原始事件关系可追踪，且没有声称求出唯一 order 或完成调用点特化。
- [x] 7.3 加入真实 BC 的旧 manifest 重提取、v1 facts 拒绝、显式 scope 重建与 linked 回归，断言迁移/祖先与完整性行为符合设计，不以 DevKit 报告作语义真值。
- [x] 7.4 将所有新增/拆分自有源纳入构建和覆盖统计；同步补强对子目录、未调用/未加载文件及可执行头文件的枚举，添加漏统计/缺报告的门槛单元测试，记录合理排除项。
- [x] 7.5 在锁定独立容器内以新的输出目录实际运行全部 C++/Python 单元测试及覆盖率入口，确保整体、各语言、逐模块行和可用分支均至少 90%；不足则补测，集成 profile 不混入。
- [x] 7.6 单独运行全部集成/文档回归并记录有界样例资源数据、命令、镜像身份及报告位置；测试或验证受阻时保留任务未完成，不宣称质量达标。

## 8. 文档与交付检查

- [x] 8.1 编写 doc/SEMANTIC_FACTS.md 的 v2 契约、支持/未知边界、预算、迁移和现有 CLI 用法；更新项目 README、doc/README、路线与 OpenSpec 当前规划状态，不改历史归档或主规格。
- [x] 8.2 完成 doc/SEMANTIC_FACTS_ACCEPTANCE.md 的具名测试映射，并在 doc/SEMANTIC_FACTS_VALIDATION.md 写入本轮实际行/分支计数、逐模块结果、统计范围、排除理由和报告位置；历史覆盖率不得冒充新结果。
- [x] 8.3 执行文档本地链接、内容一致性和原始证据 hash 回归，以及 openspec validate enrich-ir-semantic-facts --strict；确认没有扩展到线程/风险引擎、生产 Dockerfile 或归档 checker。
- [x] 8.4 仅在全部实现及验证任务通过后汇总 apply 结果，并提供本项目实际 sync/archive 阶段的可复制命令；无用户授权不自动同步或归档。
