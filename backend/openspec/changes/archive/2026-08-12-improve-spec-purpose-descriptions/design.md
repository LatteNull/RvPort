## Context

`openspec validate --specs --strict` 当前有 5 个主 spec 因 `Purpose section is too brief` 失败。相关 spec 的 requirements 和 scenarios 结构有效，问题集中在能力目的说明过短，导致全量严格校验长期带有已知噪声。

## Goals / Non-Goals

**Goals:**
- 扩展 5 个主 spec 的 `## Purpose` 文本，使其明确描述能力边界并满足严格校验长度要求。
- 保持 requirements 和 scenarios 的现有语义不变。
- 保证修改后 `openspec validate --specs --strict` 不再因为这些 Purpose warning 失败。

**Non-Goals:**
- 不改变后端 API、数据库 schema、worker、测试或运行时行为。
- 不重写现有 requirements。
- 不处理与 Purpose 长度无关的 OpenSpec 文档质量问题。

## Decisions

- 使用最小文档修复方式，只替换目标 spec 的 `Purpose` 段落。
- Purpose 内容使用中文，说明能力边界、输入输出、运行位置和安全约束，避免只写一句泛化描述。
- 每个受影响 capability 增加一条 delta requirement，要求主 spec 的 Purpose 保持足够明确，便于后续 archive/sync 时有可追踪的变更依据。

## Risks / Trade-offs

- [Risk] delta spec 不能直接表达 `Purpose` 的文本替换。  
  Mitigation: 在任务中明确主 spec 的 Purpose 修改范围，archive 前人工同步主 spec。

- [Risk] 过度扩展 Purpose 可能和 requirements 重复。  
  Mitigation: Purpose 只描述边界和目标，不复制场景细节。
