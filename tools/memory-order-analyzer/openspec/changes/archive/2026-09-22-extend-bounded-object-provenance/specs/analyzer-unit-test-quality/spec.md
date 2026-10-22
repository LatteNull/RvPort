## ADDED Requirements

### Requirement: Unit test every A5 owned executable module at ninety percent coverage

A5 新增、修改或复用的 Clang/LLVM C++ worker、schema/引用验证、对象/路径身份、候选 lattice、AA/MemorySSA/CaptureTracking 证据、pointer-field 传播、跨 TU 参数/返回/receiver 组合、A4/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python 和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but provenance composition does not
- **WHEN** 项目和语言覆盖率达标而任一候选、pointer-field、跨 TU composition或 adapter 模块的行/分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成、同步或归档

#### Scenario: Integration executes an untested conservative branch
- **WHEN** clobber、候选超限或 AST-only 集成用例通过但相应自有 unknown/partial 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛、排除模块或用无有效断言测试凑数

### Requirement: Exercise A5 C and C++ provenance semantics entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11、C17、C++17、C++20 独立 truth，覆盖单/跨 TU、struct/union、嵌套和 pointer field、参数/返回值、C++ `this`/对象/mutex 字段、phi/select/cast/GEP、唯一/多重/未知 clobber、无 debug、AST+IR、IR-only、AST-only、failed、开放 scope、ABI/profile 失配、预算、缓存损坏、CLI 退出码和中英文字段。C fixture MUST 独立于 C++ AST/标准库模型；测试不得访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit、SVF、PhASAR 或外部后端。

#### Scenario: Different instances share one field declaration
- **WHEN** C 或 C++ fixture 中两个 storage instances 访问同一声明的 mutex/payload field
- **THEN** truth 断言对象身份不合并、may 不提升 must，A4/P4 adapter 不产生虚假同对象证明

#### Scenario: The same instance crosses a direct wrapper
- **WHEN** 四语言对应 fixture 具有唯一直接 definition、相容 ABI/profile 和完整参数/返回或 receiver 证据
- **THEN** truth 断言跨 TU 保持同一 storage/subobject identity及完整 proof chain，无需 llvm-link、目标链接或运行程序

#### Scenario: One language profile is missing
- **WHEN** C11、C17、C++17 或 C++20 任一 required profile 没有 planned/completed 数、truth 和诊断断言
- **THEN** A5 语义验收失败，不能用其他语言、合并分母或覆盖率替代

### Requirement: Publish repeatable A5 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言 provenance truth、P1–P4/A1–A4 黄金回归、A4 同名字段实例回归、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、LLVM/Clang/profile/version/hash、测试数、hit/total、各语言 planned/completed/TP/FP/FN/abstention、模式完整性、缓存、排除理由和报告位置。任一 required gate 未执行、失败、覆盖不足或环境阻塞时任务 MUST 保持未完成。

#### Scenario: A supported exact case remains unknown
- **WHEN** 人工审计确认一个 required 范围的 C/C++ 直接调用对象绑定证据完整但最终为 unknown或错误对象
- **THEN** 验收失败并增加针对性单元/集成回归，不能以其他 truth、90% 覆盖率或零风险 finding 替代修复

#### Scenario: All A5 gates pass
- **WHEN** 全量单元与离线语义测试通过，整体、C++、Python和每个受影响模块行/分支 hit/total 均至少 90%，四语言 truth 无支持范围内错误且旧协议回归稳定
- **THEN** acceptance 记录实际结果和 `safety=not_established` 限制，方可标记实现完成并提示同步/归档
