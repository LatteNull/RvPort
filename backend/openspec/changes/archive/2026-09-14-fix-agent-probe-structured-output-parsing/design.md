## Context

`DefaultCodexProcessRunner` 同时保存 `stdout`、`stderr` 和按到达顺序交织的 `mergedOutput`。为便于人工诊断，merged output 的每个读取块会增加 `[STDOUT]` 或 `[STDERR]` 前缀；OpenCode 等 CLI 还会在 stderr 输出 ANSI 样式和运行状态。当前 `CodexProviderProbeService` 却优先把 merged output 交给仅支持单行完整 JSON 的解析器，造成如下问题：

```text
有效 stdout JSON
      │
      ├── stdout: {"status":"ok", ...}
      │
      └── merged: [STDOUT] {"status":"ok", ...}
                         │
                         └── 单行解析器拒绝，误报 OUTPUT_INVALID
```

真实探测记录已经证明 DeepSeek Harness 与 OpenCode 能生成预期 JSON，OpenCode 也能完成 workspace 读写；失败发生在后端结构化结果提取阶段。Codex 偶尔成功是因为通道标签按读取块添加，JSON 是否位于无标签的新行受缓冲分块影响，并不代表其输出路径更可靠。

## Goals / Non-Goals

**Goals:**

- 明确机器可读结构化结果与人工诊断日志的边界。
- 稳定解析 Codex、DeepSeek Harness、OpenCode 的真实输出形态。
- 支持日志前后缀、ANSI、通道标签、Markdown 代码块、多行 JSON 和多个 JSON 候选。
- 仅接受满足当前 probe 预期字段的 JSON，避免把 CLI 的其他 JSON 日志误认为结果。
- 保持错误诊断脱敏，并通过正常、异常和边界测试维持至少 90% 行与分支覆盖率。

**Non-Goals:**

- 不改变 `DefaultCodexProcessRunner` 的 stdout、stderr、merged output 采集格式和交织语义。
- 不改变 Agent Probe API、数据库 schema、Agent prompt 或历史探测记录。
- 不处理前端仍按旧业务阶段检查项展示通用 Agent Probe 结果的问题。
- 不把业务阶段输出 schema 再次纳入通用 Agent 兼容性探测。

## Decisions

### 1. 结构化提取按 stdout、清洗后的 merged output 顺序执行

首选 stdout，因为 Agent 的最终回答属于标准输出，且不含后端人为添加的通道标签。只有 stdout 中不存在满足契约的 JSON 时，才清洗 merged output 并回退解析。stderr 和原始 merged output 继续用于退出失败、超时和格式错误的诊断消息。

不选择直接修改 merged output 的采集方式，因为该格式同时服务于日志排障，改变它可能影响其他 Agent 任务；也不选择继续优先 merged output，因为机器结果会被诊断标签和并发 stderr 污染。

### 2. 解析器提取多个 JSON 对象并按倒序验证契约

解析流程先尝试完整文本，再识别 Markdown fenced block，最后使用理解字符串转义和括号层级的对象边界扫描提取候选。候选按照在输出中出现的顺序倒序校验，返回最后一个满足 `expectedFields` 的 JSON 对象；不满足字段的合法 JSON 继续向前搜索，而不是立即失败。

这比基于正则截取第一个 `{...}` 更稳健，因为日志或 JSON 字符串内可能包含花括号，也比“最后一个合法 JSON”更安全，因为 CLI 可能在最终回答后输出自己的统计 JSON。

### 3. merged output 回退只做传输包装清洗

回退输入清除 ANSI CSI/OSC 控制序列，并移除行首或读取块边界上的 `[STDOUT]`、`[STDERR]` 标签。清洗不得改写 JSON 字符串内部的普通文本。结构化判定使用清洗结果，失败消息仍使用既有 `sanitize` 对诊断内容进行密钥脱敏、路径规范化和长度限制。

### 4. 输出有效性由退出状态与结构契约共同决定

进程超时或非零退出码继续优先判定为执行失败，即使输出中存在 JSON。退出成功后，只有找到对象且所有预期字段完全匹配时，当前 probe 才成功。workspace write 仍需额外验证输出文件存在、内容为对象且 marker 匹配。

### 5. 用真实输出形态锁定行为

单元测试直接构造带通道标签、ANSI、日志交织和不同分块形态的 `CodexProcessResult`，并覆盖三类 runtime。API E2E 使用可控 fixture Agent 产生真实 stdout/stderr 和 workspace 文件，不依赖外部模型服务；测试同时验证失败结果不泄露密钥。最终执行完整 Maven 单元测试与 JaCoCo 门槛检查，整体和受影响模块行、分支覆盖率均不得低于 90%。

## Risks / Trade-offs

- [宽松提取可能误收日志中的 JSON] → 每个候选必须完整解析为对象并满足当前 probe 的全部预期字段，且从后向前选择。
- [ANSI 或通道标签出现在 JSON 字符串值中] → 清洗仅针对控制序列和明确的输出包装边界，不做全局字符串替换。
- [输出超过进程采集上限导致 JSON 被截断] → 保持现有输出上限与明确的格式错误；本 change 不扩大日志内存边界。
- [不同 CLI 将最终回答写入 stderr] → stdout 失败后使用清洗 merged output 回退，兼容非标准 CLI，同时保留退出码约束。
- [历史错误结果继续显示] → 不迁移历史记录，用户重新运行 Probe 后由最新组合结果覆盖展示。

## Migration Plan

1. 增加结构化输出提取与包装清洗能力及单元测试。
2. 将 Agent Probe 三个检查统一接入按预期字段筛选的提取流程。
3. 运行完整单元测试、JaCoCo 检查和 Agent Probe API E2E。
4. 重建 API 与 Worker 镜像，使用真实 DeepSeek Harness、OpenCode、Codex runtime 复测。
5. 若出现回归，可回滚解析器调用，数据库和 API 无需迁移。

## Open Questions

无。
