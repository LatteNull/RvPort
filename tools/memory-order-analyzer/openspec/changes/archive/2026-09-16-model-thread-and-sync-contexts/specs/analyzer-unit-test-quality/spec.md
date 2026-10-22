## ADDED Requirements

### Requirement: Unit test every P3 owned executable module

所有新增、修改或复用的 P3 自有 C++/Python 执行逻辑 SHALL 有带有效断言的单元测试，覆盖正常行为、边界条件、异常输入和保守 unknown 路径。质量枚举 SHALL 纳入未被测试加载的 Python、未调用的 C++、新增子目录和可执行头文件；集成测试、编译成功、schema 校验或静态检查 MUST NOT 替代单元测试。

#### Scenario: A new thread-analysis source is not loaded by tests

- **WHEN** 新增 Python/C++ 模块进入项目自有执行源码但没有 coverage 数据或单元执行
- **THEN** 质量入口失败并列明文件，不能因该文件没有命中记录而从统计范围排除

#### Scenario: P2 order is accidentally reused as proof

- **WHEN** 测试输入只有 P2 EffectSummary.order 而没有合法 P3 ExecutionOrderFacts
- **THEN** 单元测试断言不得生成 must-before/HB，并覆盖分支、循环和跨调用反例

### Requirement: Enforce ninety-percent P3 and project coverage gates

交付 P3 代码前 SHALL 实际执行可重复的单元覆盖率入口；项目整体、Python、C++ 以及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%。统计 SHALL 使用 hit/total 聚合且包含未加载源码，不得缩小范围、降低门槛或用无有效断言测试凑数。

#### Scenario: A module has 89.99 percent branch coverage

- **WHEN** 整体覆盖率达标但任一受影响模块的行或分支覆盖率低于 90%
- **THEN** 质量验收失败，相关任务不得勾选，补测或修复后必须使用新的报告目录重新执行

#### Scenario: All thresholds are satisfied

- **WHEN** 单元测试全部通过，整体、语言和逐受影响模块行/分支 hit/total 均不少于 90%
- **THEN** 质量报告记录精确命令、工具版本、统计范围、排除理由和报告位置，集成结果另行列示

### Requirement: Exercise fixed pthread semantic fixtures independently

项目 SHALL 提供固定离线 pthread C/C++ 物理 TU 和 IR 夹具，覆盖同入口多实例、main/worker、create 成败、join 前后、handle 覆盖、相同/不同 mutex、lock 失败/提前 unlock、递归/循环合并、未知 callback/wrapper、原子候选、跨 TU、无 debug 及损坏依赖。语义集成测试 SHALL 与单元覆盖率分别报告，且不得依赖 SSH、DevKit 或网络。

#### Scenario: The fixed multi-TU fixture is analyzed offline

- **WHEN** 在独立开发容器中对三个或更多物理 TU 执行 compile-only、P1/P2 和 P3 流程
- **THEN** 断言线程实例、生命周期、MHP、mutex/atomic 候选和证据链符合预期，无需 llvm-link、原生链接或运行目标程序

#### Scenario: An unsupported construct is present

- **WHEN** 固定反例包含 std::thread/RAII、自定义 wrapper、未识别 mutex 或间接 callback
- **THEN** 测试断言相关项进入 partial/unknown 且不产生虚假确定顺序、同步或安全结论
