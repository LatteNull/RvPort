## ADDED Requirements

### Requirement: 参数作用证明必须按编译使用实例保留多来源与顺序依据
Build Frontend/Normalizer/Analyzer SHALL 使用入口、target、TU、configuration 和 command/use occurrence 标识编译使用实例。参数 SHALL 保留 `-D/-U` 操作、值、真实使用点、来源 Evidence 集合和已证明的顺序；分散 token MUST NOT 合成虚假连续 span。参数赋值或规则存在本身 MUST NOT 证明目标必需或项目已执行构建。

#### Scenario: 参数标记与宏名位于不同赋值
- **WHEN** 两个已知变量分别提供 `-D` 和 `USE_AVX2=1`，同一明确 recipe 按顺序使用它们
- **THEN** Analyzer SHALL 用两个真实来源及使用点证明该参数，而不是因跨行丢弃所有来源或伪造 span
- **AND** 只有实际归属该编译使用实例的条件宏 SHALL 获得作用关系

#### Scenario: 同一源文件被两个目标编译
- **WHEN** 两个目标对相同源码分别使用 `-DUSE_AVX2=1` 和 `-UUSE_AVX2`
- **THEN** scanner SHALL 产生分开的作用实例和条件结果，不合并宏环境
- **AND** x86 compdb 的 observed 参数 MUST NOT 自动作为 RISC-V 静态选择证明

#### Scenario: 参数顺序无法证明
- **WHEN** 多个来源定义同一宏但输入不能确认实际覆盖顺序
- **THEN** scanner SHALL 保留全部来源及 unknown/conflicting 原因
- **AND** MUST NOT 用输出排序、文件行号或遍历顺序代替生效顺序

### Requirement: Make 参数桥接必须支持有界 include 条件赋值和明确自动变量
Make 参数桥接 SHALL 在既有安全边界内支持单字面本地 include、受支持 ifeq/ifneq/ifdef/ifndef/else/endif、简单变量引用以及 `=`/`:=`/`+=`/`?=` 的展开时机，并对可行分支分别求值后合流。明确单 target 规则中的 `$@` 和 `$<` SHALL 仅在 target、首个普通 prerequisite 及单 C/C++ 编译源码可确定时绑定；MUST NOT 执行 Make、shell、编译器或项目脚本。

#### Scenario: include 与目标架构条件提供编译参数
- **WHEN** 本地 include 定义参数变量，已支持目标架构条件选择其值，明确 recipe 通过 `$<` 编译源文件并以 `$@` 指定目标
- **THEN** scanner SHALL 保留 include、赋值、条件、引用、recipe 和源码的连续作用证明
- **AND** 正确 uname 结果 SHALL 按目标架构处理，不建模交叉编译误选

#### Scenario: 递归和立即变量展开不同
- **WHEN** `A = $(B)` 与 `C := $(B)` 之后 B 被重新赋值
- **THEN** 参数桥接 SHALL 按各自展开时机恢复值和来源，不统一替换为最后的 B
- **AND** 未知环境覆盖或未定义外部输入 SHALL 保持 unknown

#### Scenario: 未知条件合流
- **WHEN** 未知 Make 条件的可行分支对同一参数提供不同值
- **THEN** 合流 SHALL 保留冲突，不把两个分支顺序执行成确定结果
- **AND** 值与操作等价的所有可行分支 SHALL 能合流，同时保留各分支来源

#### Scenario: 动态和越界构造
- **WHEN** 遇到 eval、普通 shell、动态 include、模式/隐式规则、target-specific 继承、未知 `$^` 或根外路径
- **THEN** 相应参数作用 SHALL 保持 unknown 并给出稳定原因，原始 x86 事实 SHALL 保留
- **AND** 无法界定副作用范围时 SHALL 保守失效该环境，确定 inactive 的分支不得污染可达状态

### Requirement: 宏构建作用扩展必须通过隔离覆盖和规模验收
新增及实质修改的 frontend、normalizer、作用环境、图接线、consumer 和 projection 模块 SHALL 登记隔离单元测试，独立容器内项目整体及受影响模块 SHALL 达到至少 90% 行/90% 分支，统计包含未加载自有源码。新增/修改测试驱动逻辑 SHALL 另有隔离覆盖；组件、端到端或真实项目扫描 MUST NOT 代替单元覆盖。

#### Scenario: 完整验收
- **WHEN** apply 验证本轮能力
- **THEN** SHALL 分别报告单元命令/范围/排除项/覆盖/报告路径、人工 oracle、完整回归和真实项目差异
- **AND** GCC/Clang facts 哈希、默认 V2/显式 V1、三个工件及不执行项目命令边界 SHALL 不变

#### Scenario: 新功能带来额外成本
- **WHEN** 同镜像下运行固定 libarchive 822 文件、1万/2万稀疏/密集及宏/TU 规模样例
- **THEN** SHALL 在 2 CPU/2 GiB/无 swap、每扫描 300 秒以内且无 OOM 的条件下验收，保留分阶段时间、内存、查询计数、截断及工件体积
- **AND** 新功能相对成本 SHALL 作为诊断，不恢复旧相对耗时否决规则，不关闭既有能力或自动降低硬门槛
