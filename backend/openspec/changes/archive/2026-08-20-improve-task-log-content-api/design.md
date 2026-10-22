## Context

当前任务日志有两套用途：

- 运行中动态展示：任务级日志 SSE 基于 `task_log_events` 逐片段推送，适合脚本、构建、测试正在执行时展示实时输出。
- 完成后查看：构建验证和自动化测试详情页需要快速查看 merged/stdout/stderr 的历史文本。

现有 `GET /api/tasks/{taskId}/logs` 返回 `task_logs` 元数据分页。由于日志写入会按换行或固定大小 flush，每次 append 同时插入一条 `task_logs` 元数据，因此完成态页面如果用该接口拼接内容，会产生大量 API 资源和前端渲染开销。

底层 SSH streaming 已经可以写入 `STDOUT`、`STDERR` 和 `COMBINED` 三类日志文件。自动化测试记录已有 `combined_log_id`，构建验证记录当前只保存 stdout/stderr log id，需要补齐 merged log 引用。

## Goals / Non-Goals

**Goals:**

- 提供完成态任务日志内容读取接口，一次返回 merged/stdout/stderr 中任意一类或多类日志正文。
- 默认返回每类最后 100 行，支持从底部向上通过 offset 分段读取。
- 支持同一请求中不同日志类型使用不同 offset 和 lines。
- 构建验证和自动化测试详情均稳定暴露 merged/stdout/stderr 三类日志引用。
- 保持项目访问守卫、路径安全和敏感信息边界。

**Non-Goals:**

- 不替代任务级日志 SSE。
- 不改变 `GET /api/tasks/{taskId}/logs` 作为日志元数据列表的语义。
- 不一次性返回完整大日志。
- 不新增前端专用的构建日志接口和测试日志接口；统一通过任务日志内容 API 读取。

## Decisions

### 新增任务日志内容接口

新增：

```text
GET /api/tasks/{taskId}/log-content
```

默认行为：

- 不传 `types` 时返回 `merged`、`stdout`、`stderr` 三类。
- 不传 offset 时每类 offset 为 `0`，表示从日志底部开始。
- 不传 lines 时每类返回最多 100 行。

支持参数：

| 参数 | 说明 |
| --- | --- |
| `types` | 可选，逗号分隔，允许 `merged,stdout,stderr`；不传默认三类 |
| `lines` | 可选，全局默认行数，默认 100 |
| `mergedOffset` / `stdoutOffset` / `stderrOffset` | 可选，某类日志从底部向上跳过的行数 |
| `mergedLines` / `stdoutLines` / `stderrLines` | 可选，某类日志单独读取行数，优先于 `lines` |

响应使用 map，便于前端按 tab 更新：

```json
{
  "logs": {
    "merged": {
      "type": "merged",
      "logId": "uuid",
      "offset": 0,
      "lines": 100,
      "returnedLines": 100,
      "hasMore": true,
      "content": "..."
    }
  }
}
```

替代方案是为每类日志单独提供接口，例如 `/merged-log`、`/stdout-log`。该方案会让前端在多 tab 恢复时发起多次请求，也会在构建和测试之间重复协议，因此不采用。

### 从底部向上分页

offset 以日志底部为起点：

- `offset=0&lines=100`：最后 100 行。
- `offset=100&lines=100`：倒数第 101 到 200 行。
- `hasMore=false`：已经到达文件顶部。

响应内容建议仍按正常阅读顺序返回，即较早行在前、较新行在后。这样前端向上加载时可以将新返回片段 prepend 到已有内容前。

### 使用文件读取，不使用元数据记录拼接

日志内容读取 SHALL 直接读取 `task_logs.file_path` 指向的受控日志文件。`task_logs` 元数据中可能存在多条同类型记录，服务层应按类型选择该任务最新的日志元数据作为文件引用。

读取实现需要避免将整个大文件读入内存。可采用从文件尾部按块反向扫描换行的方式，或等效的受控 tail 实现。MVP 可以用清晰的文件 tail 工具类实现，并设置最大 lines 上限。

### 构建验证补齐 merged log 引用

构建验证 worker 通过 SSH streaming 执行脚本时实际会写入 `COMBINED` 日志。`build_runs` 需要保存 `combined_log_id` 或等效字段，构建详情响应返回：

- `mergedLogId`
- `stdoutLogId`
- `stderrLogId`

自动化测试已有 `combinedLogId`，响应命名可保持兼容，但 API 文档中应明确它就是 `merged` 日志引用。

### SSE 和完成态日志查看分工

运行中页面继续使用：

```text
GET /api/tasks/{taskId}/log-events
```

完成态构建/测试详情使用：

```text
GET /api/tasks/{taskId}/log-content
```

两者不可混用：SSE 承载小片段事件和终态通知，内容接口承载完成态日志文件倒序分页读取。

## Risks / Trade-offs

- [Risk] 大日志反向读取实现不当会导致内存占用过高。  
  Mitigation: 读取时设置 `lines` 上限和最大扫描块策略，测试覆盖大日志、无换行日志和超长单行。

- [Risk] 旧构建记录没有 merged log 引用。  
  Mitigation: 对旧记录返回 `merged.logId=null`，前端可降级展示 stdout/stderr；新构建记录必须写入 merged log。

- [Risk] 日志文件末尾没有换行导致行数计算错误。  
  Mitigation: tail 工具测试覆盖无结尾换行、空文件、只有一行、Windows/Unix 换行。

- [Risk] 同一类型存在多条 `task_logs` 元数据。  
  Mitigation: 内容读取只选择同任务同类型最新记录作为文件引用，不按元数据多条拼接。

## Migration Plan

1. 新增构建运行 merged log 字段并回填为空。
2. 构建 worker 完成时写入 `COMBINED` 最新日志 ID。
3. 新增日志内容读取 DTO、请求解析和 service。
4. 新增 `/api/tasks/{taskId}/log-content`，复用任务访问守卫。
5. 更新 API 文档、OpenSpec、E2E 和单元测试。

Rollback 策略：如果内容读取接口需要回滚，可保留数据库新增字段为空，不影响现有构建/测试详情和日志下载；前端可回退使用下载接口或现有元数据接口。

## Open Questions

无。
