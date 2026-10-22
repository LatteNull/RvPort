## Why

浮点扫描的证据链步骤只有类型、状态及引用，没有可读标题和判断说明，导致前端显示“未提供步骤标题/判断说明”。KB 的步骤已有这些展示信息，需要从浮点工具输出协议与生成端补齐，而非由前端或后端猜测证据含义。

## What Changes

- 为浮点 `evidenceChain.steps[]` 增加非空双语 `title/titleEn/reason/reasonEn`，覆盖源码、IR、绑定、profile、构建上下文、编译选项、assessment 和 conclusion 等已有步骤类型。
- 根据被引用的实际证据生成逐步说明，不以统一类型标签或重复结论冒充证据解释；缺失或不可解释的引用明确保留限制。
- 同步工具 v2 Schema、生成与校验、spec/docs 和测试；后端验证原始结果、入库 detail 及现有详情 API 的字段完整性，不新增获取接口。
- 保留历史不可变结果，不回填旧扫描；新扫描生成新字段，不改变风险规则、Finding 身份和现有权限模型。
- 在 Linux Docker 验证正常、异常及边界独立单测，整体与受影响模块行/分支覆盖率均至少 90%，补充真实扫描 API 验证。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-analysis-runtime`：浮点证据链步骤必须包含有证据依据的双语说明，并贯通既有制品及详情接口。

## Impact

- 后端：专项分析结果导入/响应的契约回归测试，必要时最小修复映射，不修改前端、数据库结构或 API 路径。
- 工具：申请将 `tools/floating-point-precision-scanner` 作为本 change 特别允许范围；实施前需明确授权。同步该工具的 `scanner-io-contract` 等实际受影响主规范及中文设计文档。
- 扩展本工具 v2 步骤字段，不修改 KB 或内存序工具协议；新输出需与新版 Schema 一起发布，旧的严格 Schema 无法校验新增字段。
- 复用现有报告制品及归档登记，不新增节点、报告类型、外部服务或 AI 调用。
