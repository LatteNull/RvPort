## MODIFIED Requirements

### Requirement: SBOM 分析器必须作为独立 CLI 工具运行
系统 SHALL 在根目录 `tools/sbom-analyzer` 提供独立 SBOM 分析 CLI，Java 后端通过受控进程调用该工具。Java 后端 SHALL 在调用分析器前准备本轮环境快照；分析器本身不得直接连接远程环境或读取后端数据库。

#### Scenario: Java 后端调用分析器
- **WHEN** worker 执行 `SBOM_ANALYSIS` 任务
- **THEN** 后端 SHALL 先为源环境和目标环境生成本轮环境快照
- **AND** 后端 SHALL 将环境快照和组件清单导出为分析器输入 JSON
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

### Requirement: Java SBOM runtime 必须持久化分析运行和结果
Java SBOM runtime SHALL 创建并更新 `sbom_runs`，在同一任务中完成源/目标环境采集，回填快照 ID，并将分析器结果导入 `sbom_components` 和 `replacement_candidates`。

#### Scenario: 创建 SBOM 运行记录
- **WHEN** 用户创建 SBOM 分析任务
- **THEN** 后端 SHALL 创建 `SBOM_ANALYSIS` 任务
- **AND** 后端 SHALL 创建或准备关联该任务的 `sbom_runs` 运行记录
- **AND** `sbom_runs` SHALL 引用项目、源环境、目标环境和任务 ID
- **AND** `sbom_runs.source_snapshot_id` 和 `sbom_runs.target_snapshot_id` MAY 在采集完成前为空
- **AND** 后端 SHALL 使用默认全量采集范围和默认仓库策略，不依赖前端提交分析选项

#### Scenario: SBOM 任务内部采集环境
- **WHEN** worker 开始执行 `SBOM_ANALYSIS` 任务
- **THEN** worker SHALL 将 SBOM 运行标记为 `RUNNING`
- **AND** worker SHALL 先采集源环境并保存源快照和组件清单
- **AND** worker SHALL 再采集目标环境并保存目标快照和组件清单
- **AND** worker SHALL 将新生成的源快照 ID 和目标快照 ID 回填到 `sbom_runs`
- **AND** worker SHALL 只基于本轮生成的快照构造分析器输入

#### Scenario: 源环境采集失败
- **WHEN** `SBOM_ANALYSIS` 任务中的源环境采集失败
- **THEN** worker SHALL 将 SBOM 运行和任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表达失败阶段为 `SOURCE_COLLECT`
- **AND** worker MUST NOT 调用 SBOM 分析器

#### Scenario: 目标环境采集失败
- **WHEN** `SBOM_ANALYSIS` 任务中的目标环境采集失败
- **THEN** worker SHALL 将 SBOM 运行和任务标记为 `FAILED`
- **AND** 失败摘要 SHALL 表达失败阶段为 `TARGET_COLLECT`
- **AND** 已生成的源环境快照 MAY 保留供审计
- **AND** worker MUST NOT 调用 SBOM 分析器

#### Scenario: 任务取消
- **WHEN** 用户取消正在运行的 `SBOM_ANALYSIS` 任务
- **THEN** worker SHALL 尝试中止当前 SSH 采集命令或本地分析器进程
- **AND** worker SHALL 将 SBOM 运行标记为 `CANCELLED`
- **AND** 已完成的快照 MAY 保留供审计，但 MUST NOT 写入成功态 SBOM 结果

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
- **THEN** 测试 SHALL 覆盖创建分析任务、源环境采集、目标环境采集、快照回填、导出输入、调用分析器、导入结果、查询列表、查询详情和查询组件结果

#### Scenario: 覆盖异常流程
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖环境不存在、环境不属于项目、源环境采集失败、目标环境采集失败、分析器退出失败、输出 JSON 无效、输出版本不兼容和结果导入失败

#### Scenario: 覆盖 edge case
- **WHEN** 编写 SBOM 分析测试
- **THEN** 测试 SHALL 覆盖空组件清单、同名不同版本组件、同名不同架构组件、仓库候选重复、`.so` 仅名称匹配、采集中查询采集详情、取消时部分快照已生成、输出过大和日志脱敏
