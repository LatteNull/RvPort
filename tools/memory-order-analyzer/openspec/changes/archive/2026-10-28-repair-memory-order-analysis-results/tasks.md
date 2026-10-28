> 范围修订（2026-10-28）：当前 root 同时是实施文件边界，所有任务仅适用于 D:/projects/RvPort/tools/memory-order-analyzer/。旧清单 41 项中涉及前后端的实现/验收已移出，不作为完成项。旧 31/41 进度不再适用于收紧后的清单。
>
> 以前已完成的后端修改及仓库级验证仅保留在 implementation-notes.md 的历史记录中，用户接受本次既有修改，不授权继续跨 root 操作。前端未实施内容见 frontend-handoff.md，由前端自己的 root 管理；不是本 change 的未完成任务。

## 1. 范围与基线

- [x] 1.1 在配置、proposal、design、四份 delta specs 和任务中统一当前 root 文件边界；移除外部消费能力及跨目录实施要求。
- [x] 1.2 保留普通循环负例、原子/线程/同步正例及 5 TU/2 Scope 混合证据夹具，不纳入真实运行数据。
- [x] 1.3 完成本工具 Docker 基线：854 Python、118 C++ 单元及整体/语言/模块覆盖门槛；记录与最终验收的区别。

## 2. 统一编排与协议

- [x] 2.1 使用真实 validator 回归 TU/artifact 反序、重复同值/冲突，按协议规范化 AST/LLVM/R3 身份与排序。
- [x] 2.2 发布分析使用显式 P3 引用，覆盖 thread-entry 共存、多轮次、缺失和越界引用。
- [x] 2.3 调用前检查空成员、缺 EffectSummary/root plan/overlay 及双空 source/LLVM；局部失败不清空独立结果。
- [x] 2.4 保持 compiler-default、legacy、C++17/C++20 策略/schema 一致，按标准隔离输入和失败。
- [x] 2.5 严格匹配 thread/RAII profile，覆盖零/多匹配、standard/vendor/target/DataLayout/ABI 和未知 vendor。
- [x] 2.6 区分不适用与未知，传播 ModuleFacts partial、优化证据丢失与输入缺口，不按产物存在判定完整。

## 3. 候选与投影

- [x] 3.1 保留原始事实并实施候选准入与审计，普通读写/循环不误投影，AST-only 同步线索保留。
- [x] 3.2 按 Scope/TU/profile、形状、节点/关系身份去重，保留 occurrences 及 raw/admitted/excluded 分母。
- [x] 3.3 生成并校验 3.0 的 evidenceLevel/nullable confidence，保留 2.0 校验，拒绝未知/混合版本。
- [x] 3.4 生成具体双语说明及适用缺口，覆盖缺符号/位置和非原子同步；维持 primaryPath/edges/breaks 引用合同。
- [x] 3.5 更新顶层版本、结果策略及缓存身份，覆盖旧缓存隔离、冷/热一致与 transient 不复用。

## 4. 诊断与并发制品

- [x] 4.1 汇总各阶段诊断/frontier，保留跨 Scope/TU 身份、受阻阶段及截断前分母，完整诊断纳入审计制品。
- [x] 4.2 索引和缓存只读取已发布产物；覆盖嵌套任务目录、原子写入临时文件与跨 Scope 并发回归。

## 5. 工具质量验收

- [x] 5.1 在 Docker 中执行实际协议组合单元，不 mock 被验证合同。
- [x] 5.2 使用真实 worker 和独立预生成 BC 验证混合证据、跨 TU/Scope 隔离、源码上下文与冷/热一致。
- [x] 5.3 quality-005 全量通过：884 Python 单元、118 C++ 单元、98 集成；整体/语言/逐模块行及可用分支均至少 90%，集成不混入单元覆盖。
- [x] 5.4 保留源码/镜像摘要、精确命令、covered/total、未加载源码及排除理由；工具统计独立于后端，不宣称整个仓库覆盖率。

## 6. 文档与阶段交接

- [x] 6.1 更新工具协议文档与非规范性前端交接，明确历史后端例外不产生未来跨 root 授权。
- [x] 6.2 核对 artifact 范围、内容、链接及 OpenSpec 严格校验；保留真实历史记录，不自动同步或归档。