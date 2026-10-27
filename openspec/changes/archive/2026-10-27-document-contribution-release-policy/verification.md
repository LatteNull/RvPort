# 实施验收记录

- 日期：2026-10-27（Asia/Hong_Kong）。
- 变更：`document-contribution-release-policy`。
- 工作目录：`D:/projects/RvPort`，使用根项目 OpenSpec。
- 范围：两个 README、两份开发指南、两份 AGENTS 及本次 OpenSpec 文档。

## 内容审校

| 规范场景 | 实际结果 |
|---|---|
| 提交类型与双语信息 | 六份文档均包含 `feat`、`test`、`fix`、`refactor`、`ci`、`chconf`、`docs`；两份指南的类型表一致，完整双语标题和正文示例一致，长名称不作为可用类型 |
| AI 生成代码审计 | 明确同等审计及 PR 审查，核对需求、正确性、风险和适用验证；自动检查不能代替审查 |
| 开发与发布分支 | fork → clone → 从上游 `dev` 创建主题分支 → 个人 fork → PR 到上游 `dev`；`master` 用于发布 |
| 四段版本 | 提供 `1.2.0.0`、`1.2.0.0-rc1`、`1.2.0.0-rc2`；指南明确四段约定不是标准 SemVer |
| Roadmap 与 Issue | 计划确定、Issue 和负责人、关联 PR、合并至 `dev` 并验收后确认关闭、整体完成后发布 PR 到 `master`；不假定 Issue 自动关闭 |
| 文档入口一致性 | README 和 AGENTS 各有五项摘要及对应语言的开发指南章节链接；完整规则集中在指南 |

## 实际检查

以下命令从根目录执行，均成功：

```powershell
git diff --check
git diff --stat
git diff --numstat
openspec validate document-contribution-release-policy --strict
```

另使用 PowerShell 对六份文档进行只读内容与链接检查：读取 Markdown 相对链接，解析目标文件和章节标题；逐文件核对七种类型及关键规则标识；比较两份指南类型表的顺序和完整提交示例；检查本次 OpenSpec Markdown 行尾空白。结果为：六份文档通过，36 个本地链接存在，4 个锚点存在，类型表与双语提交示例一致，本次 OpenSpec Markdown 无行尾空白。

`git diff --numstat` 显示六份既有文档共新增 172 行、删除 0 行，原 Docker、测试、覆盖率及其他章节完整保留。按 delta spec 六个场景审校中英文内容，全部满足。工作区除这六份文档外仅新增本次 OpenSpec 目录；未修改 `.agents/`、业务代码、版本元数据或流水线。

## 验证适用范围

本次仅修改文档和规则文本，无自有可执行代码变更。单元测试、行/分支覆盖率、Docker 运行时构建及 Compose 启动不适用，未执行；不引用历史测试报告作为本次验收依据。内容检查不代表远端分支保护、实际 Issue/PR 或发布自动化已经配置。

## 阶段状态

apply 的实现与验证完成。2026-10-27 按用户授权完成 sync 与 archive：

- 新增主规范 `openspec/specs/contribution-release-policy/spec.md`，6 项要求的正文与 delta spec 完全一致。
- `openspec validate contribution-release-policy --type spec --strict` 通过，归档前重新验证 change 也通过。
- 9 项任务全部完成，归档到 `openspec/changes/archive/2026-10-27-document-contribution-release-policy/`；移动时核对全部 6 个文件的 SHA256 一致，保留 `.openspec.yaml`，随后更新本记录的阶段状态。
- OpenSpec 流程结束，未执行 Git 提交或推送。
