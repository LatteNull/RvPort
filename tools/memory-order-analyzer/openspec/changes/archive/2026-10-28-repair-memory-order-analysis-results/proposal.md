## Why

实际调查发现分析编排和协议错误阻断正式分析，普通读写被过度投影为源码候选，阶段诊断丢失，输出的证据等级与完整性不足以支持准确消费。本 change 修复分析器自身的请求编排、候选准入、结果投影和诊断合同。

## What Changes

- 本变更为分析器运行时修复；2026-10-28 按用户要求修订 artifacts，将实施文件边界收紧为当前工具 root。本次范围修订仅修改文档与 OpenSpec 配置。
- 修复 AST/IR/R3 成员身份和排序、显式 P3 引用、空输入及缺依赖处置、语言标准与原子策略一致性、C++ profile 匹配诊断。
- 保留原始源码事实和计划分母，仅将有可追溯内存序相关性依据的源码形状发布为待核实候选，保留准入审计与全部 occurrences。
- **BREAKING（版本化输出）**：新输出使用 MemoryOrderFindingProjection 3.0，增加 evidenceLevel，允许未评估 confidence 为 null；本工具仍校验合法 2.0 历史数据。候选为 info、非阻断、unknown/partial，不伪造概率或正式结论。
- 汇总 ingestion、source、适配器和下游诊断/frontier；保留 Scope/TU、双语说明、阶段引用、截断前分母和完整审计。
- 保留 primaryPath、edges、breaks 的独立投影语义，保证引用正确；页面渲染交由外部消费者。
- 隔离旧结果缓存，排除并发 Scope 尚未发布的任务目录和原子写入临时文件。
- 在 Docker 中执行本工具全量单元、真实协议/worker 集成及整体、语言、模块的行/可用分支至少 90% 门槛。

## Capabilities

### New Capabilities

无。原拟新增的 memory-order-result-consumption 属于外部应用消费行为，已从本 change 的 delta specs 移除。

### Modified Capabilities

- unified-project-analysis-entry：输入规范化、依赖选择、阶段适用性、诊断传播和缓存隔离。
- degraded-source-analysis：内部事实与对外候选分离、相关性准入、去重及可审计分母。
- memory-order-finding-evidence-projection：3.0 投影、证据等级、双语说明及主路径/断点引用合同。
- analyzer-unit-test-quality：工具自身的真实协议回归、Docker 隔离和全量覆盖率验收。

## Impact

- 唯一 OpenSpec root 及文件写入边界为 D:/projects/RvPort/tools/memory-order-analyzer/。代码、测试、配置、规格和文档修改均限于该目录。
- 涉及本工具 python/、schemas/、protocols/、tests/、doc/ 和 openspec/。不新增通用 HB 求解器或全程序安全证明，生产分析流程不生成 BC。
- 后端、前端、仓库根和兄弟工具不属于本 change 的实施范围；依赖关系不能推导出跨 root 修改授权。外部消费者应在各自 root 管理接入与验收。
- 3.0 字段、候选数量和诊断信息影响外部消费；接口与前端待办见 [前端交接说明](frontend-handoff.md)，该文档不是本 change 的实施任务或外部项目规范。
- 2026-10-27 已完成的后端修改由用户本次接受，保留代码和历史验证记录，不回滚，也不据此继续跨目录实施。此前未完成的前端任务是移出范围，未被标记为完成。
- 历史仓库级 Compose 与后端验收只作为既有记录保留。本工具的代码验收使用自身全量 Python/C++ 统计，不能用外部项目结果替代。