## ADDED Requirements

### Requirement: API E2E 必须覆盖 ELF/SO provider package 版本匹配
API E2E 依赖分析模块 SHALL 覆盖 ELF/SO 到源环境 provider package、目标环境 provider package 和版本关系的端到端验证。

#### Scenario: 覆盖 provider package 正常匹配
- **WHEN** E2E 使用包含 ELF/SO 链接依赖的真实 C/C++ 项目完成 source-only 构建并创建依赖分析
- **THEN** 测试 SHALL 等待依赖分析任务成功
- **AND** 测试 SHALL 查询依赖分析结果列表和详情
- **AND** 至少一条 ELF/SO 相关结果 SHALL 包含 source owner package、source owner version、target provider package、target provider version、version relation 和 risk mapping evidence

#### Scenario: 覆盖目标版本关系风险映射
- **WHEN** E2E 或 test-support fixture 准备五类 ELF/SO provider 匹配场景
- **THEN** 测试 SHALL 验证 `SAME_MAJOR` 映射为 `INFO`
- **AND** 测试 SHALL 验证 `TARGET_NEWER` 映射为 `LOW`
- **AND** 测试 SHALL 验证 `TARGET_OLDER` 映射为 `HIGH`
- **AND** 测试 SHALL 验证 `TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED` 映射为 `MEDIUM`
- **AND** 测试 SHALL 验证 `NO_TARGET_VERSION_FOUND` 映射为 `CRITICAL`

#### Scenario: 覆盖 flag 和宏不进入依赖结果
- **WHEN** E2E 使用 CMake 项目产生 `compile_commands.json`、CMake compiler flag probe 宏和项目自定义宏
- **THEN** 依赖分析结果列表 MUST NOT 包含 `compile_database_define`、`strace_execve_define`、`compiler_flag_probe`、`compile-db` 或 `build-ninja` 类型结果
- **AND** 下载的 JSON 和 HTML 制品 MUST NOT 把这些内容展示为依赖结果项

#### Scenario: 覆盖 provider 结果去重聚合
- **WHEN** 同一个 source owner package 通过多个 ELF/SO 文件命中同一个 target provider package 和版本关系
- **THEN** 依赖分析结果列表 SHALL 只展示聚合后的 provider package 结果
- **AND** 单条结果详情 SHALL 保留所有参与聚合的源路径或 SONAME evidence

#### Scenario: 覆盖迁移输入导入展示
- **WHEN** E2E 将 ELF/SO provider package 依赖结果导入迁移输入
- **THEN** 迁移输入 SHALL 使用 `sourceType=DEPENDENCY_RESULT`
- **AND** `detectedLevel` SHALL 使用 `riskLevel + "/" + versionRelation`
- **AND** `locationLabel` SHALL 优先使用 `package:<name@version>`，源无 owner 时使用 `lib:<soname-or-path>`
