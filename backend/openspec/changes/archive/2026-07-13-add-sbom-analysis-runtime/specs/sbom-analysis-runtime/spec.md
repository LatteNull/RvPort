## ADDED Requirements

### Requirement: SBOM 分析器必须作为独立 CLI 工具运行
系统 SHALL 在根目录 `tools/sbom-analyzer` 提供独立 SBOM 分析 CLI，Java 后端通过受控进程调用该工具，工具不得直接连接远程环境或读取后端数据库。

#### Scenario: Java 后端调用分析器
- **WHEN** worker 执行 `SBOM_ANALYSIS` 任务
- **THEN** 后端 SHALL 将环境快照和组件清单导出为分析器输入 JSON
- **AND** 后端 SHALL 以受控进程调用 `tools/sbom-analyzer`
- **AND** 后端 SHALL 从分析器输出 JSON 导入 SBOM 结果

#### Scenario: 分析器不访问远程环境
- **WHEN** 分析器执行替代分析
- **THEN** 分析器 MUST NOT 建立 SSH 连接
- **AND** 分析器 MUST NOT 解密或读取 Git/SSH 凭据
- **AND** 分析器 MUST NOT 直接查询后端 PostgreSQL

#### Scenario: 分析器失败
- **WHEN** 分析器返回非零退出码、输出 JSON 缺失或输出 JSON 无法解析
- **THEN** worker SHALL 将 `SBOM_ANALYSIS` 任务标记为 `FAILED`
- **AND** 后端 SHALL 保存 tool run、stdout/stderr 日志和安全错误摘要
- **AND** 后端 MUST NOT 写入成功态 SBOM 结果

### Requirement: SBOM 分析器输入输出必须使用稳定 JSON 契约
SBOM 分析器 SHALL 使用版本化 JSON 输入和输出，使 Java 后端可以稳定导出、调用和导入。

#### Scenario: 生成分析器输入
- **WHEN** Java 后端准备调用分析器
- **THEN** 输入 JSON SHALL 包含 `schemaVersion`、项目信息、运行信息、源环境、目标环境、源快照、目标快照、源组件、目标已安装组件、目标仓库组件和分析选项
- **AND** 输入 JSON MUST NOT 包含明文凭据、服务器真实绝对路径或任务完整日志

#### Scenario: 读取分析器输出
- **WHEN** 分析器成功完成
- **THEN** 输出 JSON SHALL 包含 `schemaVersion`、`summary`、`components`、`replacementCandidates`、`warnings` 和 `tool`
- **AND** `replacementCandidates` SHALL 为每个源侧组件给出替代结论或明确无候选结论
- **AND** 输出 JSON MUST NOT 包含明文凭据或服务器真实绝对路径

#### Scenario: 版本不兼容
- **WHEN** 分析器输出的 `schemaVersion` 不被 Java 后端支持
- **THEN** worker SHALL 将任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表示分析器结果版本不兼容

### Requirement: SBOM 分析必须比较源侧依赖和目标侧可替代能力
SBOM 分析 SHALL 基于源侧已安装组件和目标侧已安装及仓库可用组件生成替代候选和风险。

#### Scenario: 目标侧已安装组件可满足源侧组件
- **WHEN** 源侧组件在目标已安装组件中存在可匹配项
- **THEN** 分析结果 SHALL 生成 `TARGET_PRESENT` 替代结论
- **AND** 候选项 SHALL 包含匹配类型、候选名称、版本、架构和证据摘要

#### Scenario: 目标仓库存在可安装候选
- **WHEN** 源侧组件未在目标已安装组件中命中但在目标仓库组件中存在候选
- **THEN** 分析结果 SHALL 生成 `DIRECT_AVAILABLE` 或 `UPGRADE_AVAILABLE` 替代结论
- **AND** 候选项 SHALL 标记来源为仓库清单

#### Scenario: 只能源码构建或人工确认
- **WHEN** 源侧组件无法从目标已安装组件或目标仓库组件中直接匹配
- **THEN** 分析结果 SHALL 生成 `SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE` 或 `MANUAL_CONFIRM_REQUIRED` 结论
- **AND** 结果 SHALL 给出可展示的建议说明和风险等级

### Requirement: Java SBOM runtime 必须持久化分析运行和结果
Java SBOM runtime SHALL 创建并更新 `sbom_runs`，并将分析器结果导入 `sbom_components` 和 `replacement_candidates`。

#### Scenario: 创建 SBOM 运行记录
- **WHEN** 用户创建 SBOM 分析任务
- **THEN** 后端 SHALL 创建 `SBOM_ANALYSIS` 任务
- **AND** 后端 SHALL 创建或准备关联该任务的 `sbom_runs` 运行记录
- **AND** `sbom_runs` SHALL 引用项目、源环境、目标环境、源快照、目标快照和任务 ID

#### Scenario: 导入组件结果
- **WHEN** 分析器成功输出组件结果
- **THEN** 后端 SHALL 写入 `sbom_components`
- **AND** 源侧组件 SHALL 使用 `environment_side=SOURCE`
- **AND** 目标侧或候选组件 SHALL 使用 `environment_side=TARGET` 或 `CANDIDATE`
- **AND** 每个组件 SHALL 具备稳定 `fingerprint`

#### Scenario: 导入替代候选
- **WHEN** 分析器成功输出替代候选
- **THEN** 后端 SHALL 写入 `replacement_candidates`
- **AND** 每个候选 SHALL 关联对应源侧 `sbom_components`
- **AND** `replacement_status` SHALL 使用既有数据库枚举值

### Requirement: SBOM 分析必须配套测试覆盖
SBOM 分析相关实现 SHALL 配套 Java 单元测试、分析器测试和 API E2E 测试，并覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖创建分析任务、导出输入、调用分析器、导入结果、查询列表、查询详情和查询组件结果

#### Scenario: 覆盖异常流程
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖快照不存在、环境不属于项目、分析器退出失败、输出 JSON 无效、输出版本不兼容和结果导入失败

#### Scenario: 覆盖 edge case
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖空组件清单、同名不同版本组件、同名不同架构组件、仓库候选重复、`.so` 仅名称匹配、输出过大和日志脱敏
