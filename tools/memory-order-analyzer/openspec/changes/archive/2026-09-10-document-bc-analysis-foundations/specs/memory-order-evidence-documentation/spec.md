## ADDED Requirements

### Requirement: Distinguish memory-model semantic layers

文档 SHALL 区分 C/C++ 语言模型、LLVM IR 语义和硬件内存序，说明普通数据竞争、全原子协议顺序风险和目标硬件迁移风险的差别；SHALL 解释 atomic/fence、线程入口、共享对象、锁、reads-from 与 happens-before 的联系及未建模边界。

#### Scenario: IR contains atomic operations and fences

- **WHEN** 读者在 BC 中观察到 atomic 或 fence
- **THEN** 文档说明其存在不等于已经建立跨线程同步，并明确 volatile、编译器屏障和信号 fence 不能直接替代通用线程同步

#### Scenario: Optimization changes visible accesses

- **WHEN** 同一示例在 O0 和优化配置下的 IR 不同
- **THEN** 文档结合源语义与编译配置解释差异，不将被优化掉的普通访问解释为原程序已无并发风险

### Requirement: Preserve experiment provenance and scope

文档 SHALL 将本地实测、官方资料、设计建议和待验证结论分开标注；SHALL 保留现有实验的日期、环境、源文件、命令、原始 JSON 入口、27 个 BC 模块和 74 项检查的统计含义，并区分示意命令与实际执行命令。

#### Scenario: Summarize the existing Clang experiment

- **WHEN** 文档引用 2026-09-10 的 Clang 18.1.3 结果
- **THEN** 文档可追溯到 `doc/experiments/results/clang18-evidence.json`，且不将 74 项检查表述为缺陷检测准确率、完整验证或程序安全证明

### Requirement: Keep DevKit observations separate from validation plans

文档 SHALL 保留有日期的 SSH 网络阻塞记录，明确未执行的 DevKit 检查，引用对应版本的官方流程并保留版本探测、BC 接受、跨模块输入和报告解释的待验证矩阵；SHALL 不以远端连接成功作为本次文档验收前提。

#### Scenario: No new ARM validation evidence is collected

- **WHEN** 本次文档整理没有执行新的 ARM/DevKit 实验
- **THEN** 文档保持历史观察及待验证标注，不声称当前网络状态或 DevKit 功能已被重新确认

### Requirement: Explain coverage before interpreting findings

文档 SHALL 区分构建覆盖和分析完成度，并说明缺失 TU、外部实现、未建模同步与超时等对结论的限制。

#### Scenario: A partial analysis reports zero findings

- **WHEN** 编译不完整或分析存在未知行为且报告零告警
- **THEN** 文档明确零告警仅描述已覆盖范围内的结果，不能解释为全程序并发安全

### Requirement: Provide discoverable and consistent documentation

项目 README 和文档索引 SHALL 链接构建上下文、跨 TU、BC 流水线、分析设计、实验与 DevKit 专题；文档 SHALL 保持阶段说明、统计值、状态和术语一致，对外部技术结论标注官方出处及适用版本，对本地文件提供有效链接。

#### Scenario: Follow the documentation entry point

- **WHEN** 新读者从项目 README 进入文档
- **THEN** 可以按阅读顺序找到所有专题、实验原始证据和未验证项，并明确本项目尚无生产分析器实现且不依赖归档项目
