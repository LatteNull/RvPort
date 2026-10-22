## Why

当前构建验证接口的 `command` 字段返回的是脚本摘要，而前端需要使用该字段回填构建脚本编辑器。多行脚本会被摘要成 `set -eu # sha256:...`、shebang 或第一条清理命令，导致前端回填的内容不是当次真实构建脚本，并可能污染下一次构建提交。

## What Changes

- 调整构建验证详情和 latest 接口的返回语义，使前端可获取当次构建提交的完整脚本用于回填。
- 保留构建脚本摘要能力，避免列表展示和审计场景只能显示完整脚本。
- 不改变当前数据库存储模型：完整脚本继续保存在 `task_script_payloads`，hash 继续由后端计算并校验。
- 列表接口默认不返回完整脚本，避免批量查询暴露过多脚本内容和增加响应体积。
- 补充测试覆盖正常回填、无 payload/校验失败等异常流程，以及多行脚本第一行为 shebang 或 `set -eu` 的边界场景。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `build-validation-runtime`: 构建验证记录详情和 latest 查询需要返回可回填的完整构建脚本，并区分脚本摘要。

## Impact

- 影响后端构建验证 API DTO、Service 映射逻辑和相关测试。
- 影响接口契约：详情/latest 的 `command` 应可用于前端回填；摘要通过独立字段表达。
- 不新增数据库表或字段，不改变脚本加密存储与 SHA-256 校验机制。
