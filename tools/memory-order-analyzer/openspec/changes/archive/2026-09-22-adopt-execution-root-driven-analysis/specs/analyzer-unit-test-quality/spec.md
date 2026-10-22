## ADDED Requirements

### Requirement: Unit test every execution-root R1 owned module at ninety percent coverage

R1 新增、修改或复用的 C++/Python worker、schema/引用验证、AST/BC 候选发现、证据对齐、root identity、reachable planner、P2/P3 编排、cache、预算、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but root alignment does not
- **WHEN** 项目和语言覆盖率达标而任一候选合并、证据分类、reachable planner或 P2/P3 adapter 模块的行/分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成、同步或归档

#### Scenario: Integration executes an untested frontier branch
- **WHEN** 间接调用、profile 冲突或 root 预算集成用例通过但对应自有 partial/unknown 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛、排除模块或用无有效断言测试凑数

### Requirement: Exercise four-language root discovery semantics entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11、C17、C++17、C++20 独立 truth，覆盖显式 root、唯一 main、库导出入口、直接 pthread、跨 TU wrapper、std::thread profile、AST+IR、IR-only、AST-only、无 debug、开放 scope、callback 冲突、间接调用、递归、预算、缓存损坏、CLI 退出码和中英文字段。C fixtures MUST 不依赖 C++ AST 或标准库模型；测试不得访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: Candidate union preserves an unmatched source site
- **WHEN** AST truth 含创建候选而 BC 侧无法匹配
- **THEN** 集成断言候选以 source-candidate 和非空 frontier 保留，不因缺少交集而消失

#### Scenario: Exact IR-only pthread is retained
- **WHEN** 无 AST/no-debug 输入具有受支持直接 pthread ABI 和唯一 callback SSA target
- **THEN** 集成断言创建点为 ir-exact、源码完整性降低且 root plan仍可审计

#### Scenario: One language profile is absent
- **WHEN** C11、C17、C++17 或 C++20 任一 required profile 没有 planned/completed、root truth 和诊断断言
- **THEN** R1 语义验收失败，不能由其他语言或合并分母替代

### Requirement: Publish repeatable R1 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言 root truth、P1–P4/A1–A5 黄金回归、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、LLVM/Clang/profile/version/hash、测试数、hit/total、各语言 planned/completed/exact/candidate/ambiguous/unsupported/failed、root/reachable coverage、缓存、排除理由和报告位置。任一 required gate 未执行、失败、覆盖不足或环境阻塞时任务 MUST 保持未完成。

#### Scenario: A supported exact root remains ambiguous
- **WHEN** 人工审计确认 required 范围内 AST/IR/ABI/callback 证据完整而结果仍为 ambiguous、遗漏或错误 root
- **THEN** 验收失败并增加针对性单元/集成回归，不能以其他 truth、90% 覆盖率或零 finding 替代修复

#### Scenario: All R1 gates pass
- **WHEN** 全量单元与离线语义测试通过，整体、C++、Python和每个受影响模块行/分支 hit/total 均至少 90%，四语言 truth 无支持范围内错误且旧协议回归稳定
- **THEN** acceptance 记录实际结果和 `safety=not_evaluated` 限制，方可标记实现完成并提示同步/归档
