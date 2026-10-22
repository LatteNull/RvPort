## Context

当前 `GET /api/tasks/{taskId}/log-content` 用于构建、测试等完成态日志查看。接口支持 `merged/stdout/stderr` 三类日志，并通过 `offset + lines` 从日志文件中分段读取。

现有实现中 `TaskLogTailReader` 从物理文件尾部向上读取，隐含假设是“日志文件尾部代表最新日志”。但真实构建日志存在倒序存储场景：文件头部是最新日志，文件尾部是最早日志。此时 `offset=0` 会返回最早日志，导致前端首屏展示错误。

约束：
- 不改变响应结构，避免影响前端已有解析。
- 不改变 SSE 实时日志推送。
- 不改变日志下载接口，下载仍返回原始日志文件内容。
- 不引入新的数据库表。

## Goals / Non-Goals

**Goals:**

- 将 `log-content` 的 offset 语义定义为展示顺序 offset。
- `offset=0` 必须返回当前日志的最新展示页。
- 倒序日志文件中，最新页从文件头读取；后续 offset 返回更旧内容。
- 页内内容保持日志文件中的自然顺序，避免后端在单页内二次反转导致时间关系混乱。
- 覆盖单元测试、服务测试和 E2E fixture。

**Non-Goals:**

- 不重写历史日志文件。
- 不改变日志写入策略。
- 不改变任务日志事件表或 SSE event id 语义。
- 不实现前端虚拟滚动或 UI 展示逻辑。

## Decisions

### Decision 1: API offset 面向展示顺序，而不是物理文件顺序

`offset` 表示“按用户看到的日志顺序跳过多少行”。因此：

```text
offset=0&lines=100   -> 最新展示页
offset=100&lines=100 -> 更旧的下一页
```

这样前端不需要知道日志文件是正序追加还是倒序保存。

### Decision 2: 当前修复按倒序文件处理完成态日志内容读取

本次 bug 来自倒序日志文件：文件头是最新日志，文件尾是更早日志。因此本次实现应让完成态日志内容读取从文件头按 `offset + lines` 读取对应窗口。

单页返回保持文件内自然顺序：

```text
file:
  latest-1
  latest-2
  older-1
  older-2

offset=0&lines=2 -> latest-1/latest-2
offset=2&lines=2 -> older-1/older-2
```

### Decision 3: 保持 response schema 不变

继续返回：

- `type`
- `logId`
- `offset`
- `lines`
- `returnedLines`
- `hasMore`
- `content`

`hasMore` 表示按展示顺序继续增加 offset 后是否还有更旧内容。

### Decision 4: 保持下载接口返回原始文件

下载接口面向审计与离线分析，应保留原始物理文件内容，不因页面分页语义改变而改写文件顺序。

## Risks / Trade-offs

- [Risk] 如果部分日志文件仍是正序追加，直接按文件头分页会让这部分日志首屏变成最早内容。  
  → Mitigation: 实现前先确认当前生产日志内容接口所服务的完成态构建/测试日志统一为倒序，或在实现中抽象 reader 策略，为后续按日志元数据区分方向预留入口。

- [Risk] 从文件头读取大文件时如果直接 `Files.readAllLines` 会造成内存风险。  
  → Mitigation: reader 只读取 `offset + lines` 所需窗口，保持 `lines` 上限，避免一次性加载完整日志。

- [Risk] 文档中“最后 100 行”容易再次被理解为物理文件尾。  
  → Mitigation: specs 和 API 文档统一改为“最新展示页/更旧日志”，避免使用“文件底部”表述。
