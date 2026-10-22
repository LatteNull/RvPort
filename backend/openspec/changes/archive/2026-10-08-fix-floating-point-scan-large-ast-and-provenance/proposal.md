## Why

`demo-test1` 的真实浮点精度扫描表明，常见 C++ 标准库头文件会使 Clang AST JSON 达到 94 MiB 至 230 MiB，当前扫描器却按 16 MiB 截断 stdout 后继续解析，最终将可诊断的输出预算问题误报为 `frontend_invalid_json`，并由后端进一步掩盖为下游 `source_fact_bundle_missing`。临时放宽输出上限后，扫描又因 Finding 携带过量标准库 source facts 导致 provenance 不符合结果 Schema，因此必须同时修复大 AST 处理、项目源码事实收敛、结果协议和失败诊断闭环。

## What Changes

- 调整浮点扫描器的 Clang AST 获取方式，使大输出能够通过受预算约束的文件或流式路径处理，不再先截断字符串后尝试 JSON 解析。
- 当 AST 输出确实超过配置预算时，返回稳定、明确且包含翻译单元身份的输出超限诊断，不再误报 JSON 损坏。
- 将 source facts、evidence 和 Finding provenance 收敛到项目源码及与具体结论直接相关的事实，过滤标准库和系统头文件造成的无关事实膨胀，并对 provenance 去重、排序和施加协议边界。
- 修正浮点结果生成与 Schema 校验的一致性，保证合法扫描不会因 provenance 数量或结构失控转为 `internal_error`。
- 后端在浮点扫描失败时保存可审计的原始结果 JSON，并按因果优先级向任务错误和运行摘要暴露上游诊断，避免仅显示 `source_fact_bundle_missing` 等派生错误。
- 对明确标记为不可重试的扫描协议、输入或预算错误停止无效自动重试；可重试的瞬时错误继续沿用任务重试策略。
- 增加覆盖正常、异常和边界流程的独立单元测试，并验证项目整体及受影响模块行覆盖率和可用分支覆盖率至少为 90%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `floating-point-analysis-runtime`: 修改浮点扫描器对大 Clang AST、项目源码 facts/provenance、失败制品、根因诊断和重试分类的要求。

## Impact

- 受影响组件包括 `tools/floating-point-precision-scanner` 的 Clang frontend、facts/evidence/result 生成与 Schema 校验，以及后端专项分析 request adapter、运行时结果校验、制品持久化和任务失败分类。
- 浮点分析请求预算将增加明确的 frontend 输出约束；协议兼容范围内不会改变现有 API 路径，但失败响应和运行摘要会返回更准确的原因码与诊断。
- 失败运行将新增或完善原始结果制品留存，可能增加少量对象存储占用；不得保存服务器绝对路径、环境变量或凭据。
- 不修改共享 LLVM BC v2 生产协议；本次问题发生在浮点消费者现场生成源码 facts 和结果聚合阶段。
