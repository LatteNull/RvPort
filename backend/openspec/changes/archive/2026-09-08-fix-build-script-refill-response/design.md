## Context

构建验证创建时，完整脚本已经通过 `task_script_payloads` 加密保存，`build_runs.script_payload_id` 和 `build_runs.script_sha256` 保存引用和完整性校验。当前 `build_runs.command` 只保存由第一条非空脚本行生成的摘要，例如 `set -eu # sha256:...`，但前端将 `BuildValidationResponse.command` 用作构建脚本编辑器回填内容，导致多行脚本被错误回填成摘要。

已有安全约束是：任务输入快照不能保存脚本明文，批量列表也不应无差别返回大量脚本正文。需要在不改表结构的前提下，把详情和 latest 的回填语义修正为完整脚本，同时保留摘要展示能力。

## Goals / Non-Goals

**Goals:**

- 构建详情接口返回完整构建脚本，供前端回填。
- 构建 latest 接口在 `freshness=CURRENT` 且存在 result 时返回完整构建脚本，供节点页面默认回填。
- 构建列表接口继续保持轻量，默认只返回摘要，不批量返回完整脚本。
- API 响应区分完整脚本和摘要，避免继续混淆 `command` 与 `commandSummary`。
- 复用现有加密 payload 和 SHA-256 校验，不新增数据库字段。

**Non-Goals:**

- 不修改构建脚本的加密存储方式。
- 不修改 worker 实际执行脚本的方式。
- 不处理历史记录中 payload 缺失或损坏的数据修复。
- 不修改前端代码；本 change 只提供后端契约。

## Decisions

### 详情/latest 解密脚本，列表不解密

`GET /api/builds/{buildId}` 和 `GET /api/projects/{projectId}/builds/latest` 面向单条记录或当前节点回填，后端可以在通过项目权限校验后调用 `TaskScriptPayloadService.requireScript(...)` 解密脚本，并将完整脚本放入响应。

`GET /api/projects/{projectId}/builds` 是列表接口，默认继续返回 `command` 摘要或空脚本回填字段，避免一次返回大量脚本文本。前端如需查看或回填某条历史记录，应请求详情接口。

### 响应字段兼容前端回填

为了让现有前端仍能读取 `command` 回填，详情/latest 的 `command` 返回完整脚本。新增 `commandSummary` 返回原 `build_runs.command` 摘要，供展示、审计和列表使用。

列表接口可以继续让 `command` 返回摘要以保持现有展示兼容，但必须同时返回 `commandSummary`，并在文档中明确列表的 `command` 不能作为脚本回填来源。后续前端应逐步改为详情/latest 用 `command` 回填，列表展示用 `commandSummary`。

### 解密失败按当前记录不可回填处理

如果详情/latest 记录的 `script_payload_id` 缺失、payload 不存在、无法解密或 hash 校验失败，后端不能静默返回摘要冒充完整脚本。应返回安全错误，错误信息不暴露脚本内容、密钥信息或服务器路径。这样可以阻止前端把错误摘要再次提交成构建脚本。

## Risks / Trade-offs

- [Risk] 同一个 DTO 在列表和详情中 `command` 语义不同，容易造成误用。→ 通过新增 `commandSummary` 并在规格中明确列表 `command` 不可作为回填来源；后续可进一步拆分列表 DTO 和详情 DTO。
- [Risk] latest 接口解密脚本会比原来稍重。→ latest 只返回单条记录，影响可控。
- [Risk] 历史数据 payload 损坏时详情无法返回。→ 明确失败，而不是返回摘要造成错误回填。
- [Risk] 完整脚本可能包含敏感构建变量。→ 仅在项目权限校验通过后返回；列表不批量返回完整脚本；环境变量仍按现有逻辑脱敏展示。
