## ADDED Requirements

### Requirement: Unit test every P5 owned executable module at ninety percent coverage

所有新增、修改或复用的 P5 runner、schema/引用校验、truth 比较、指标、抽样、资源采集、cache、外部适配器、CLI、报告和决策逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++ 及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须纳入分母，集成/真实工程/外部工具 profile 不得补入单元覆盖。

#### Scenario: An adapter is covered only by an external integration run

- **WHEN** 外部工具实验成功但适配器错误、超时或解析分支未被单元测试命中
- **THEN** P5 质量门禁失败，不能用 live backend 结果替代单元覆盖或缩小统计范围

#### Scenario: Overall coverage passes but a validation module fails

- **WHEN** 项目整体和语言覆盖率达标而任一受影响模块行或分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

### Requirement: Exercise P5 validation semantics entirely offline

单元和固定集成验收 SHALL 使用本地 truth/语料、合成 P1–P4 产物、录制 GenMC/herdtools7/DevKit 输出及固定真实工程 profile，覆盖 schema 版本、陈旧 digest、TP/FP/FN/unknown 分母、零分母、确定性抽样、cold/warm digest、预算、损坏缓存、后端不可用和双语决策。日常质量门禁 MUST NOT 访问网络、SSH、运行专有工具、执行用户 CMake 或运行被分析程序。

#### Scenario: Recorded backend evidence is malformed

- **WHEN** 测试输入未来版本、截断 JSON、错误 input hash 或 exit-zero 空报告
- **THEN** 单元断言 failed/partial 和完整诊断，不产生 agreement 或安全结论

#### Scenario: Cold and warm observations are semantically identical

- **WHEN** 固定输入仅在时间、路径和 cache hit 计数上不同
- **THEN** 单元断言 semantic digest 相同，同时原始资源指标分别保留

### Requirement: Publish repeatable P5 quality and validation acceptance

交付前 SHALL 在独立开发容器使用新输出目录实际运行全量单元测试、覆盖率门槛、离线语料集成、真实工程 cold/warm 基线和文档校验，并分别记录命令、版本/hash、测试数、整体/语言/逐模块 hit/total、语料指标、完整性、性能、缓存和报告位置。外部 live backend 若环境不可用 SHALL 明确 not_run/partial，不能阻塞核心离线门禁，也不能伪装已执行。

#### Scenario: Core quality passes while optional live backends are absent

- **WHEN** 单元、覆盖、离线语料和真实工程基线全部通过，但实施环境没有可验证的 GenMC/herdtools7 镜像
- **THEN** 核心验收可记录完成，live backend 明确 not_run，并保留适配器录制夹具测试结果和后续复现命令

#### Scenario: A required offline gate fails

- **WHEN** 任一单元测试、90% 门槛、truth comparison、确定性或真实工程完整性验收失败
- **THEN** 任务保持未完成并保存差距，不以历史 P4 覆盖率、外部工具一致或部分报告提示归档
