# 贡献与发布规范

## Purpose

统一 RvPort 的双语提交信息、AI 代码审计、开发与发布分支、四段版本命名，以及 Roadmap、Issue 和 PR 的协作流程，并保持项目文档入口一致。

## Requirements

### Requirement: 提交类型与双语信息
开发规范 SHALL 使用 `Type: Message` 格式，标题具体为 `<type>: <English> / <中文>`，类型限定为 `feat`、`test`、`fix`、`refactor`、`ci`、`chconf`、`docs`，并提供类型含义及英文、中文正文示例。

#### Scenario: 文档变更选择提交类型
- **WHEN** 贡献者仅更新规范文档
- **THEN** 指南 SHALL 提供 `docs: Document contribution rules / 补充贡献规范` 一类双语示例
- **AND** SHALL 说明 `docs` 用于文档、`chconf` 用于非 CI 配置、`ci` 用于 CI/CD 配置
- **AND** SHALL 不把 `feature` 或 `config change` 作为可用提交类型

### Requirement: AI 生成代码接受同等审计
协作规范 SHALL 要求 AI 生成代码遵循与人工代码相同的审计和 PR 审查流程，检查正确性、风险及适用测试和验证证据，不因生成方式免审。

#### Scenario: 提交含 AI 代码的 PR
- **WHEN** PR 包含 AI 生成或修改的代码
- **THEN** 文档 SHALL 要求审查者完成代码审查并确认适用验证结果
- **AND** SHALL 明确自动检查通过不能代替代码审查

### Requirement: 开发与发布分支职责
规范 SHALL 指定 `dev` 为开发集成分支、`master` 为发布分支，并说明 fork、clone、主题分支、PR 到上游 `dev` 的贡献流程。

#### Scenario: 贡献者开始开发
- **WHEN** 开发者按照贡献指南提交修改
- **THEN** 指南 SHALL 要求先 fork 上游仓库并 clone 到本地，从上游 `dev` 创建主题分支
- **AND** SHALL 指导向个人 fork 推送并向上游 `dev` 发起 PR，经审查合并
- **AND** SHALL 不把直接推送 `master` 描述为日常开发流程

### Requirement: 四段版本命名
版本规范 SHALL 使用“大版本.小版本.bug fix.hotfix”四段数字，预发布版本追加连字符、类型及序号，并以 `rc1`、`rc2` 举例。

#### Scenario: 标记发布候选版本
- **WHEN** 阅读版本命名示例
- **THEN** 文档 SHALL 展示 `1.2.0.0-rc1`、`1.2.0.0-rc2` 和正式版本 `1.2.0.0`
- **AND** SHALL 不把四段命名描述为标准 SemVer

### Requirement: Roadmap 驱动 Issue 与发布
开发规范 SHALL 描述从 Roadmap 到 Issue、负责人、关联 PR、完成关闭和发布的完整流程。

#### Scenario: 交付一个计划阶段
- **WHEN** 下一阶段 Roadmap 确定
- **THEN** 团队 SHALL 创建具体 Issue 并指派负责人
- **AND** 开发 PR SHALL 关联对应 Issue，合并至 `dev` 并完成验收后关闭 Issue
- **AND** 文档 SHALL 提醒确认 Issue 关闭状态，不假定面向 `dev` 的 PR 自动关闭 Issue
- **AND** Roadmap 整体完成后 SHALL 通过发布 PR 将 `dev` 合并到 `master` 并发布

### Requirement: 规范入口一致且可校验
根目录中英文 README、开发指南和 AGENTS SHALL 对上述规则保持一致；开发指南承载详情，README 和 AGENTS 提供摘要与有效相对链接。

#### Scenario: 从项目入口查找协作约定
- **WHEN** 贡献者阅读任一语言的根 README
- **THEN** SHALL 能看到提交、审计、分支、版本及 Roadmap 规则摘要，并通过链接进入对应开发指南
- **AND** 文档校验 SHALL 检查新增链接、示例、格式与跨文档一致性
- **AND** 纯文档变更 SHALL 标注单元测试及代码覆盖率不适用，含可执行代码的变更仍遵守既有测试要求
