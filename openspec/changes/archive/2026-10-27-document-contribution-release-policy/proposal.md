## Why

会议明确了提交信息、代码审计、分支、版本和 Roadmap 协作规则，但项目入口与开发规范尚未统一记录。需要通过根项目 OpenSpec 固化这些约定，让人工和 AI 辅助开发遵循同一套可审查流程。

## What Changes

- 统一提交标题为 `Type: Message`，具体采用 `<type>: <English> / <中文>`；类型限定为 `feat`、`test`、`fix`、`refactor`、`ci`、`chconf`、`docs`，说明各类型用途，并提供中英双语标题与正文示例。
- 明确 AI 生成代码必须经过与人工代码相同的代码审计、PR 审查及适用验证。
- 明确 `dev` 为开发集成分支、`master` 为发布分支；贡献者 fork 上游仓库并 clone 到本地，从 `dev` 开发主题分支，经 PR 合并回上游 `dev`。
- 采用“大版本.小版本.bug fix.hotfix”的四段版本号；预发布版本使用类型后缀，例如 `1.2.0.0-rc1`、`1.2.0.0-rc2`。
- 记录 Roadmap 确定计划、创建 Issue 并指派负责人、关联 PR、完成后关闭 Issue、整体完成后合并至 `master` 发布的流程。
- 更新根 README、开发指南和协作约定，保持现有中英文对应文档的规则一致。

## Capabilities

### New Capabilities

- `contribution-release-policy`: 提交类型与双语格式、AI 代码审计、分支贡献流程、四段版本和 Roadmap/Issue/PR 发布闭环，以及文档入口的一致性。

### Modified Capabilities

无。新增协作规范，不重写历史 README 规范中的安装和架构要求。

## Impact

- 实施范围：`README.md`、`README.zh-CN.md`、`docs/开发指南.md`、`docs/development.md`、`AGENTS.md`、`AGENTS.en.md`，以及本次根项目 OpenSpec 文档。
- 不修改业务代码、实际版本号、Git 分支或远端保护设置，不新增 CI，不创建实际 Issue、PR 或发布。
- `.agents/` 保持本地忽略状态，本变更不修改或提交本地 skill。
- 纯文档变更以规则一致性、示例、相对链接、格式和 OpenSpec 严格校验验收；单元测试、代码覆盖率和运行时构建不适用。
