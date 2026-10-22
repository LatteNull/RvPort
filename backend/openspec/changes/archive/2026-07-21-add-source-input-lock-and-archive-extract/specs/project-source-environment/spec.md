## ADDED Requirements

### Requirement: 项目必须在首次成功源码入库后锁定源码来源
后端 SHALL 在项目级记录源码来源锁定状态，并 SHALL 防止同一项目混用压缩包上传和 Git 同步两种源码入库方式。

#### Scenario: 新项目尚未锁定源码来源
- **WHEN** 已登录用户创建新项目
- **THEN** 后端 SHALL 将项目源码来源锁定字段保存为空
- **AND** 后端 SHALL 允许该项目后续选择压缩包上传或 Git 同步作为首次源码入库方式

#### Scenario: 压缩包首次成功入库后锁定 ARCHIVE
- **WHEN** 项目源码来源尚未锁定
- **AND** 用户通过 `POST /api/projects/{projectId}/sources/archive` 成功上传、校验并解包源码包
- **THEN** 后端 SHALL 将项目源码来源锁定为 `ARCHIVE`
- **AND** 后端 SHALL 创建 `revision_type=ARCHIVE` 的源码版本
- **AND** 后端 SHALL 创建 `input_type=ARCHIVE` 且 `status=SUCCEEDED` 的导入记录

#### Scenario: Git 首次成功同步后锁定 GIT
- **WHEN** 项目源码来源尚未锁定
- **AND** `SOURCE_GIT_SYNC` worker 成功完成 Git clone 或 fetch checkout
- **THEN** 后端 SHALL 将项目源码来源锁定为 `GIT`
- **AND** 后端 SHALL 创建 `revision_type=GIT` 的源码版本
- **AND** 后端 SHALL 将对应导入记录更新为 `SUCCEEDED`

#### Scenario: 失败入库不锁定源码来源
- **WHEN** 压缩包保存、格式校验、解包、源码结构校验或 Git 同步失败
- **THEN** 后端 MUST NOT 将空源码来源锁定字段写为 `ARCHIVE` 或 `GIT`
- **AND** 后端 MUST NOT 创建成功态源码版本

#### Scenario: 拒绝与锁定来源不一致的压缩包上传
- **WHEN** 项目源码来源已锁定为 `GIT`
- **AND** 用户调用 `POST /api/projects/{projectId}/sources/archive`
- **THEN** 后端 SHALL 返回 `SOURCE_INPUT_TYPE_LOCKED` 错误
- **AND** 后端 MUST NOT 保存上传文件、解包源码、创建源码版本或创建成功导入记录

#### Scenario: 拒绝与锁定来源不一致的 Git 同步
- **WHEN** 项目源码来源已锁定为 `ARCHIVE`
- **AND** 用户调用 `POST /api/projects/{projectId}/sources/git-sync`
- **THEN** 后端 SHALL 返回 `SOURCE_INPUT_TYPE_LOCKED` 错误
- **AND** 后端 MUST NOT 创建 Git 同步任务、创建导入记录或投递队列消息

### Requirement: 压缩包源码上传必须自动解包到源码运行目录
后端 SHALL 在压缩包上传成功后自动解包源码包，并 SHALL 将解包后的源码目录作为源码版本工作副本保存。

#### Scenario: 支持指定压缩包格式
- **WHEN** 用户上传源码压缩包
- **THEN** 后端 SHALL 支持 `zip`、`rar`、`7z`、`tar.gz`、`tgz`、`tar.xz` 和 `gzip`
- **AND** 后端 SHALL 对不支持的格式返回 `SOURCE_ARCHIVE_UNSUPPORTED_FORMAT`

#### Scenario: 解包到独立源码目录
- **WHEN** 源码压缩包格式有效且内容校验通过
- **THEN** 后端 SHALL 将源码解包到独立运行目录
- **AND** 运行目录 SHALL 与 `projectId` 和 `sourceRevisionId` 绑定
- **AND** `source_revisions.working_copy_path` SHALL 保存该运行目录作为内部字段
- **AND** API 响应 MUST NOT 返回该服务器本地路径

#### Scenario: 保存原始压缩包和解包目录
- **WHEN** 压缩包源码上传成功
- **THEN** 后端 SHALL 保存原始上传包到受控上传目录
- **AND** `source_revisions.archive_path` SHALL 保存原始上传包路径作为内部字段
- **AND** `source_revisions.working_copy_path` SHALL 保存解包后的源码工作副本路径

#### Scenario: gzip 单文件压缩结构校验
- **WHEN** 用户上传单文件 `gzip` 源码包
- **THEN** 后端 SHALL 解压出单个文件
- **AND** 后端 SHALL 校验该文件或其所在目录满足源码输入最小结构要求
- **AND** 如果无法形成可用源码输入，后端 SHALL 返回 `SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE`

#### Scenario: 防止压缩包路径逃逸
- **WHEN** 压缩包 entry 包含绝对路径、`..` 路径段或 normalize 后逃逸目标目录的路径
- **THEN** 后端 SHALL 拒绝该压缩包并返回 `SOURCE_ARCHIVE_UNSAFE_PATH`
- **AND** 后端 MUST NOT 将逃逸文件写入目标目录之外
- **AND** 后端 MUST 尽力清理本次临时解包目录

#### Scenario: 拒绝空源码包
- **WHEN** 压缩包为空、只包含目录或解包后没有可用文件
- **THEN** 后端 SHALL 返回 `SOURCE_ARCHIVE_EMPTY`
- **AND** 后端 MUST NOT 创建成功态源码版本

#### Scenario: 修复后再次上传同来源源码
- **WHEN** 项目源码来源已锁定为 `ARCHIVE`
- **AND** 用户再次上传修复后的有效源码包
- **THEN** 后端 SHALL 创建新的 `ARCHIVE` 源码版本
- **AND** 后端 MUST NOT 覆盖旧源码版本记录或旧源码工作目录

#### Scenario: 修复后再次 Git 同步同来源源码
- **WHEN** 项目源码来源已锁定为 `GIT`
- **AND** 用户再次创建 Git 同步任务
- **THEN** 后端 SHALL 允许创建新的 Git 同步任务
- **AND** worker 成功后 SHALL 创建新的 `GIT` 源码版本
- **AND** 后端 MUST NOT 覆盖旧源码版本记录或旧源码工作目录
