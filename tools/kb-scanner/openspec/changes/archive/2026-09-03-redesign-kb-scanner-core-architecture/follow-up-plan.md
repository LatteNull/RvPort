# KB Scanner 后续 Change 与技术验证计划

## 1. 拆分原则

- 每个 change 只引入一组可以独立验证的能力。
- 第一批 change 先建立内部关系分析骨架，但对外结果必须保持完全兼容。
- `clang-x86-entries.json`、`gcc-x86-entries.json` 和现有 `generatedSet` 是迁移基线，不是待清理内容。
- 新能力必须先证明不会降低现有 41 个测试和 24 个规则文件的覆盖。
- KB Scanner 只做静态分析；真实编译和测试由后续 RvPort 节点负责。
- 构建分析假设 `uname` 等已识别 selector 返回当前机器的正确架构，不实现交叉编译误选模型。

## 2. 建议的实现 Change 顺序

### 2.1 `introduce-kb-analysis-core`

**范围**

- 定义内部 Fact/Evidence、Relation、Observation、Assessment 接口和稳定引用。
- 建立 Relation/Observation 到现有 Finding `trace` 的投影。
- 建立可选 `summary.readiness` 数据对象，但本阶段可以只输出 `unknown`。
- 保持现有检测器执行路径和 Finding 结果不变。

**验收**

- 当前 41 个 scanner 测试全部通过。
- 同一 fixture 的既有 Finding 数量、rule ID、分类和阻断状态不发生非预期变化。
- `scan-result.json` 仍为 schemaVersion `1.0`，当前后端 parser 可直接导入。

### 2.2 `adapt-existing-kb-assets-to-analysis-core`

**范围**

- 将现有 C/C++、asm、RPM、compile_commands 前端接入统一分析入口。
- 增加 Knowledge Provider，直接加载现有 Clang/GCC JSON 结构。
- 保持 `generatedSet`、运行时合并和现有规则包语义。
- 为重复条目保留 Clang/GCC 来源集合。

**验收**

- 两个生成 JSON 的六类数据均可加载。
- `test_generated_clang_x86_entries_are_loaded`、`test_generated_gcc_x86_entries_are_loaded` 及全部矩阵 fixture 通过。
- 不修改或重新生成两个 JSON 文件的内容。

### 2.3 `add-static-build-selection-analysis`

**范围**

- 为 Makefile 和 Autoconf 增加最小静态变量、条件、include 和源码选择关系。
- 识别 `uname -m` 等架构 selector，并按目标 RISC-V 推导分支。
- 区分 RISC-V 专用路径、generic/portable/fallback 和缺失路径。
- 不分析交叉编译，不声称执行了真实构建。

**验收**

- 有 RISC-V 分支时分析该分支，不报告 `uname` 本身。
- 只有通用 fallback 时将 x86 分支标为 inactive，并分析 fallback。
- 没有 RISC-V 和 fallback 时产生“缺少 RISC-V 选择路径”，不得描述成进入 x86 分支。
- 无法部分求值的表达式产生 unknown/diagnostic，而不是确定结论。

### 2.4 `add-architecture-aware-test-analysis`

**范围**

- 识别 test、benchmark、example 和 production 文件/目标角色。
- 建立测试到实现/特性的静态覆盖关系和目标选择关系。
- 产生 `x86_test_guarded`、`riscv_test_blocker`、`riscv_test_coverage_gap`。
- 不消费或判断真实测试运行结果。

**验收**

- 路径名不能成为唯一测试角色证据。
- 已正确隔离的 x86 测试不成为 blocker。
- 仅在静态可达且无兼容替代时产生 blocker。
- 覆盖关系不足时输出 unknown，不直接断言 coverage gap。

### 2.5 `add-cross-file-macro-relations`

**范围**

- 建立自定义宏定义、使用、展开、token paste 和最终架构依赖之间的关系。
- 关联定义源头与使用影响，控制重复 Finding。
- 增加模糊架构宏和 enum candidate Observation，保持 comment hint 独立。

**验收**

- 能从使用点追溯到宏定义和最终 x86 intrinsic/header/feature。
- 同一根因的使用引用不会产生互不关联的重复问题。
- 模糊标识符只有获得代码上下文证据后才升级为可操作 Finding。

### 2.6 `expand-rpm-architecture-relations`

**范围**

- 扩展 `%ifarch/%ifnarch`、`_arch`、`_target_cpu`、`_isa`、`__isa_name` 等静态语义。
- 分析架构宏在依赖、build、install 和 check section 中的关系。
- 继续使用独立 RPM YAML 规则并保持现有输出契约。

**验收**

- 普通依赖和注释/changelog 不新增误报。
- 架构条件依赖和缺失 RISC-V 路径具有 section、条件栈和 trace。
- 当前 RPM fixture 全部通过。

### 2.7 `add-static-project-readiness-assessment`

**范围**

- 汇总 sourceReachability、buildSelection、architectureDependencies、alternativeImplementations、testCoverage、inputCompleteness。
- 产生静态 readiness 状态和计数。
- 投影到可选 `summary.readiness`。

**验收**

- 仅靠零 Finding 不得得到 `riscv_ready`。
- 输入不足时必须存在 unknown 维度。
- `staticOnly=true`，不暗示真实编译或测试成功。
- 旧后端忽略或保存 readiness 时，既有导入行为不变。

### 2.8 `link-memory-model-assessment`

**范围**

- 只定义 memory-model IR checker 结果的引用和摘要边界。
- 不在 KB Scanner 内实现线程同步或 RVWMO 分析。

**验收**

- 外部结果存在时记录工具/产物身份和摘要。
- 外部结果缺失时为 unknown/not-run，不解释为通过。

## 3. 依赖顺序

```text
introduce-kb-analysis-core
        ↓
adapt-existing-kb-assets-to-analysis-core
        ├── add-static-build-selection-analysis
        │        ├── add-architecture-aware-test-analysis
        │        └── add-static-project-readiness-assessment
        ├── add-cross-file-macro-relations
        └── expand-rpm-architecture-relations

link-memory-model-assessment ──→ add-static-project-readiness-assessment
```

项目 readiness 应最后落地，因为它依赖前面多个关系分析器的稳定语义。

## 4. 技术 Spike 计划

### 4.1 实现语言

**问题**：继续使用 Python，还是迁移核心实现语言。

**验证内容**：

- 在代表性项目上测量当前扫描时间、峰值内存和规则加载成本。
- 估算关系图规模及最坏边数。
- 比较 Python 原地演进与其他语言重写的部署、依赖、调试和后端调用成本。

**退出条件**：形成 ADR，只有 Python 无法达到明确性能/部署指标时才建议换语言。本 change 不预设结论。

### 4.2 C/C++ 深层前端

**候选**：现有轻量解析、libclang、Clang tooling、tree-sitter 或组合模式。

**验证 fixture**：条件编译、宏展开、多行 inline asm、模板/if constexpr、语法不完整文件和缺失 include。

**退出条件**：记录预处理器保真度、错误恢复、安装体积、平台支持和性能；选型必须允许轻量模式继续作为 fallback。

### 4.3 Makefile/Autoconf 部分求值

**第一阶段候选边界**：简单赋值、递归/立即展开变量、`ifeq/ifneq/ifdef/ifndef`、有限 include、变量拼接、已识别 selector、静态源码列表。

**明确不求值**：任意 shell 副作用、递归 make 的开放世界状态、运行时生成且无静态边界的文件集合。

**退出条件**：以真实开源项目片段建立 supported/unknown 矩阵；所有 unsupported 表达式必须产生稳定 diagnostic，而不是猜测。

### 4.4 架构 Selector 目录

**问题**：除 `uname -m` 外，首批识别哪些架构来源。

**候选**：`CMAKE_SYSTEM_PROCESSOR`、Autoconf host/cpu 变量、RPM `_arch/_target_cpu`、编译器预定义宏和项目传入 `ARCH`。

**退出条件**：每个 selector 定义规范化值、可信边界、RISC-V alias 和 unknown 行为；不加入交叉编译误选推理。

### 4.5 证据图性能

**验证内容**：实体/关系稳定 ID、索引方式、去重、循环宏/include、最大追踪深度和序列化成本。

**退出条件**：给出默认资源上限和截断 diagnostic；没有数据证明前不引入图数据库。

## 5. 已接受决策

- KB Scanner 只做静态分析。
- C/C++、构建、RPM 和测试静态语义在范围内；OS/内核/系统调用/硬件迁移不在范围内。
- `uname` 必须分析，但假设返回正确机器架构，不考虑交叉编译误选。
- 保留 Clang/GCC 两份编译器派生事实数据及 `generatedSet`。
- 使用 Fact/Evidence → Relation → Finding → Assessment 的四层语义。
- 对外保持现有 `scan-result.json` schemaVersion `1.0` 和三个 artifact。
- 新关系优先写入 Finding `trace`，项目级静态评估写入可选 `summary.readiness`。
- memory-model IR checker 继续负责 RVWMO 分析。

## 6. 延后到后续 Change/Spike 的问题

- 核心实现语言。
- C/C++ 深层解析器选型。
- Makefile/Autoconf 第一阶段精确支持子集。
- 首批架构 selector 完整列表。
- Evidence Graph 的具体类、索引和资源上限。
- `rulePack` 中知识来源可选元数据的最终字段名。
- memory-model 外部摘要的具体接入时机。

这些问题不阻塞本设计 change 收口，也不得在没有独立 change 的情况下直接进入运行时代码。
