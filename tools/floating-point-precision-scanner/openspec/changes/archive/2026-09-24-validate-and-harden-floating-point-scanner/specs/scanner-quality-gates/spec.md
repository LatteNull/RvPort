## ADDED Requirements

### Requirement: Reviewed corpus 和检测质量必须成为交付门禁
实现变更交付前 SHALL 运行完整 validation corpus，并按 finding code 报告 TP、FP、FN、strict/supported-only precision/recall、exact match 和 abstention。缺失 oracle 类别、任一规则低于 90% strict precision/recall、整体 exact match 低于 95% 或失败生命周期 case 非 100% exact match 时，质量任务 MUST 保持未完成。

#### Scenario: 只运行单元测试未运行 corpus
- **WHEN** 单元测试和覆盖率通过但 reviewed corpus 未执行
- **THEN** 本 change 的质量验收失败，不能以单元覆盖率替代检测质量

### Requirement: 故障注入必须覆盖全部新增边界
单元测试 SHALL 覆盖共享 deadline、CPU/RSS 超限、Clang/LLVM worker 终止、文件/字节/输出/facts/evidence/rule/diagnostic/suppression 预算、缓存 miss/损坏/冲突/原子写失败、结果 fsync/replace 失败以及 suppression 有效/到期/缺少 policy 日期。每类测试 MUST 断言 status、退出码、分母、frontier、诊断、旧文件保留和路径脱敏。

#### Scenario: 只断言异常被抛出
- **WHEN** 故障测试没有断言公开状态、诊断和既有产物完整性
- **THEN** 该异常路径不视为完成测试覆盖

### Requirement: Python 和 C++ 覆盖率门禁必须继续统计全部项目源码
coverage 配置 SHALL 纳入 `src/floating_point_precision_scanner` 和 `src/cpp` 全部项目自有可执行源码，包括未被测试加载的文件。项目整体及本次受影响模块的行覆盖率、分支覆盖率 MUST 分别不低于 90%；validation/benchmark 集成测试、编译成功或静态检查不得替代单元测试。第三方 LLVM/GTest、生成构建文件和无手写逻辑生成物可以排除，但 MUST 在报告中列出理由。

#### Scenario: 新增缓存模块未被单元测试加载
- **WHEN** 缓存源码存在但测试未导入
- **THEN** 该源码仍进入覆盖率分母并可能导致门禁失败

### Requirement: 性能、确定性和缓存等价必须独立验收
交付前 SHALL 在固定 benchmark 环境执行 S/M/L 三档冷、热缓存测试和不同绝对工作区重复测试，检查绝对资源上限、相对基线回退、热缓存比例以及语义字节等价。无法满足固定环境、任一资源指标缺失或任一档位超限时，性能验收 MUST 保持未完成。

#### Scenario: 热缓存更快但语义不同
- **WHEN** 热缓存达到耗时门禁但任一 assessment、finding、diagnostic 语义、stable ID 或排序不同
- **THEN** 缓存等价门禁失败且不得接受该性能结果

### Requirement: 验证报告必须公开全部命令和产物
最终验证报告 SHALL 列出单元测试、contract、validation corpus、benchmark、Python/C++ coverage、lint、typecheck 和严格 OpenSpec 校验命令，并报告测试数量、失败数、逐规则质量指标、三档性能、整体/受影响模块行分支覆盖率、统计范围、排除项及报告位置。未执行或受环境阻塞的项目 MUST 明确标为未完成。

#### Scenario: 性能环境不可用
- **WHEN** 交付环境无法运行固定 4 vCPU/4 GiB benchmark
- **THEN** 报告记录阻塞原因，任务不标记完成且不声称性能达标
