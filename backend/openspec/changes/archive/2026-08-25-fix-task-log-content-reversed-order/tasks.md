## 1. 日志读取语义修正

- [x] 1.1 将完成态日志内容读取的 offset 语义实现为“按展示顺序跳过行数”。
- [x] 1.2 支持倒序日志文件：文件头为最新日志时，`offset=0` 从文件头读取最新展示页。
- [x] 1.3 保持单页内容按文件内自然顺序返回，并正确计算 `returnedLines` 和 `hasMore`。
- [x] 1.4 保持缺失文件、空文件、零行数、offset 超出总行数等 edge case 行为稳定。
- [x] 1.5 确认日志内容脱敏、日志路径保护、日志下载和 SSE 实时日志不受影响。

## 2. API 与文档

- [x] 2.1 更新 `docs/API_DESIGN.md` 中 `GET /api/tasks/{taskId}/log-content` 的 offset 说明，去除“从文件底部向上”的物理方向表述。
- [x] 2.2 更新相关 OpenSpec 主文档同步后的描述，统一使用“最新展示页”和“更旧日志页”。
- [x] 2.3 确认响应结构不变，前端无需修改字段解析。

## 3. 测试

- [x] 3.1 更新 `TaskLogTailReaderTests`，覆盖倒序日志首屏读取最新内容。
- [x] 3.2 更新 `TaskLogTailReaderTests`，覆盖倒序日志 offset 读取更旧内容和 `hasMore`。
- [x] 3.3 更新 `TaskLogServiceTests`，验证 content API 读取倒序日志时返回正确内容并保留脱敏。
- [x] 3.4 更新 `003-task-sse` 或相关 E2E fixture，覆盖倒序日志的 `mergedOffset=0` 和非零 offset。
- [x] 3.5 覆盖非法参数和越权测试保持通过。

## 4. 验证

- [x] 4.1 运行相关单元测试。
- [x] 4.2 运行任务日志相关 E2E 模块。
- [x] 4.3 运行 `openspec validate fix-task-log-content-reversed-order --strict`。
