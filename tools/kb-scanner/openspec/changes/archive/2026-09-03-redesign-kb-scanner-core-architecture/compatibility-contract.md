# KB Scanner 现有结果兼容契约

## 1. 权威基线

兼容判断以以下现有实现为准：

- Scanner 产出：`kb_scanner/report.py::to_json_payload`
- Scanner Finding 字段：`kb_scanner/models.py::Finding`
- 后端导入 DTO：`backend/.../kb/KbScannerResult.java`
- 后端导入流程：`backend/.../kb/runtime/KbScanRuntimeService.java`

本 change 不修改这些实现，只冻结后续重写必须遵守的外部行为。

## 2. 文件和版本契约

| 项目 | 必须保持 |
|---|---|
| 机器结果 | `scan-result.json` |
| 人类报告 | `scan-report.html` |
| 诊断日志 | `scan.log` |
| schemaVersion | 字符串 `1.0` |
| 主结果数量 | 只有现有 `scan-result.json`；不得增加替代主结果 |
| 后端 parser | 当前 `KbScannerResult` 无需切换或升级即可读取 |

后端会拒绝任何非 `1.0` 的 `schemaVersion`。三种 artifact 的文件名、用途和类型均不得改变。

## 3. scan-result.json 顶层字段

| 字段 | 类型 | 现有语义 | 兼容要求 |
|---|---|---|---|
| schemaVersion | string | 结果结构版本 | 固定为 `1.0` |
| tool | object | scanner 名称和版本 | 保留 `name`、`version` |
| rulePack | object | 规则包 ID 和版本 | 保留 `id`、`version`；新增知识来源只能是可选字段 |
| project | object | 项目根、扫描模式、目标架构和编译上下文 | 保持既有字段；只允许可选扩展 |
| summary | object | 文件、Finding、类型、阻断和 severity 统计 | 保持既有计数语义；readiness 作为可选子字段 |
| findings | array | 所有局部扫描结论 | 继续作为唯一局部问题集合 |
| diagnostics | string[] | 非 Finding 的扫描诊断 | 保持字符串数组，不改为对象数组 |

## 4. project 字段

| 字段 | 类型 | 语义 |
|---|---|---|
| root | string | 扫描项目根路径，进入后端前仍受路径脱敏约束 |
| scanMode | string | source_context、syntax_scan 等扫描模式 |
| targetArch | string | 本次静态分析目标，当前默认 riscv64 |
| includeInactiveBranches | boolean | 是否把 inactive/guarded 路径纳入审计输出 |
| compileCommands | string/null | compile_commands 输入位置或未提供 |
| compileContexts | object | 按源码记录 includeDirs、defines、languageStandard、entryIndex、compiler、tokenCount |

新架构可以在 `project` 下增加可选的覆盖或策略元数据，但现有字段不得改名、改类型或改变含义。

## 5. summary 字段

| 字段 | 类型 | 语义 |
|---|---|---|
| files | integer | 纳入扫描的文件数量 |
| findings | integer | Finding 总量 |
| issues | integer | 非 hint Finding 数量 |
| hints | integer | hint 数量 |
| blocking | integer | `is_blocking=true` 的数量 |
| portabilityGaps | integer | `finding_type=portability_gap` 数量 |
| inactiveOrGuarded | integer | inactive 与 guarded 数量 |
| referenceSources | integer | 作为引用源头的 issue 数量 |
| references | integer | 非引用源头的 issue 数量 |
| severity 动态键 | integer | 按当前 severity 字符串统计的数量 |

### 5.1 可选 summary.readiness

项目级 Assessment 使用现有 `summary` 下的可选字段，不创建新的顶层结构：

```json
{
  "readiness": {
    "state": "partial_riscv",
    "staticOnly": true,
    "dimensions": {
      "sourceReachability": "gap",
      "buildSelection": "unknown",
      "architectureDependencies": "gap",
      "alternativeImplementations": "partial",
      "testCoverage": "unknown",
      "inputCompleteness": "partial"
    },
    "blocking": 2,
    "gaps": 3,
    "unknown": 2
  }
}
```

最小字段集合固定为：

- `state`：项目静态 readiness 状态。
- `staticOnly`：固定为 true，避免被理解为真实编译结论。
- `dimensions`：六个维度到 `pass|gap|partial|unknown|not_applicable` 的映射。
- `blocking`、`gaps`、`unknown`：非负整数摘要。

`summary.readiness` 不内嵌完整证据链；详细证据继续由相关 Finding 的 `trace` 承载。旧消费者忽略该可选字段时，原有 summary 统计保持不变。

## 6. findings[] 字段清单

| 字段 | 类型 | 现有语义 |
|---|---|---|
| id | string | scanner Finding ID |
| rule_id | string | 稳定规则 ID |
| severity | string | 风险级别 |
| confidence | string | 结论置信度 |
| title / title_en | string | 中英文标题 |
| file | string | 命中文件 |
| line | integer | 起始行；后端最小按 1 处理 |
| column | integer/null | 可选列号 |
| symbol | string/null | 命中符号或 token |
| reason / reason_en | string | 中英文原因 |
| suggestion / suggestion_en | string | 中英文建议 |
| snippet | string | 代码或文本摘要 |
| scan_mode | string | 产生该 Finding 的扫描模式 |
| finding_type | string | issue、hint、guarded、inactive、portability_gap 等分类 |
| source_kind | string | code、comment、compile_command、rpm_spec 等来源 |
| is_actionable | boolean | 是否需要处理 |
| is_reference_source | boolean | 是否是同类问题的引用源头 |
| is_blocking | boolean | 是否阻断静态迁移就绪 |
| arch_reachability | string | 对目标 RISC-V 的静态可达性 |
| branch_group_id | string/null | 条件分支组 ID |
| branch_role | string/null | x86/riscv/generic/fallback/unknown 分支角色 |
| compatible_sibling_branch | boolean | 是否存在兼容兄弟分支 |
| compatible_branch_kind | string/null | 兼容兄弟分支类型 |
| build_context | object | compile_commands 或静态构建上下文 |
| alternative_impl | object | 替代实现信息 |
| condition_macros | string[] | 条件栈中的宏名 |
| trace | object | 可扩展、可追溯的证据链 |
| location | object | file、line、column 的兼容定位对象 |
| context | object | 当前包含 snippet 的兼容上下文对象 |

不得删除、重命名、改变类型或重新解释上述字段。新的局部分析仍必须表现为现有 Finding。

## 7. 后端实际导入边界

- `KbScannerResult` 和内部 `Finding` 使用 `ignoreUnknown=true`，因此可选未知字段不会导致 JSON 解析失败。
- 后端会硬校验 `schemaVersion == "1.0"`。
- 顶层 `summary` 会以 Map 保存，适合承载可选 `readiness`。
- 当前后端 evidence 映射能够可靠保留 `trace`，因此新关系证据优先写入 `trace`。
- Scanner 当前输出 `build_context`、`alternative_impl`、`condition_macros` 为 snake_case，而后端 DTO 对对应 camelCase 字段没有显式映射；本设计不在本 change 修复该差异，也不依赖这些字段承载必须入库的新信息。
- `location`、`context` 以及未被 evidence 映射使用的字段仍保留在原始 artifact 中，不应被新设计移除。

## 8. 内部模型兼容投影矩阵

| 内部概念 | 现有输出位置 | 投影规则 |
|---|---|---|
| Fact / Evidence | Finding 的 file、line、column、symbol、snippet、source_kind、confidence | 选择支撑结论的主要证据；其他证据引用放入 trace |
| Relation | `findings[].trace` | 记录 relation type、端点的稳定摘要、推导路径和不确定性 |
| Observation | 不单独输出 | 未升级时可成为 hint；升级后由 Finding 表达 |
| Finding | `findings[]` | 保持现有字段和分类机制 |
| Assessment | `summary.readiness` | 只放静态状态、维度和计数，不复制完整 Finding |
| Coverage / incomplete input | `project` 可选字段、`summary.readiness.dimensions.inputCompleteness`、diagnostics | 可查询摘要进入 project/summary，解释文本进入 diagnostics |
| Knowledge provenance | rulePack 可选字段或 Finding trace | 不改变 rulePack 既有 id/version |

## 9. 兼容性验收标准

后续每个实现 change 必须同时满足：

1. `schemaVersion` 仍为字符串 `1.0`。
2. 三个现有输出文件继续生成且用途不变。
3. 七个顶层字段继续存在，既有字段的名称、类型和语义不变。
4. 当前 41 个 scanner 测试继续通过，并为新增能力补充 fixture。
5. Clang/GCC 两份事实数据和 `generatedSet` 测试继续通过。
6. 当前后端 `KbScannerResult` 可以直接反序列化结果。
7. 当前后端 `KbScanRuntimeService` 能导入 findings 和 summary，无需切换 parser。
8. 新增可选字段被旧消费者忽略时，不影响现有 Finding 数量、summary 统计和 artifact 保存。
9. 任何不能安全投影的新内部信息先留在内部或 diagnostics，不得推动创建新的主结果结构。
