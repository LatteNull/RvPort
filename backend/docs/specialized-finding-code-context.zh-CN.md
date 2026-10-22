# 专项分析详情内嵌源码上下文

[English](specialized-finding-code-context.md) | 简体中文

## 请求

```http
GET /api/projects/{projectId}/floating-point-findings/{findingId}
GET /api/projects/{projectId}/memory-order-findings/{findingId}
```

沿用登录会话和项目访问权限。无需提交源码路径、版本或上下文大小，后端从 Finding 读取；两个接口不能交叉读取不同分析类型的 Finding。

## 响应

沿用现有详情 API 和 `data/traceId/timestamp` 包装，保留原有 Finding 字段，新增 `data.codeContext` 与 `data.codeContextUnavailableReason`。成功时后者为 null，`data.codeContext` 字段如下：

| 字段 | 含义 |
|---|---|
| findingId / runId | Finding 和分析运行 ID |
| sourceRevisionId | 该分析绑定的历史源码版本，不是当前最新版本 |
| filePath | 项目相对路径 |
| contextBefore / contextAfter | 上下文窗口配置，均为 20 |
| startLine / endLine | 实际返回的首末行号，1-based；文件边界会截断 |
| highlightStartLine / highlightEndLine | 主位置需要高亮的真实行号范围，包含两端 |
| lines | 按行号升序排列的片段行 |
| lines[].lineNumber | 原文件真实行号 |
| lines[].text | 原始行文本，不含行尾换行符；空行仍返回 |
| lines[].highlighted | 是否属于主位置高亮范围 |

例如 Finding 在第 62 行，则片段从第 42 行开始，最多到第 82 行；文件只有 72 行则截至第 72 行。高亮仍为真实第 62 行，不应把编辑器片段的第 62 行当作该位置。

前端可用 `lines.map(line => line.text).join('\n')` 作为编辑器文本，以 `startLine` 设置显示行号偏移；若编辑器高亮接受片段内行号，转换为 `lineNumber - startLine + 1`。本次未修改前端。

详情一次返回 Finding 和代码，无需额外请求，不再提供独立 `/code-context` 接口。列表不加载源码，这两个新增字段为 null。上下文展示主位置，不自动合并多文件 occurrences。浮点 v2 主位置为点坐标时起止高亮行相同；内存序 span 可以高亮多行。

## 错误与边界

- 项目无权限：沿用项目权限错误。
- `SPECIALIZED_FINDING_NOT_FOUND`：结果不存在或不属于指定项目/类型，404。

以下情况不导致详情请求失败：`codeContext=null`，`codeContextUnavailableReason` 为以下原因码，原始 Finding 正常返回。

- `SOURCE_REVISION_NOT_FOUND`：绑定源码版本不存在或归属不符。
- `FINDING_SOURCE_LOCATION_UNAVAILABLE`：没有有效位置、范围倒置或超出文件。
- `FINDING_SOURCE_FILE_NOT_FOUND`：工作副本或文件已清理，不回退到最新代码。
- `FINDING_SOURCE_PATH_INVALID`：绝对路径、目录穿越、越界符号链接等非法路径。
- `FINDING_SOURCE_FILE_UNREADABLE`：读取失败或非合法 UTF-8 文本。
- `FINDING_SOURCE_FILE_TOO_LARGE`：超过 8 MiB 的读取上限。
- `FINDING_SOURCE_DIGEST_MISMATCH`：源码内容与 Finding 的 `fact.primaryLocation.sourceSha256` 不一致；不展示其他版本的代码。

接口不修改扫描结果、不重新运行扫描；原始源码文本不做破坏性路径替换，错误消息不泄漏服务器绝对路径。

## 内存序位置与快照

内存序 Finding 使用 `detail.fact.primaryLocation` 的项目相对路径和 `span`。工具按引用的
Scope、翻译单元和事件定位，不把头文件行号套到主源文件。`occurrences` 保留多个位置；
证据链中的关联源码访问步骤各自保留位置，不给所有分析层复制一个位置。

`span.end` 是不包含端点的坐标。当结束位置为下一行第 1 列时，详情高亮截至上一行；
源码片段仍为高亮范围前后各 20 行。详情已有的 `codeContext` 返回主位置，其他位置的
扫描时片段在 `detail.occurrences[].location.context` 中，不增加请求接口。

正式分析的事件没有调试位置、路径越界或快照不可用时，工具保留原始风险/消解结论，
并通过 `source-location-unavailable` 与中英文说明标记源码证据缺口。源码候选仍是候选，
不能因为获得代码片段而提升为正式风险。历史记录不重写，需重新扫描获取修复后的片段。

## 浮点证据链步骤说明

浮点 Finding 详情仍使用上述 `GET /api/projects/{projectId}/floating-point-findings/{findingId}`，
双语步骤位于 `data.detail.evidenceChain.steps[]`。无需新增说明接口，不以 Finding 顶层的
`title/titleEn/message/messageEn` 替代步骤文案。此扩展不改变内存序工具的协议。

扩展后的浮点 v2 合同保持 `schemaVersion: "2.0"`，新工具输出的每个步骤包含：

| 字段 | 含义与新输出约束 |
|---|---|
| title | 中文标题，非空，最多 512 字符 |
| titleEn | 英文标题，非空，最多 512 字符 |
| reason | 中文证据说明或判断限制，非空，最多 4096 字符 |
| reasonEn | 英文证据说明或判断限制，非空，最多 4096 字符 |

以上文案由浮点工具根据步骤直接引用的证据生成，工具与严格 Schema 必须配套发布。
步骤原有 `id/kind/status/references/reasonCodes` 以及顺序保持原样；证据不足时保留
`partial/unknown` 等状态和原因码，不因文案完整就视为证据完整。以下仅为步骤字段示例：

```json
{
  "title": "源码浮点比较",
  "titleEn": "Source floating-point comparison",
  "reason": "源码包含比较表达式：x == 0.1，位置为 main.cpp:1。",
  "reasonEn": "Source contains comparison x == 0.1 at main.cpp:1."
}
```

后端将工具原始 Finding 整体导入并保存在 `specialized_analysis_findings.detail` JSONB 中，
详情完整透传这些字段，包括中文、英文和嵌套引用。源码上下文不可用时，仍返回原始 `detail`，
只有 `codeContext` 与 `codeContextUnavailableReason` 按上文规则变化。项目访问权限保持不变。

历史记录不回填：没有 `evidenceChain`、空 `steps`、步骤缺全部或部分文案字段时仍可读取，
响应保留原有缺失状态，不补空字符串、固定文案或用其他语言替代。新版生成约束不用于拒绝
历史详情。要获取新文案需新建扫描，不静默重写旧扫描、稳定 ID 或历史摘要。

原始 JSON 仍通过既有
`GET /api/projects/{projectId}/floating-point-analyses/{runId}/artifacts:download?format=json`
下载；对应位置是原始结果的 `findings[].evidenceChain.steps[]`。原始 JSON、落库 `detail`
和详情中的步骤应一致。继续复用现有专项分析报告制品与归档候选登记，不增加归档节点、
报告类型或数据库列。
