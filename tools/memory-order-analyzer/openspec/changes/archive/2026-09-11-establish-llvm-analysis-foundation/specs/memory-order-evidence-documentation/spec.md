## MODIFIED Requirements

### Requirement: Keep DevKit observations separate from validation plans

文档 SHALL 保留有日期的 SSH 网络阻塞历史，并按日期区分新 ARM/DevKit 实测、对应版本官方流程和剩余待验证项；SHALL 纳入 2026-09-11 DevKit 25.3.0、自带 LLVM 16.0.4 的代表证据及完整性限制，不再把已执行项目统一标为待验证。SHALL 保留版本探测、BC 接受、跨模块输入和报告解释矩阵，不以在线远端连接作为本 change 的日常或归档验收前提。

#### Scenario: No new ARM validation evidence is collected

- **WHEN** 某次文档整理没有执行新的 ARM/DevKit 实验
- **THEN** 只引用此前有日期和来源的历史记录，不声称该次重新确认了当前网络状态或工具行为

#### Scenario: Preserve the September 11 experiment evidence

- **WHEN** 纳入 2026-09-11 的实测
- **THEN** 保存环境、命令、源码/产物 hash、代表原始报告与完整矩阵入口，说明 47 份 success 报告不是检测正确率、322 文件 hash 验证不是单元覆盖率，并区分提交的证据子集与完整原包

#### Scenario: Interpret independent and linked bitcode results

- **WHEN** 文档比较三个 object BC 的零建议与 linked BC 的 2/3/4 条建议
- **THEN** 明确三个 TU 来自同源码不同 PART 配置，结论限定该样例，说明同目录扫描未自动恢复所需关联，不声称已经验证所有跨文件能力

#### Scenario: Compiler exit zero or scanner success is misleading

- **WHEN** 引用 bc-gen 零退出零产物、缺 debug 零建议或正确同步仍被建议插入屏障的结果
- **THEN** 文档分别说明产物/定位/语义判定限制，不把 mm-check 作为 C/C++ 并发正确性 oracle 或自动修复依据

### Requirement: Provide discoverable and consistent documentation

项目 README 和文档索引 SHALL 链接构建上下文、跨 TU、BC 流水线、分析设计、实验与 DevKit 专题，并增加实际实现的开发容器、CLI/schema 和测试验收入口；文档 SHALL 保持阶段说明、统计值、状态和术语一致，对外部技术结论标注出处及版本，对本地文件提供有效链接。SHALL 区分已完成基础设施与未实现的线程/别名/内存序判定，不依赖归档项目。

#### Scenario: Follow the documentation entry point

- **WHEN** 新读者从项目 README 进入文档
- **THEN** 可找到各专题、实测证据、开发镜像构建和测试命令，并明确当前只实现已验收的基础设施，尚不能输出并发安全结论

#### Scenario: Development image is delivered before production consolidation

- **WHEN** 本 change 已完成独立开发镜像构建验证
- **THEN** 文档记录该完成状态和复现命令，同时明确与生产 Dockerfile 的合并属于后续 change，不将两项工作混为未交付或已合并
