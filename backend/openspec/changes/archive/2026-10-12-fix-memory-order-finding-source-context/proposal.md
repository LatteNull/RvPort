## Why

内存序分析的正式 Finding 投影没有传递源码位置，源码候选又可能把头文件的行号关联到翻译单元主文件，导致已有详情接口无法返回可信代码片段。需要打通真实证据位置、源码快照和后端详情的链路，而不是新增取代码接口或伪造位置。

## What Changes

- 修复正式风险与已消解审计结果的位置投影，从实际关联证据解析源码位置，保留多位置关联及不可用原因。
- 修复源码候选的文件归属，明确头文件、宏 spelling/expansion、跨翻译单元及结束位置的边界，使用正确文件的可信快照。
- 沿用现有内存序 Finding 详情 API，随响应返回主位置的上下各 20 行代码、高亮及不可用原因；保留工具提供的逐位置上下文，不增加专用接口。
- 保持风险判断、候选/正式结论区分、权限和历史扫描不变，不修改前端。
- 同步工具自身规范和中文文档；补充独立单测、覆盖率门禁及真实编译器/API 验证。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `memory-order-analysis-runtime`：明确内存序结果位置与代码上下文的可信映射、详情返回及验证要求。

## Impact

- 运行时实现变更，不是纯文档变更。后端涉及 SpecializedAnalysisRuntimeService、SpecializedAnalysisService 及相关测试/文档。
- 工具涉及 unified_coordinator、finding_projection、source_context 和必要的证据解析；工具侧规范映射到 memory-order-finding-evidence-projection、unified-project-analysis-entry，实施时同步工具自己的 openspec/specs 和 doc。
- 提案保存在 backend/openspec，不在根目录另建 change。工具位于默认 backend 范围外，实施前需明确授权 tools/memory-order-analyzer 为本 change 的特别允许范围。
- 不新增数据库表、API 或外部服务，不改变其他工具。新结果修复位置及上下文，旧数据不自动回填；展示补齐不应无故改变 Finding 身份。
- 本地当前没有内存序 Finding 记录，已确认的是代码路径缺口，用户实际失败记录仍需在实施验证中核对。
