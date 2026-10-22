## 1. Agent 输出契约

- [x] 1.1 修改测试比较 prompt，要求 agent 写出 `comparison-result.json`，并避免组合枚举和 `...` 示例值。
- [x] 1.2 修改 agent runtime 调用后的结果读取逻辑，优先读取 workspace 中的 `comparison-result.json`。
- [x] 1.3 增加 stdout fenced JSON 或最后完整 JSON 的兼容降级逻辑，并禁止从 `mergedOutput` 作为正常解析来源。
- [x] 1.4 扩展 agent 输出 artifact 内容，保存 `stdout`、`stderr`、`mergedOutput`、结果文件内容和解析来源。

## 2. 结果校验和失败处理

- [x] 2.1 增加测试比较结果结构校验，校验顶层字段、source/target 统计字段和 findings 字段。
- [x] 2.2 增加语义校验，拒绝组合枚举字符串、占位符 `...`、空模板内容和非法置信度。
- [x] 2.3 修改失败处理，agent 输出无效时将比较运行标记为 `FAILED`，并保存受控错误码与原始诊断 artifact。
- [x] 2.4 确认比较失败不会修改 x86/riscv 自动化测试记录自身状态和日志引用。

## 3. 测试覆盖

- [x] 3.1 增加单元测试覆盖合法 `comparison-result.json` 输出解析。
- [x] 3.2 增加单元测试覆盖缺失结果文件、stdout 降级解析、占位符输出拒绝和组合枚举拒绝。
- [x] 3.3 增加 handler 或 service 测试，验证无效 agent 输出会落库为比较失败。
- [x] 3.4 更新 E2E 模块，覆盖 x86 成功、target 失败后自动触发比较，以及无效 agent 输出不被保存为成功。

## 4. 验证

- [x] 4.1 运行相关单元测试。
- [x] 4.2 重建后端容器并确认服务健康。
- [x] 4.3 使用 `test2` 或等价 fixture 运行真实自动化测试比较，确认比较结果不再保存 schema 占位符。
- [x] 4.4 运行对应 E2E 模块并记录结果。
