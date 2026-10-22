## Context

当前后端已经具备三块可复用基础能力：

- KB 扫描通过独立 `tools/kb-scanner` CLI 运行，结果按 finding 逐条写入 `findings` 表，并提供 finding 列表、详情、代码上下文和 artifact 下载接口。
- agent runtime 已支持 `CODEX`、`DEEPSEEK_HARNESS`、`OPENCODE` 等统一 adapter，可在受控 workspace 中执行模型任务，并保存 stdout、stderr、`mergedOutput` 和退出状态。
- 模型 profile 与阶段绑定当前只允许 `TEST_LOG_COMPARE`，测试比较阶段已经形成了“写输入文件 -> 调 agent -> 读结构化输出文件 -> 入库”的实现范式。

本 change 要把这套范式扩展到知识库扫描：KB scanner 仍负责静态规则发现，AI 扩展扫描只负责对已有 finding 生成更具体的解释、修复建议和置信度。前端展示时不需要单独拉 AI result，而是在 KB finding 列表和详情中直接看到当条最新 AI 建议。

## Goals / Non-Goals

**Goals:**

- 新增 `KB_AI_EXTENSION` 异步任务类型，用于对一次已完成 KB 扫描的 findings 执行 AI 扩展。
- 新增 `KB_AI_EXTENSION` 模型阶段绑定，使管理员可以为该节点选择 agent runtime 和模型 profile。
- 将当前 KB scan 的 findings 导出为 agent 可稳定读取的 workspace 文件；当 finding 自带信息不足时，允许 agent 读取当前源码版本的源码补充判断。
- 将 AI 扩展结果逐条入库，并在 KB finding 列表和详情中直接返回最新成功扩展建议。
- 保存 AI 输入、输出和 agent 执行摘要为 artifact，便于审计和故障排查。
- 沿用项目权限校验、路径安全、敏感信息脱敏、任务日志、SSE、取消和测试约束。

**Non-Goals:**

- 不修改 KB Scanner CLI 的主输出文件契约，不改变 `scan-result.json`、`scan-report.html` 或 scanner 规则输出结构。
- 不让 AI 扩展创建新的 finding，也不自动修改 finding 是否进入报告。
- 不实现 AI 自动修复源码，不允许 agent 修改源码工作副本。
- 不要求前端单独展示 AI result 列表作为主流程；单独运行记录接口仅用于历史、审计和调试。
- 不在业务请求中直接提交模型 base URL、API key、agent 类型或任意 agent 命令。

## Decisions

### Decision: 将 AI 扩展建模为 KB finding 的派生增强

AI 扩展结果使用独立运行表和逐条结果表保存，但业务展示挂在原 finding 上。这样 finding 仍是代码问题的主实体，AI 内容只是补充说明，不会产生第二套问题列表。

替代方案是提供独立 AI result 查询页面。这个方案会让前端在 KB 扫描页面额外联动两套列表，也容易出现 finding 与 AI result 状态不一致。当前产品形态是“知识库扫描上的按钮”，因此直接扩展 finding 响应更清晰。

### Decision: 使用独立阶段 `KB_AI_EXTENSION`

模型和 agent runtime 通过现有阶段绑定机制解析，但必须新增 `KB_AI_EXTENSION`，不能复用 `TEST_LOG_COMPARE`。测试比较和 KB AI 扩展的 prompt、输出 schema、稳定性要求不同，共用阶段会导致管理员无法独立调整模型。

阶段未配置、profile 禁用、runtime 禁用或模型参数不完整时，启动接口返回明确业务错误，不创建任务。这样避免队列中出现必然失败的任务。

### Decision: 输入输出通过 workspace 文件传递

后端为每次 AI 扩展创建专用 workspace：

```text
workspace/
  input/
    manifest.json
    findings-0001.jsonl
    findings-0002.jsonl
  source/
    ... 当前源码版本只读副本 ...
  output/
    summary.json
    results-0001.jsonl
    results-0002.jsonl
```

`manifest.json` 描述项目、源码版本、KB scan、finding 总数、分片文件和输出 schema。`findings-*.jsonl` 每行一个 finding，包含 rule、severity、title、description、原始 suggestion、evidence 安全摘要、相对路径、行号和固定 20 行上下文。agent 必须把结果写入 `output/results-*.jsonl`，每行一条 AI 建议，并用 `findingId` 回指原 finding。

相比把 findings 直接塞进 prompt，文件方式更适合较大扫描结果，也方便保存和审计。

### Decision: 支持源码读取但限制写入

agent prompt SHALL 明确说明：优先基于 finding 输入判断；如果当前信息不足，可以读取 `source/` 下当前源码版本文件和相关上下文；不得修改源码、不得删除输入文件、不得生成源码补丁。

实现上应尽量使用临时只读源码副本或在任务结束后校验源码工作副本未被修改。prompt 不是安全边界，后端需要通过 workspace 隔离和路径安全降低误改风险。

### Decision: 输出必须可校验并允许部分结果入库

后端解析输出时应校验：

- 输出 JSONL 每行都是对象。
- 每条结果包含合法 `findingId`。
- `findingId` 必须属于本次 KB scan。
- 枚举值、置信度、文本长度和 raw payload 大小满足后端约束。
- 对合法且可追溯的结果允许先逐条入库。
- 对缺失 finding、重复 finding、未知 finding ID 或单条 schema 非法的情况，运行 summary 必须记录缺失、重复、未知和非法数量，并将运行标记为部分成功或带诊断的成功状态。

允许部分结果入库可以避免单条输出异常导致整批 AI 建议不可用，但必须保证写入的数据都能追溯到本次 KB scan 的真实 finding。不可追溯的输出不得入库。

### Decision: finding 响应返回最新成功 AI 扩展

`GET /api/kb-scans/{scanId}/findings` 和 `GET /api/findings/{findingId}` 应左连接或批量查询同一 scan 下最新成功 AI 扩展结果，返回 `aiExtension` 字段。无结果时返回 `null`。

运行记录接口仍然保留，用于查看某次 AI 扩展任务状态、下载输入输出 artifact、排查 agent 失败原因。

### Decision: 报告只引用已确认 finding，可附带 AI 建议

AI 扩展不改变 migration input reference 的确认状态。评估报告生成时，如果已确认的 KB finding 存在当前 scan 的最新 AI 扩展建议，可以在报告建议中引用该 AI 内容；没有 AI 扩展时继续使用原始 KB suggestion。

### Decision: AI 扩展制品必须登记归档候选

AI 扩展的输入文件、结构化输出文件和 agent 执行摘要是后续报告、审计和复核的重要输入之一。任务完成后必须登记归档候选，归档当前状态时应能打包这些制品；如果某阶段没有运行或没有成功生成制品，则归档中不显示对应内容。

## Risks / Trade-offs

- [Risk] agent 输出不稳定或遗漏 finding → 使用 JSONL schema、逐条校验、部分成功诊断、任务日志和 artifact 留痕。
- [Risk] finding 数量过多导致单次 agent 处理超时 → 设计上支持输入分片；实现可先设置合理批大小，再根据真实 E2E 调整。
- [Risk] agent 读取源码时误改文件 → 使用临时源码副本或任务结束校验，且 prompt 明确只读。
- [Risk] AI 建议与原始规则建议冲突 → 原 finding 保持主事实，AI 建议作为独立 `aiExtension` 字段展示，不覆盖原字段。
- [Risk] 阶段未配置导致用户点击失败 → 提供 readiness 接口，并在启动接口返回明确业务错误。
- [Risk] 输出 artifact 可能包含路径或敏感信息 → 保存前执行路径脱敏和 provider secret 脱敏，API 不返回服务器真实路径。

## Migration Plan

1. 新增 Liquibase 迁移：创建 AI 扩展 run/result 表，扩展 artifact owner 和阶段绑定可用枚举/约束。
2. 重新生成 jOOQ 代码，确保生成代码提交到源码目录。
3. 新增 `KB_AI_EXTENSION` task type、handler、runtime service、repository、response DTO 和 controller。
4. 扩展 KB finding 查询，将最新成功 AI 扩展结果附加为 `aiExtension`。
5. 扩展模型阶段绑定和 agent runtime 受控阶段白名单。
6. 增加单元测试和 E2E 模块，验证正常流程、异常流程和 edge case。

回滚时可以禁用 `KB_AI_EXTENSION` 阶段绑定和启动接口。已保存 AI 扩展表与 artifact 可保留为历史数据，不影响原 KB scan 主流程。

## Open Questions

- 暂无。
