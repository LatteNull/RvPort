## 1. Purpose 文档修复

- [x] 1.1 扩展 `backend-database-design` 的 `## Purpose`，明确持久化边界、数据安全、索引和运行时关联。
- [x] 1.2 扩展 `kb-scan-runtime` 的 `## Purpose`，明确 CLI 调用、源码输入、finding 输出、代码上下文和制品边界。
- [x] 1.3 扩展 `migration-report-runtime` 的 `## Purpose`，明确报告输入、统计摘要、对象存储和下载边界。
- [x] 1.4 扩展 `running-task-cancellation` 的 `## Purpose`，明确取消请求、定点取消、运行时句柄和资源清理边界。
- [x] 1.5 扩展 `test-support-api` 的 `## Purpose`，明确构建隔离、安全边界、白名单能力和生产禁用要求。

## 2. 验证

- [x] 2.1 分别运行 5 个受影响 spec 的严格校验，确认不再出现 Purpose 过短 warning。
- [x] 2.2 运行 `openspec validate --specs --strict`，确认全量主 spec 校验通过或记录剩余非本 change 问题。
- [x] 2.3 检查 change 状态，确认 proposal、design、specs 和 tasks 均完成。
