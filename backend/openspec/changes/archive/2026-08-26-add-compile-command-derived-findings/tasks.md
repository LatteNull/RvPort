## 1. Scanner Compile Command 解析

- [x] 1.1 扩展 compile database 解析模型，保留每个 entry 的相对源码文件、entry index、compiler、token 列表和来源字段。
- [x] 1.2 支持优先解析 `arguments` 数组，并在只有 `command` 字符串时使用 shell-like token 解析。
- [x] 1.3 对解析失败、缺失 file、越界 file、排除路径和构建系统内部探测 entry 输出 diagnostics warning，并继续处理其他 entry。

## 2. Finding 生成和 Evidence

- [x] 2.1 增加 compile command 派生候选逻辑，识别明确 x86/SIMD 编译参数和命令行宏。
- [x] 2.2 将 compile command 候选映射为稳定 KB finding，包含 rule id、severity、title、description、suggestion 和 fingerprint。
- [x] 2.3 在 evidence 中写入 `sourceKind=compile_command`、命中 token、token 类型、compile command index 和源码相对路径。
- [x] 2.4 实现同来源内去重，避免相同 `sourceKind + ruleId + relativePath + token` 重复写入。
- [x] 2.5 确认 compile database 只补充 finding，不减少源码扫描默认 finding。
- [x] 2.6 实现构建参数风险跨来源去重：源码或构建文件已扫描出同一 token 时，不新增 compile command 展示 finding，只合并 compile command evidence。

## 3. 后端导入和安全边界

- [x] 3.1 确认 KB scan worker 继续按同项目、同源码版本下载并传入最新可用 compile database。
- [x] 3.2 确认 findings 导入链路可保存 compile command evidence，并不破坏现有列表、详情、上下文和 migration input 行为。
- [x] 3.3 确认 compile command evidence、日志、summary 和 artifact 内容通过统一路径脱敏处理。
- [x] 3.4 确认非法或不可下载 compile database artifact 时仍按现有降级策略处理。

## 4. 测试覆盖

- [x] 4.1 增加 scanner 单元测试：源码无 x86 文本但 compile command 包含 `-mavx2` 时生成 finding。
- [x] 4.2 增加 scanner 单元测试：`arguments` 数组和 `command` 字符串两种格式均可解析。
- [x] 4.3 增加 scanner 单元测试：非法 JSON、解析失败 entry、越界 entry、排除路径和内部探测 entry 不导致整次扫描失败。
- [x] 4.4 增加 scanner 单元测试：带 compile database 后默认源码 finding 不减少。
- [x] 4.5 增加 Java 或 E2E 测试：KB scan summary、finding evidence 和 API 响应不暴露服务器真实路径、远端路径或对象存储 key。
- [x] 4.6 增加 scanner 单元测试：源码或 Makefile 已命中同一编译参数时，compile database 不重复生成展示 finding。
- [x] 4.7 更新 API E2E fixture，覆盖 source/x86 构建生成 compile database 后自动派生 KB finding。

## 5. 验证和文档

- [x] 5.1 运行 `tools/kb-scanner` 单元测试并确认全部通过。
- [x] 5.2 运行相关 Java 单元测试或轻量集成测试。
- [x] 5.3 使用真实 API 流程验证：同一项目先不带构建上下文扫描，再构建生成 compile database 后重新扫描，确认 finding 不减少且新增 compile command finding。
- [x] 5.4 更新 E2E 文档或覆盖矩阵，说明 compile database 派生 finding 的运行方式和清理要求。
