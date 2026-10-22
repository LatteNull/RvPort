## Why

现有 schema 1.0 为兼容旧消费者，把 Evidence、Relation、ProofPath、occurrence 和完整性状态压入自由形态的 `Finding.trace`，能够保留数据，却无法为“点击 Finding 后查看从构建选择、源码证据、知识事实到最终判断的完整链路”提供稳定、可验证的合同。现在证据闭包与 reachability 已经具备，适合先设计 schema v2，把 Finding 从扁平报告项提升为可解释结论，同时给后续后端与前端实现提供唯一目标。

## What Changes

- **BREAKING** 设计 `schemaVersion: "2.0"` 的 Finding-centric 结果合同，不再依赖无约束 `trace`，也不要求消费者到顶层全局 Catalog 拼装 Finding 详情。
- 每个 Finding SHALL 自包含 `fact`、`conclusion`、`occurrences[]` 和 `evidenceChain`；`evidenceChain` 直接携带完整 `steps[]`、`edges[]`、`primaryPath[]` 和 `breaks[]`，使单个 Finding 可以独立展示和审计。
- 每个有源码或构建文件依据的 fact、occurrence 和 chain step SHALL 携带项目相对路径、精确 start/end 行列、逐行代码上下文、真实行号和命中高亮范围；knowledge、Classification 和 Assessment step 则展示来源、判断理由和状态，不伪造代码位置。
- 前端列表 MAY 使用 Finding 摘要投影，但 Finding 详情接口 SHALL 可一次返回完整 Finding，无需额外查询 Explanation、Catalog 或 scanner 内部 snapshot。
- 链路 SHALL 同时支持默认展示的确定性主路径和宏候选、替代实现、歧义关系等分支，并表达 `complete`、`partial`、`ambiguous`、`inactive`、`unknown` 及断点原因。
- 设计 Finding 内引用完整性、类型约束、稳定 ID、排序、预算截断、循环、缺失引用和确定性序列化规则，使离线 artifact 中的每个 Finding 也能独立还原自身证明链。
- 设计 schema 1.0 与 2.0 的迁移和共存策略：同一次 scan 只产生一个被请求版本的 `scan-result.json`，artifact 名称保持不变；迁移期继续支持 v1 兼容投影，禁止把 v2 信息再次塞入新的自由形态字段。
- 固化静态分析边界：v2 只能表达 scanner 已取得的静态 proof，不得暗示真实编译、链接或测试已经执行；操作系统、内核、驱动和板级迁移不进入该 schema。
- 保留 Clang/GCC 两份 compiler-derived x86 事实数据及其现有分类和 provenance，不在本设计 change 中转换知识数据格式。
- 本 change 仅交付 schema、示例、迁移矩阵和验证计划，不修改 scanner 运行时代码或前端；后续实现 change 必须为每个新增/修改业务模块提供独立容器单元测试映射和覆盖率门禁。

### v2 Finding 目标形态

```text
findings[]
├─ fact
│  ├─ kind / symbol / matchedText
│  └─ primaryLocation
│     ├─ file / start / end
│     └─ context.lines[] / highlights[]
├─ conclusion
├─ occurrences[]
│  └─ location / context / configuration / selectionStatus
└─ evidenceChain
   ├─ status / reasonCodes
   ├─ primaryPath[]
   ├─ steps[]
   │  └─ kind / status / source context / provenance / reason
   ├─ edges[]
   └─ breaks[]
```

页面默认沿 `primaryPath` 展示“构建选择 → 源码或宏命中 → x86 knowledge → Classification → Assessment”；用户展开时直接读取同一个 `evidenceChain` 中的其他 step、edge、occurrence 和断点。每个代码型 step 自带命中行及前后文，不需要前端重新读取源码。

代码型 fact、occurrence 或 step 的位置采用同一结构，例如：

```json
{
  "file": "src/vector.c",
  "span": {
    "start": { "line": 42, "column": 12 },
    "end": { "line": 42, "column": 27 }
  },
  "context": {
    "lines": [
      { "line": 41, "text": "..." },
      { "line": 42, "text": "result = _mm256_add_ps(a, b);" },
      { "line": 43, "text": "..." }
    ],
    "highlights": [
      { "line": 42, "startColumn": 12, "endColumn": 27 }
    ]
  }
}
```

## Capabilities

### New Capabilities

- `kb-scanner-report-schema-v2`: 定义 Finding 自包含的 fact、conclusion、occurrence、代码上下文和 evidenceChain 子图，以及完整性状态、确定性序列化、静态范围声明、JSON Schema、示例和消费者合同。

### Modified Capabilities

- `kb-scanner-compatible-projection-and-cutover`: 将“只能输出 schema 1.0”的固定合同扩展为明确的 v1/v2 版本选择与迁移合同；迁移期保留 v1 兼容投影和既有 artifact 名称，同时禁止一次扫描产生两套主结果。

## Impact

- 当前 change 只影响 `tools/kb-scanner` 内的 OpenSpec、schema 设计文档、合同示例和验证资产，不改变默认 CLI、后端消费或现有结果。
- 后续实现预计影响 projection contract/mapper、source-context projector、evidence-chain builder、serializer、JSON/HTML/log renderer、CLI 输出版本选择、后端摘要/详情接口和 Finding 详情前端。
- v2 artifact 会因每个 Finding 自包含链路和代码上下文而增大；列表接口不直接返回完整 `findings[]`，详情接口按 Finding 返回，代码上下文采用有界行窗口，底层可按稳定 ID 缓存重复步骤。
- schema 2.0 对直接解析 v1 顶层 Finding/字符串 diagnostics 的消费者是破坏性升级，因此必须有显式版本选择、v1/v2 合同差异清单和独立 consumer contract；这份清单只指导消费者迁移，不是运行时转换链。
- 不新增运行时第三方依赖，不改生产镜像或根 Compose；所有未来实现与测试仍只通过独立 `kb-scanner-test` 容器完成。
