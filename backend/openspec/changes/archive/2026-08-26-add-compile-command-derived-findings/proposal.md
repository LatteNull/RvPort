## Why

当前 KB Scanner 只把 `compile_commands.json` 作为构建上下文增强输入，用于 include 路径、宏定义和构建可达性摘要，但不会把编译命令中出现的 x86 专属参数或宏转换为 finding。这样会漏掉只存在于真实构建命令中的迁移风险，例如 `-mavx2`、`-msse4.2`、`-march=x86-64` 或 `-D__AVX__`。

## What Changes

- 从 `compile_commands.json` 的 `command` 或 `arguments` 中提取编译参数、宏定义、语言标准和编译器信息。
- 对 x86 专属编译参数生成 KB finding，来源标记为 compile command。
- 对命令行宏中明确启用 x86/SIMD 路径的项生成 KB finding 或 evidence。
- 保持默认扫描不因 compile database 存在而减少 finding；compile database 只能补充上下文或新增构建命令层面的 finding。
- 在 API/E2E 中覆盖“源码无明显风险但 compile command 有 x86 参数”的真实/fixture 流程。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scan-runtime`: KB 扫描需要把 compile database 中的编译命令风险转换为 finding，并保持现有源码 finding 不被默认过滤。
- `api-e2e-test-suite`: E2E 需要覆盖 compile database 派生 finding 的正常流程、异常流程和 edge case。

## Impact

- 影响 `tools/kb-scanner` 的 compile command 解析、规则匹配和报告输出。
- 影响 KB 扫描运行结果、finding evidence 和 migration input 生成。
- 影响 KB scan 相关单元测试和 E2E fixture。
- 不新增前端提交参数，不改变 `POST /api/projects/{projectId}/kb-scans` 请求结构。
