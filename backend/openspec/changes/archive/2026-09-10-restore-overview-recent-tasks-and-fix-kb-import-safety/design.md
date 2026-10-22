## Context

当前项目 overview 只返回 `project`、`currentContext`、`workflow` 和 `latestTaskEventId`。原有 `recentTasks` 在 overview 重构时被删除，但前端仍需要最近任务作为项目首页的重要信息。现有 `TaskRepository.list` 已按 `created_at DESC, id DESC` 稳定分页，可直接复用。

KB Scanner schema v2 会生成 JSON、HTML 和日志制品。后端导入成功后先将扫描标记为成功，再登记归档候选；归档候选当前使用包含 `path` 的宽泛字段名正则，导致合法的 `scope.paths` 被拒绝。异常随后被 KB 运行时统一捕获并将扫描改写为失败，使 Scanner 成功与后处理失败无法区分。

此外，当前实现会将整个 JSON 文件作为普通文本执行通用路径正则替换。该正则无法区分服务器绝对路径与源码文本，可能错误修改 `#include "../..."`、诊断文本和代码上下文，并破坏 JSON 转义或结构。

## Goals / Non-Goals

**Goals:**

- 恢复 overview 最近 5 条任务的稳定响应契约。
- 允许归档摘要保存合法路径字段和安全相对路径，同时继续拒绝敏感信息、服务器绝对路径和目录穿越。
- 保证 KB JSON 制品脱敏后仍可被 JSON parser 读取，并保持源码证据文本不变。
- 区分 Scanner/导入成功与归档候选登记失败，避免将后处理异常误报为 Scanner 失败。
- 使用正常流程、异常流程和 edge case 测试锁定行为。

**Non-Goals:**

- 不修改 KB Scanner schema v2 或 Scanner 输出字段。
- 不新增数据库表或迁移脚本。
- 不修复、重写或删除历史失败任务和历史制品。
- 不改变项目级 SSE、任务重试和归档包生成的整体架构。

## Decisions

### 1. 在现有 overview 响应中恢复最近任务

`ProjectOverviewResponse` 增加非空 `recentTasks` 列表。`ProjectService` 在项目权限校验通过后调用现有任务仓储，读取第一页 5 条记录并映射为 `TaskResponse`。该字段与现有 `currentContext`、`workflow`、`latestTaskEventId` 并列，不恢复已经废弃的领域空摘要和推荐动作字段。

选择复用 `TaskRepository.list`，因为其已经提供稳定的倒序分页语义。相比新增专用 SQL，这可以避免产生两套最近任务排序规则。

### 2. 将归档安全检查拆分为字段语义和字段值检查

字段名拒绝规则仅针对明确承载秘密或内部对象存储位置的键，例如密码、私钥、口令、secret、token、object key 和 bucket。`path`、`paths`、`filePath` 等字段名不单独构成违规。

所有字符串值仍递归接受安全检查：服务器绝对路径、目录穿越、秘密文本和对象存储内部位置继续被拒绝。安全的项目相对路径、文件名和空路径列表可以进入轻量摘要。

不采用单独放行 `paths` 的字段白名单，因为未来合法 schema 可能出现其他路径字段，白名单会不断制造同类误报；值驱动检查更接近真正的安全目标。

### 3. 按数据类型执行路径脱敏

KB `scan-result.json` 必须先由 Jackson 解析为 JSON tree，再递归处理并重新序列化。路径语义字段中的绝对路径按允许根目录替换为受控占位符，安全相对路径保持不变。普通源码文本、matched text、代码上下文和建议文本只替换已知源码根目录、KB 输出根目录及后端 runtime 根目录，不运行会吞掉相对 include 的通用路径正则。

HTML 和 scan log 属于非结构化制品，只替换已知运行根目录；任务 stdout/stderr 可以继续采用严格的日志脱敏，但不得复用该策略改写结构化 JSON。

写回 JSON 后立即重新解析一次，用作格式有效性保护。解析或序列化失败时，导入阶段以明确错误终止，且不保存损坏制品。

### 4. 归档登记是可诊断的后处理，不反转扫描成功事实

Scanner 返回成功、结果通过 schema 校验、findings 完成入库且制品保存成功后，KB 扫描可进入 `SUCCEEDED`。归档候选登记随后执行；若登记失败，后端记录脱敏 warning 和 tool run 后处理摘要，但不得将扫描改写为 `FAILED`，也不得让任务以 Scanner 失败重试完整扫描。

选择该边界是因为归档候选可由后续操作补偿，而重复运行数分钟的 Scanner 不能修复确定性的归档校验错误。Scanner、结果导入或制品保存本身失败时仍保持现有失败语义。

## Risks / Trade-offs

- [风险] 放宽路径字段名检查可能让真实服务器路径进入摘要 → 继续递归校验所有字符串值，并覆盖 Windows、Unix、目录穿越和嵌套集合测试。
- [风险] 仅替换已知根目录可能遗漏诊断文本中的其他绝对路径 → 对非源码日志保留严格脱敏；对结构化字段按字段语义处理，并在 API 输出边界继续执行安全检查。
- [风险] 归档登记失败后扫描成功但暂时不可归档 → 写入明确 warning 和后处理摘要，使问题可观测并允许后续重新登记，不牺牲扫描结果。
- [风险] overview 每次多一次任务查询 → 查询固定上限为 5 且复用现有索引排序，开销可控。

## Migration Plan

1. 先部署兼容性响应变更和归档安全校验修复。
2. 部署结构化 KB 制品脱敏及归档登记状态边界调整。
3. 运行 Java 测试和相关 API E2E，确认 overview、KB 扫描、制品下载与归档候选登记。
4. 对此前因该误判失败的 KB 扫描由用户重新发起；不修改历史记录。

## Open Questions

无。
