## ADDED Requirements

### Requirement: Exercise the P4 publication semantic matrix offline
项目 SHALL 提供直接 POSIX pthread 的 C11/C17 与 C++17/C++20 固定单 TU、物理跨 TU 和 IR 输入，覆盖普通 flag、relaxed flag 与普通 payload、release/acquire、seq_cst、fence unsupported、过晚 acquire、改名 flag、all-atomic relaxed、发布过早、不同 flag、多写者、重复发布、初值与发布值相同、单线程、join 后访问、未知调用、无 debug、开放 scope、预算及 wrapper 可解析/不可解析。期望 SHALL 来自明确语言语义和人工核对，不以 DevKit、SSH、运行频率或编译成功作为 oracle。

#### Scenario: CASE0 through CASE7 equivalents are analyzed with pthread
- **WHEN** 开发容器离线运行 P1/P2/P3/P4 固定矩阵
- **THEN** 对每例断言候选、finding/discharged/unknown、证据链、完整性和退出码，且不需要网络、SSH、DevKit、llvm-link 或运行目标程序

#### Scenario: The existing std-thread experiment remains in the repository
- **WHEN** `doc/experiments/publication.cpp` 继续使用 `std::thread`
- **THEN** 测试只把它作为 IR 表达对照，P4 端到端测试不借此宣称 P3 支持 std::thread

### Requirement: Unit test every P4 owned code path at ninety percent coverage
所有新增、修改或复用的 P4 C++、Python、schema/引用校验、cache、CLI、report 和质量入口逻辑 SHALL 有正常、边界、异常及 unknown 单元测试；项目整体、Python、C++ 和每个受影响自有模块的行覆盖率及分支覆盖率 MUST 均至少 90%。未被测试加载的新增源码 MUST 纳入分母，语义集成与单元 profile 分开统计。

#### Scenario: Risk logic passes integration but lacks branch coverage
- **WHEN** pthread 矩阵通过，但任一受影响规则/worker/report 模块分支覆盖率低于 90%
- **THEN** 质量验收失败，任务不得标记完成或提示归档

#### Scenario: All P4 quality gates pass
- **WHEN** 单元、文档和独立集成测试通过，整体、语言及逐受影响模块行/分支 hit/total 均至少 90%
- **THEN** 验证文档记录精确命令、版本、统计范围、排除理由、结果和新报告目录
