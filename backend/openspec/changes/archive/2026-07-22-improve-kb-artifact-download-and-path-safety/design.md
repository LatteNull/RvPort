## Context

KB 扫描已将 `scan-result.json`、`scan-report.html` 和 `scan.log` 作为受控 artifact 保存，并提供 artifact 列表和按 `artifactId` 下载接口。当前前端若只想下载 HTML 或 JSON，需要先查询列表、识别 artifact type、再使用具体 artifact ID 下载，交互上不够直接。

路径安全方面，KB artifact 的 `content_path`、finding 代码上下文的源码路径、scanner evidence 中的文件路径都涉及服务器本地路径。当前实现中存在局部 `normalize`、`toRealPath`、`startsWith` 和字符串替换逻辑，行为分散且不利于复用。

## Goals / Non-Goals

**Goals:**

- 提供按格式下载 KB 扫描 artifact 的 API，使前端可以直接选择 HTML、JSON 或日志格式。
- 保留现有按 artifact ID 下载 API，支持列表页精确下载。
- 新增统一服务器路径安全工具，用于根目录内路径解析、真实路径边界校验和路径文本脱敏。
- 让 KB artifact 下载、finding 代码上下文和 scanner evidence/log/error 摘要复用统一路径安全逻辑。
- 用单元测试和 E2E 覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不修改 KB scanner CLI 输出格式。
- 不新增数据库表或修改 artifact schema。
- 不引入通用 artifact API。
- 不实现前端页面改造。
- 不改变现有项目权限模型。

## Decisions

### 1. 增加按格式下载接口，保留按 ID 下载接口

新增接口：

```text
GET /api/kb-scans/{scanId}/artifacts:download?format=html
GET /api/kb-scans/{scanId}/artifacts:download?format=json
GET /api/kb-scans/{scanId}/artifacts:download?format=log
```

格式映射：

| format | artifactType |
| --- | --- |
| `html` | `SCAN_REPORT_HTML` |
| `json` | `SCAN_RESULT_JSON` |
| `log` | `SCAN_LOG` |

选择这个方案的原因是前端可以不关心 artifact ID 即可下载常见报告格式，同时保留已有精确下载接口用于审计列表。替代方案是在现有列表接口中强约定前端自行挑选 artifact ID，但这会把后端领域映射泄露到前端流程中。

### 2. artifact 文件访问必须绑定 KB 输出根目录

下载接口不能只信任数据库中的 `content_path`。服务层应先根据配置得到 KB 输出根目录，再将 artifact `content_path` 解析为真实路径，并校验其位于该输出根目录内。

若文件不存在、路径越界、符号链接逃逸或格式没有对应 artifact，统一返回安全业务错误，不返回本地路径、异常堆栈或真实文件名。

### 3. 新增通用服务器路径安全工具

建议新增：

```text
cn.rvport.backend.common.path.ServerPathGuard
```

核心能力：

- `resolveExistingFileUnderRoot(root, candidate)`：解析并校验既有文件位于 root 内。
- `resolveExistingDirectoryUnderRoot(root, candidate)`：解析并校验既有目录位于 root 内。
- `resolveRelativeUnderRoot(root, relativePath)`：用于用户或 scanner 输出中的相对路径边界校验。
- `redactPathText(text, allowedRoot, replacement)`：将 allowedRoot 下的绝对路径替换为受控占位符；非 allowedRoot 路径不得原样出现在 API 响应、日志摘要或 evidence 中。

工具内部应区分：

- 访问文件：越界必须失败。
- 脱敏文本：允许 root 内路径替换为相对/占位符；root 外路径替换为 `<server-path-redacted>` 或触发安全错误，具体由调用方选择。

### 4. 代码上下文复用路径工具

`GET /api/findings/{findingId}/code-context` 继续只允许读取 finding 所属源码工作副本内的文件。实现上使用统一工具替代当前局部 `normalize + toRealPath + startsWith` 逻辑，并覆盖 Windows/Unix 路径、`..`、绝对路径和符号链接逃逸。

### 5. scanner 输出脱敏复用路径工具

`KbScanRuntimeService` 中 evidence、日志摘要和错误摘要应复用同一脱敏工具。根目录内源码路径可替换为 `<source-root>/relative/path` 或等效相对路径，KB 输出目录可替换为 `<kb-output-root>`，其他服务器绝对路径不得原样进入 API 响应或任务事件。

## Risks / Trade-offs

- 路径文本识别无法覆盖所有非标准路径表达 → 测试覆盖 Windows、Unix、混合分隔符和 JSON 嵌套 evidence，并保守替换疑似服务器绝对路径。
- `content_path` 历史数据可能是相对路径或旧格式绝对路径 → 实现需兼容已有合法路径，但所有路径最终必须落入 KB 输出根目录。
- 符号链接校验依赖文件存在 → 下载和代码上下文读取只对既有文件执行真实路径校验；不存在时返回安全 not found。
- 新接口与旧接口并存会增加 API 面 → 文档明确旧接口用于精确 artifact 下载，新接口用于按格式快捷下载。
