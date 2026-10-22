## ADDED Requirements

### Requirement: KB Scanner 必须从 compile database 生成构建命令 finding
KB 扫描运行时 SHALL 在使用 compile database 时，将真实编译命令中明确的 x86/SIMD 编译参数和命令行宏转换为可入库的 KB finding。

#### Scenario: x86 编译参数生成 finding
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** `kb_scan_runs.summary.compileCommands.mode=USED`
- **AND** compile database 中的真实编译命令包含明确 x86/SIMD 编译参数
- **THEN** KB Scanner SHALL 为这些参数生成 finding
- **AND** finding SHALL 使用稳定 rule id、severity、title、description、suggestion 和 fingerprint
- **AND** finding evidence SHALL 标记来源为 compile command

#### Scenario: 命令行宏生成 finding
- **WHEN** compile database 中的真实编译命令包含明确启用 x86/SIMD 路径的 `-D` 宏
- **THEN** KB Scanner SHALL 为该宏生成 finding 或附加到对应 finding evidence
- **AND** finding evidence SHALL 保存宏名、宏值摘要、关联源码相对路径和 compile command 索引
- **AND** scanner MUST NOT 将普通项目宏仅因名称格式相似就误判为 x86/SIMD 风险

#### Scenario: arguments 和 command 字段兼容
- **WHEN** compile database entry 提供 `arguments` 数组
- **THEN** KB Scanner SHALL 优先基于 `arguments` 解析 token
- **WHEN** compile database entry 只提供 `command` 字符串
- **THEN** KB Scanner SHALL 使用 shell-like 解析提取 token
- **AND** 解析失败 SHALL 记录 warning 并继续扫描其他 entry

#### Scenario: compile database 不得减少源码 finding
- **WHEN** KB Scanner 使用 compile database 执行扫描
- **THEN** scanner SHALL 保留默认源码扫描 finding
- **AND** scanner MUST NOT 仅因为某个源码、头文件或构建文件没有出现在 compile database 顶层 `file` 字段中而隐藏该 finding
- **AND** compile database SHALL 只能补充上下文、可达性信息或新增构建命令 finding

#### Scenario: 过滤未参与本次构建的配置项
- **WHEN** 仓库中存在 CMake、Meson、Ninja、Make 或 rpmbuild 配置文件
- **AND** 本次 compile database 没有真实执行对应工具或没有关联项目源码 entry
- **THEN** KB Scanner MUST NOT 仅因为配置文件存在就生成 compile command finding

#### Scenario: 过滤内部探测和越界命令
- **WHEN** compile database entry 的 `file` 不在当前源码版本工作副本内
- **OR** entry 命中 scanner 排除目录、排除文件或构建系统内部探测文件
- **THEN** KB Scanner MUST NOT 为该 entry 生成 compile command finding
- **AND** scanner MAY 在 diagnostics 中记录被过滤的安全原因码

#### Scenario: finding evidence 安全边界
- **WHEN** compile command 派生 finding 被写入数据库、API 响应、artifact 或任务日志
- **THEN** evidence MUST NOT 暴露服务器真实路径、远端绝对路径、compile database 临时路径、对象存储 key、凭据、token 或私钥
- **AND** evidence SHALL 使用源码相对路径和脱敏命令摘要表达命中位置

#### Scenario: 同源 finding 去重
- **WHEN** 同一次扫描中多个 compile database entry 产生相同 `sourceKind + ruleId + relativePath + token` 的 finding
- **THEN** KB Scanner SHALL 对同源 finding 做稳定去重
- **AND** 去重后的 finding evidence SHALL 保留可审计的命中次数或命中 entry 摘要
- **AND** scanner MUST NOT 因重复命中导致整次扫描失败

#### Scenario: 源码已命中的构建参数不重复展示
- **WHEN** 默认源码或构建文件扫描已经产出某个构建参数风险 finding
- **AND** compile database 中的真实编译命令也包含同一个风险 token
- **THEN** KB Scanner MUST NOT 再生成另一条用于展示的 compile command finding
- **AND** Scanner SHALL 将 compile command 的命中 token、token 类型、entry index 和脱敏命令摘要合并到已有 finding evidence 或使用稳定 fingerprint 保证导入后只有一条展示记录
- **AND** 该合并 MUST NOT 删除已有源码 finding 的 rule、severity、位置、描述或建议
