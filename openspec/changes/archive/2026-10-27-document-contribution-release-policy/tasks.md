## 1. 完整协作规范

- [x] 1.1 在 `docs/开发指南.md` 增加七种提交类型的用途，以及 `Type: Message` 的双语标题和正文示例，包含 `docs`。
- [x] 1.2 在开发指南补充 AI 代码审计、fork/clone/主题分支/PR 到上游 `dev` 的流程与 `master` 发布职责。
- [x] 1.3 在开发指南补充四段版本及 `rc1`/`rc2` 示例，完整描述 Roadmap、Issue、负责人、PR、验收关闭和发布流程。
- [x] 1.4 同步 `docs/development.md` 对应英文内容，核对七种类型、分支方向和版本示例一致。

## 2. 项目入口与协作约定

- [x] 2.1 更新 `README.zh-CN.md` 和 `README.md`，提供五项规则摘要及对应开发指南链接。
- [x] 2.2 更新 `AGENTS.md` 和 `AGENTS.en.md`，同步提交、审计、分支与发布核心约束及指南链接，保留既有 Docker 和代码质量要求。

## 3. 文档验收

- [x] 3.1 逐项核对 delta spec 场景、中英文一致性、七种类型、双语示例、四段版本及 Issue 完成条件；记录实际检查结果。
- [x] 3.2 检查六份文档新增相对链接与锚点可达，运行 `git diff --check`，确认修改仅涉及计划内文档及本次 OpenSpec 内容。
- [x] 3.3 从 `D:/projects/RvPort` 运行 `openspec validate document-contribution-release-policy --strict`；记录纯文档的单元测试、覆盖率与运行时构建不适用，完成后给出下一阶段命令，等待用户要求 sync/archive。
