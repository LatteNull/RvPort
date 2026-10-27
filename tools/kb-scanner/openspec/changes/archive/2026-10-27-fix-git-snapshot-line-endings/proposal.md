## Why

CI 从 Git 检出的 Clang JSON 为 293356 字节，Windows 工作区混入 9930 个 CRLF 后为 303286 字节；之前按工作区冻结原始字节并构建 Docker，遗漏了 Git 快照验证。知识语义相同，但字节数、SHA-256 及引用它们的回归合同跨平台不一致，必须修复验收输入和基线来源。

## What Changes

- 为 KB Scanner 的文本输入明确 LF 属性，保留二进制与已有特殊夹具属性；不批量重写其他工具、前后端或历史账本。
- 以 Git 中的 LF 字节核对当前事实基线、manifest 与活动测试摘要；证明数据、类别计数及检测语义未变化，记录换行造成的摘要差异。
- 补充字节合同的正常、换行污染、内容篡改和元数据不一致测试，维持整体和受影响模块行/分支至少 90%。
- 用独立 Git 快照执行 Docker 完整入口，审计 `core.autocrlf` 和导出属性，避免把经过 Windows 转换的 archive 当成原始 Git blob。
- 按用户授权更新根 `.agents/skills/git-commit-push/SKILL.md`，增加原始字节、Git index、换行属性及验证快照一致性检查，保留其现有失败停止和授权边界。

## Capabilities

### New Capabilities

- `kb-scanner-portable-source-baselines`: 定义跨平台 LF 输入、原始字节冻结及可追溯快照验收合同。

### Modified Capabilities

- `kb-scanner-unit-suite-mappings`: 完整验收须验证实际拟提交的 Git 快照，不能仅凭工作区 Docker 和变更文件摘要宣称与 CI 一致。

## Impact

影响 KB Scanner 的 Git 属性、事实来源摘要、活动测试与开发文档，以及用户明确指定的根提交技能；已有 `.gitignore` 技能例外保持不变。保留 Clang/GCC 六类知识和 generatedSet 引用，不改变扫描业务、JSON/HTML/log 输出结构，也不涉及操作系统迁移。新增或调整测试支持逻辑时纳入隔离单测映射及双 90% 门槛；不以合同或整站冒烟替代单测。不因修改提交技能自动创建提交或推送。
