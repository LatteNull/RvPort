## ADDED Requirements

### Requirement: 源码压缩包输入必须具备可配置的大文件上传能力
源码管理能力 SHALL 将源码压缩包上传上限作为部署配置管理，默认支持最大 10GB 的源码包输入。

#### Scenario: 默认大文件上传上限
- **WHEN** 后端使用默认配置启动
- **THEN** multipart 单文件大小上限 SHALL 为 10GB
- **AND** multipart 请求总大小上限 SHALL 为 10GB
- **AND** 后端 MUST NOT 使用 Spring/Tomcat 默认 1MiB 限制作为源码包上传上限

#### Scenario: 部署时调整上传上限
- **WHEN** 运维通过环境变量配置上传大小上限
- **THEN** 后端 SHALL 使用配置值作为 multipart 单文件和请求总大小上限
- **AND** 源码上传 API SHALL 遵循该配置进行请求接收

#### Scenario: 大文件上传仍遵循源码来源锁定
- **WHEN** 项目源码来源已锁定为 `GIT`
- **AND** 用户上传任意大小的源码压缩包
- **THEN** 后端 SHALL 返回 `SOURCE_INPUT_TYPE_LOCKED`
- **AND** 后端 MUST NOT 保存上传文件、解包源码或创建源码版本

### Requirement: Git 源码输入必须规范化常见仓库 URL
Git 源码输入 SHALL 在创建源码导入任务前规范化常见仓库 URL，减少用户输入是否带 `.git` 后缀造成的行为差异。

#### Scenario: 规范化 HTTP(S) 仓库 URL
- **WHEN** Git 源码输入为 HTTP(S) URL 且 path 最后一段未以 `.git` 结尾
- **THEN** 后端 SHALL 去除末尾 `/` 并追加 `.git`
- **AND** `source_imports` 关联任务 input snapshot SHALL 使用规范化后的 URL
- **AND** 后续 `source_revisions.git_url` SHALL 保存规范化后的 URL

#### Scenario: 规范化 SSH scp 仓库 URL
- **WHEN** Git 源码输入为 SSH scp 风格 URL 且仓库路径未以 `.git` 结尾
- **THEN** 后端 SHALL 去除末尾 `/` 并追加 `.git`
- **AND** Git worker SHALL 使用规范化后的 URL 执行 clone

#### Scenario: 不重复追加 .git
- **WHEN** Git 源码输入已经以 `.git` 结尾
- **THEN** 后端 SHALL 保持 URL 不变
- **AND** 后端 MUST NOT 生成 `.git.git` 形式的 URL

#### Scenario: 保留 Git URL 安全边界
- **WHEN** Git 源码输入包含 HTTP(S) 内嵌凭据
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建源码导入记录、任务、凭据或审计中的敏感 URL
