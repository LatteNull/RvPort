## ADDED Requirements

### Requirement: KB 扫描节点必须支持本节点确认进入报告
KB 扫描运行时 SHALL 支持在 KB 扫描节点内将 finding 加入、撤回或确认为报告输入。

#### Scenario: KB finding 默认确认
- **WHEN** KB 扫描任务成功写入 finding
- **AND** finding severity 归一化为 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT`
- **THEN** 后端 SHALL 创建或维护对应 `KB_FINDING` migration input reference
- **AND** reference 状态 SHALL 默认为 `CONFIRMED`

#### Scenario: KB finding 低风险默认候选
- **WHEN** KB 扫描任务成功写入 finding
- **AND** finding severity 归一化为 `LOW`
- **THEN** 后端 SHALL 创建或维护对应 `KB_FINDING` migration input reference
- **AND** reference 状态 SHALL 默认为 `CANDIDATE`

#### Scenario: KB 节点人工撤回
- **WHEN** 用户在 KB 扫描节点撤回某个 finding
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `EXCLUDED`
- **AND** 报告生成 MUST NOT 使用该 finding

#### Scenario: KB 节点人工加入低风险
- **WHEN** 用户在 KB 扫描节点人工加入 `LOW` finding
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `CONFIRMED`
- **AND** 报告生成 SHALL 可以使用该 finding
