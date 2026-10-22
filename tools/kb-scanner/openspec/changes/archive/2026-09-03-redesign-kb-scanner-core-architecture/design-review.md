# KB Scanner 总体设计评审记录

## 1. 评审结论

本 change 的总体设计已接受，定位为 C/C++ x86→RISC-V 静态迁移分析器。它不实现真实编译或测试，不承担操作系统迁移，也不以新增规则数量作为重写目标。重写重点是让现有局部检测能力能够参与跨文件关系推理和项目级静态评估。

## 2. 能力范围

| 范围 | 结论 | 处理方式 |
|---|---|---|
| C/C++ 源码、预处理器和头文件 | 纳入 | 识别架构依赖、条件分支、宏、调用、类型和替代实现 |
| 汇编源文件与内联汇编 | 纳入 | 保留当前检测深度，并参与目标可达性分类 |
| Makefile、Autoconf、RPM、compile_commands | 纳入 | 仅做静态配置、选择关系和已知编译上下文分析 |
| 测试源码与静态测试选择 | 纳入 | 识别测试角色、守卫、选择关系和覆盖缺口 |
| 真实 RISC-V 编译与测试执行 | 后续阶段 | 不作为 KB Scanner 输入或结论；由 RvPort 后续节点负责 |
| 操作系统、内核、系统调用、驱动、开发板 | 排除 | 不计入 KB Scanner 静态迁移就绪度 |
| RVWMO 并发语义 | 外部能力 | 由 memory-model IR checker 分析，KB Scanner 不重复实现 |

## 3. 必须保留的现有资产

### 3.1 编译器派生事实数据

| 数据文件 | headers | intrinsics | builtins | vectorTypes | platformMacros | compilerFlags |
|---|---:|---:|---:|---:|---:|---:|
| clang-x86-entries.json | 125 | 7,563 | 1,993 | 10 | 5 | 216 |
| gcc-x86-entries.json | 120 | 7,602 | 3,438 | 10 | 47 | 225 |

两份文件均保留 `source`、`headers`、`intrinsics`、`builtins`、`vectorTypes`、`platformMacros`、`compilerFlags` 结构。运行时允许按类别合并去重，但不得删除任一来源，不得破坏现有 `generatedSet` 引用。

### 3.2 检测能力基线

- 当前规则文件：24 个 YAML。
- 当前自动化基线：41 个测试全部通过。
- 必须保持：x86 header、intrinsic、builtin、SIMD 类型、平台宏、编译参数、汇编、寄存器、CPU API、固定向量宽度、架构对齐、现代 C/C++ 分发模式、构建脚本线索、RPM 约束、compile_commands 增强和替代实现降噪。
- 现有 `guarded`、`inactive`、`portability_gap`、comment hint、reference source/reference 语义不得无证据退化。

## 4. 分层职责评审

| 阶段 | 负责 | 不负责 |
|---|---|---|
| Workspace Intake | 文件发现、排除边界、文件角色、规则包与上下文入口 | 不判断迁移风险 |
| Frontends / Knowledge Providers | 将 C/C++、asm、构建、RPM、测试和生成事实数据规范化 | 不决定 severity 或 blocking |
| Fact / Evidence | 表达扫描器直接看见的内容、位置、来源和解析完整度 | 不表达跨文件结论 |
| Relation | 连接宏、条件、文件、构建变量、源码集合、测试和替代实现 | 不直接生成最终报告 |
| Observation / Detector | 描述规则或知识数据命中的候选现象 | 不在缺少上下文时宣称 blocker |
| Classification / Finding | 结合目标 RISC-V、可达性和策略形成局部结论 | 不代替项目整体评估 |
| Assessment | 汇总静态迁移状态、维度、阻断项、缺口和未知项 | 不宣称真实编译或测试成功 |
| Compatible Report Projection | 投影到现有 scan-result.json、HTML 和 log | 不创建新的主结果结构 |

## 5. 核心术语和生命周期

| 术语 | 大白话定义 | 生命周期约束 |
|---|---|---|
| Fact | 扫描器直接读到的事实 | 由前端产生，不含最终风险判断 |
| Evidence | Fact 的出处和可信程度 | 必须可追溯到文件、位置、解析器或知识来源 |
| Relation | 多个事实之间的连接 | 必须记录关系类型、端点和推导证据 |
| Observation | 检测器发现的候选现象 | 可以是确定匹配，也可以是待上下文确认的候选 |
| Finding | 一个需要展示的局部迁移结论 | 必须说明 actionability、blocking、reachability 和证据链 |
| Assessment | 整个项目的静态迁移判断 | 必须同时展示状态、维度、缺口和 unknown |

禁止混用：Fact 不得直接承载 severity；Observation 不等于 Finding；Finding 不得因抑制而删除原始 Evidence；Assessment 不得仅根据“没有 Finding”推导 ready。

生命周期固定为：

```text
输入 → Fact/Evidence → Relation → Observation → Finding → Assessment → 兼容输出投影
```

## 6. 架构知识 ontology

| 维度 | 最小集合 | 用途 |
|---|---|---|
| family | x86、riscv、arm、generic、unknown | 判断架构分支和实现归属 |
| alias | x86_64、amd64、i386、riscv64 等 | 将不同写法归一到 family |
| feature | SSE、AVX、AVX2、AVX512、AESNI、RVV 等 | 区分架构特性而非只看 family |
| implementation role | architecture-specific、portable、fallback、unknown | 判断替代路径和降噪 |

注释中的架构词最多产生非阻断 hint。`ENABLE_X86_FAST_PATH`、`X86_AESNI` 等代码标识符先产生 candidate Observation，只有结合守卫、选择、调用或类型使用证据后才升级为 Finding。

## 7. 静态构建选择模型

统一关系集合至少包括 `declares`、`assigns`、`derives-from`、`guards`、`expands-to`、`selects` 和 `includes`。目标是静态回答“目标为 RISC-V 时，哪些源码、参数、依赖和目录会被选择”。

`uname -m` 是必要的 selector 事实，但不是风险，并采用以下确定假设：

| 静态结构 | RISC-V 推导 | 结论 |
|---|---|---|
| 有 RISC-V 分支 | 选择 RISC-V 分支 | 分析其内容，不报告 uname |
| 无 RISC-V 分支，有 generic/portable/fallback | x86 分支 inactive，进入通用路径 | 验证通用路径是否足够 |
| 只有 x86 分支 | x86 分支 inactive，RISC-V 无可选路径 | 报告缺少 RISC-V 选择路径 |

任何情况下都不得描述为“RISC-V 因 uname 错误进入 x86 分支”。其他无法静态求值的动态表达式必须保持 unknown/partial。

## 8. 架构感知测试模型

测试分析只使用源码、构建目标、测试框架注册、命名和条件守卫等静态证据：

| 结果 | 证据门槛 | 阻断性 |
|---|---|---|
| x86_test_guarded | 确认 x86 测试不会进入 RISC-V 静态测试配置 | 非阻断 |
| riscv_test_blocker | 含 x86 依赖的测试静态可达于 RISC-V，且无兼容替代 | 阻断或高优先级 |
| riscv_test_coverage_gap | x86 实现有可确认测试，RISC-V 对应实现无覆盖证据 | 缺口；关系不确定时必须为 unknown |

本层不判断真实测试通过、失败或跳过。

## 9. 项目级静态 readiness

状态集合接受为：`architecture_independent`、`x86_only`、`multiarch_without_riscv`、`partial_riscv`、`riscv_ready`、`unknown`。

评估维度接受为：sourceReachability、buildSelection、architectureDependencies、alternativeImplementations、testCoverage、inputCompleteness。`riscv_ready` 只表示当前静态输入覆盖内未发现阻断项，不等价于真实 RISC-V 编译或测试成功。关键上下文缺失时必须输出 unknown，不能因为零 Finding 自动输出 ready。

## 10. Memory model 边界

KB Scanner 不分析线程同步、release/acquire 或 RVWMO 正确性。未来只能把 memory-model IR checker 结果作为独立外部维度关联；未提供或失败时状态为 unknown/not-run，不得解释为没有问题。
