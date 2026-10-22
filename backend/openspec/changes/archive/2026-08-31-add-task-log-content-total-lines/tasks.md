## 1. Schema 与持久化

- [x] 1.1 为任务日志增加每类日志总行数的持久化元数据；如涉及 schema 变更，使用 Liquibase 并重新生成 jOOQ 代码。
- [x] 1.2 更新任务日志追加和落库路径，在写入内容时维护总逻辑行数。
- [x] 1.3 为旧数据或缺失行数元数据提供降级处理，并确保不暴露服务器路径。

## 2. 日志内容 API

- [x] 2.1 为 `TaskLogContentResponse.LogContent` 增加 `totalLines` 字段。
- [x] 2.2 为 `merged`、`stdout`、`stderr` 分别独立返回 `totalLines`。
- [x] 2.3 保持现有 `offset`、`lines`、`returnedLines`、`hasMore` 和 `content` 行为不变。
- [x] 2.4 确保日志记录或日志文件缺失时返回 `totalLines=0`、空内容、`returnedLines=0` 和 `hasMore=false`。

## 3. 测试与验证

- [x] 3.1 增加正常流程单元测试，验证日志内容响应返回准确总行数。
- [x] 3.2 增加异常流程单元测试，覆盖日志文件缺失和非法请求参数。
- [x] 3.3 增加 edge case 单元测试，覆盖 offset 超过总行数、空日志、没有尾随换行的内容。
- [x] 3.4 更新 API E2E 日志内容测试，验证默认请求、单类请求和分页请求中的 `totalLines`。
- [x] 3.5 运行目标后端测试和 OpenSpec 校验。
