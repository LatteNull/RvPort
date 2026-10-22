## Why

P1–P4 已经形成可运行的一次性发布风险分析链，但当前证据主要来自固定语义夹具，尚不能回答真实工程中的输入覆盖、unknown 分布、误报/漏报边界、资源消耗和外部后端可用性。现在需要先建立可复现、带人工真值且不改变现有分析语义的 P5 验证与规模化基线，再用量化结果决定后续能力投资。

## What Changes

- 这是一个包含运行时验证工具、数据契约、固定输入、测试和文档的实现型 change，不是仅文档变更；同时修正路线图中 P4 尚待 sync/archive 的过时状态。
- 新增独立版本化的验证套件清单、人工真值注解、运行结果和决策记录，引用但不改写 P1–P4 产物，明确区分预期、观察结果、人工复核、unknown、unsupported 和工具失败。
- 建立完全离线的 C11/C17/C++17/C++20 单 TU、物理跨 TU 验证集，覆盖正确、风险和 unknown/unsupported，对候选、assessment、完整性、证据链和退出码进行确定性比对。
- 选择并固定一个许可、版本和来源可审计的真实 GCC/Clang C/C++ CMake 工程；消费已有 `compile_commands.json` 与显式 scope，不擅自执行配置、构建、安装或目标程序，记录输入闭包和选择偏差。
- 增加可重复的规模验证入口，统计计划/成功 TU、P1–P4 分层完整性、未知调用/对象/同步、候选与 finding/discharged/unknown、人工裁决、运行时间、峰值内存和冷/热缓存行为；只有带完整真值的离线集计算准确率类指标。
- 通过独立进程/容器适配器隔离评估 GenMC 与 herdtools7；ARM DevKit 仅接受显式提供的历史或新证据包作为可选对照，日常测试和归档不得依赖网络、SSH 或专有工具可用性。
- 生成有量化依据的后续决策记录，分别评估 B1 CMake scope 导入、`std::thread`、更强指针分析以及 fence/RMW 支持，不在本 change 中直接实现这些通用能力。
- 保持 ModuleFacts/RunReport v2、EffectSummary v1、ThreadContextGraph v1、PublicationRiskReport v1 及现有 CLI/退出码/缓存语义不变；验证结果不得回写或提升 P1–P4 的 unknown 与安全结论。
- 为全部新增、修改或复用的自有执行代码提供正常、边界、异常和 unknown 路径单元测试；项目整体、Python、C++ 及每个受影响模块的行覆盖率和可用分支覆盖率均至少 90%，集成、真实工程和外部后端结果与单元覆盖分开统计。

## Capabilities

### New Capabilities

- `analysis-validation-corpus`: 定义离线人工真值语料、真实 CMake 工程选择与固定输入清单、语言/编译配置矩阵以及可审计的预期结果。
- `analysis-validation-reporting`: 定义独立版本化的验证请求、运行报告、准确性/完整性/性能/缓存统计、人工裁决和后续决策记录。
- `external-backend-evaluation`: 定义 GenMC、herdtools7 和可选 ARM DevKit 的隔离适配、证据身份、失败边界与非 oracle 约束。

### Modified Capabilities

- `analyzer-unit-test-quality`: 将 P5 验证 runner、schema、统计、适配器和决策逻辑纳入全部自有代码单元测试与整体/语言/逐模块 90% 行和分支覆盖率门槛。
- `memory-order-evidence-documentation`: 要求路线图和文档索引反映 P4 已同步归档及 P5 的真实状态，并区分人工真值、实际观察、外部工具对照和未验证结论。

## Impact

- 主要影响 `tools/memory-order-analyzer` 内新增的验证 CLI/runner、严格 schema、固定语料和真实工程 profile、指标/报告生成、外部后端适配、质量入口及中文文档；所有 OpenSpec 产物保留在本项目内。
- P1–P4 分析器、产物 schema 和既有命令作为只读被测对象，不做破坏性迁移；新验证缓存和报告使用独立身份与输出目录。
- GenMC、herdtools7、ARM DevKit 和真实项目不成为核心安装或运行依赖；第三方版本、许可证、hash、容器/进程边界和不可用原因必须显式记录。
- 实现验收需要开发容器内的离线单元/集成/覆盖率门禁，并另外发布真实工程规模测试和可选后端实验结果；没有人工真值的真实工程数据不得包装成准确率或全程序安全结论。
