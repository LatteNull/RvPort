## ADDED Requirements

### Requirement: 源码版本创建后必须隔离迁移输入
项目源码管理 SHALL 保证每个成功创建的源码版本拥有独立迁移输入作用域。

#### Scenario: 压缩包源码入库后迁移输入为空
- **WHEN** 用户通过压缩包上传成功创建新的 `source_revision`
- **THEN** 后端 SHALL 为该源码版本提供空迁移输入集合
- **AND** 后端 MUST NOT 复制上一源码版本迁移输入 reference

#### Scenario: Git 同步成功后迁移输入为空
- **WHEN** `SOURCE_GIT_SYNC` worker 成功创建新的 `source_revision`
- **THEN** 后端 SHALL 为该源码版本提供空迁移输入集合
- **AND** 后端 MUST NOT 复制上一源码版本迁移输入 reference

#### Scenario: 失败源码入库不创建迁移输入事实
- **WHEN** 压缩包上传、解包、源码结构校验或 Git 同步失败
- **THEN** 后端 MUST NOT 为失败入库创建可用迁移输入集合
- **AND** 后端 MUST NOT 改变当前 active source revision 的迁移输入集合
