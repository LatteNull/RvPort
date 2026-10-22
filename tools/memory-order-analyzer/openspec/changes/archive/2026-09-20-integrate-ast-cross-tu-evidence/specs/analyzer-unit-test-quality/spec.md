## ADDED Requirements

### Requirement: Unit test every AST-assisted owned module at ninety percent coverage

所有新增、修改或复用的 LibTooling worker、schema/引用校验、profile identity、entity index、binding、overlay、下游适配、预算、cache、CLI、报告和双语诊断 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、C++、Python 及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未被测试加载的项目源码、子目录和可执行头文件必须进入分母。

#### Scenario: Overall coverage passes but the entity resolver does not

- **WHEN** 项目整体和语言覆盖率达标而 entity resolver 任一行或分支指标低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

#### Scenario: Integration cases execute untested worker branches

- **WHEN** 集成矩阵成功但 worker 的错误或预算分支缺少单元断言
- **THEN** 不能用集成执行补入单元覆盖率或缩小统计范围

### Requirement: Exercise AST-assisted semantics entirely offline

日常单元和固定集成门禁 SHALL 使用本地 C/C++ fixture、合成/固定 P1–P5 产物和锁定开发容器，覆盖编译 profile、linkage/ABI、USR 缺失、定义歧义、绑定基数、no-debug、候选相关完整性、预算、缓存损坏、CLI 退出码和双语字段。测试 MUST NOT 访问网络/SSH、执行用户 CMake、运行 ARM DevKit/外部后端或运行被分析目标程序。

#### Scenario: Cached overlay references a replaced binding

- **WHEN** 单元测试提供 schema 有效但 dependency digest 陈旧的 cache fixture
- **THEN** 系统拒绝复用并产生确定中英文诊断，不静默返回旧结果

### Requirement: Publish repeatable AST-assisted quality acceptance

交付前 SHALL 在独立开发容器使用新输出目录实际运行全量单元测试、整体/语言/受影响模块覆盖率门槛、离线 truth 矩阵、旧协议回归、TinyCThread cold/warm 基线和文档校验，并记录命令、版本/hash、测试数、line/branch hit/total、truth 指标、完整性、性能、缓存和报告位置。任一必需门禁失败时任务 MUST 保持未完成。

#### Scenario: Host Python lacks pytest but the development image is available

- **WHEN** 宿主机不能执行单元测试而锁定开发容器包含测试依赖
- **THEN** 验收必须在开发容器实际执行并记录结果，不能把宿主环境缺失声明为通过

#### Scenario: A previously accepted supported case is a false negative

- **WHEN** 验收后审计证明一个明确支持范围的 reviewed risk case 因实现错误返回 unknown
- **THEN** change 重新打开并增加针对性单元/集成回归；修复后重跑全量单元、逐模块 line/branch 90% 门禁和固定 truth，旧验收数字不得继续当作最终结果
