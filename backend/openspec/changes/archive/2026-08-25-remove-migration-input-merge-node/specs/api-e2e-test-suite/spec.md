## MODIFIED Requirements

### Requirement: E2E 测试必须覆盖迁移报告 API
API E2E 测试套件 SHALL 增加迁移报告模块，并 SHALL 覆盖正常流程、异常流程和 edge case。测试 SHALL 使用节点内确认后的迁移输入 reference，而不是依赖独立迁移输入合并节点。

#### Scenario: 正常生成迁移评估报告
- **WHEN** E2E 创建项目、创建源码版本、准备 KB 或依赖分析来源结果，并通过节点内确认规则产生至少一条 `CONFIRMED` reference
- **THEN** E2E SHALL 调用报告创建 API
- **AND** E2E SHALL 等待报告任务成功
- **AND** E2E SHALL 校验报告详情、报告输入快照、HTML 下载和 JSON 下载均可用
- **AND** E2E SHALL 校验报告输出制品已写入对象存储元数据

#### Scenario: 未确认输入生成失败
- **WHEN** E2E 在源码版本下只存在 `CANDIDATE` 或 `EXCLUDED` 迁移输入
- **THEN** 报告生成任务 SHALL 失败
- **AND** 失败错误 SHALL 表达没有 confirmed 输入

#### Scenario: 报告快照不可变
- **WHEN** E2E 成功生成报告后修改原迁移输入状态或备注
- **THEN** 后续查询报告输入快照和下载 JSON 报告 SHALL 保持生成时内容不变

#### Scenario: 越权访问报告失败
- **WHEN** E2E 使用普通用户访问其他用户项目的报告详情、输入快照或下载接口
- **THEN** API SHALL 返回访问拒绝

#### Scenario: 非法报告下载格式
- **WHEN** E2E 调用报告下载接口并提交不支持的 `format`
- **THEN** API SHALL 返回明确业务错误

## ADDED Requirements

### Requirement: E2E 测试必须覆盖节点内迁移输入确认
API E2E 测试套件 SHALL 覆盖 KB 和依赖分析节点内确认、撤回和默认风险规则。

#### Scenario: 默认确认高中风险和说明类结果
- **WHEN** E2E 准备 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT` 来源结果
- **THEN** 对应 migration input reference SHALL 默认为 `CONFIRMED`

#### Scenario: 默认低风险候选
- **WHEN** E2E 准备 `LOW` 来源结果
- **THEN** 对应 migration input reference SHALL 默认为 `CANDIDATE`
- **AND** 报告生成 MUST NOT 默认使用该结果

#### Scenario: 人工加入低风险
- **WHEN** E2E 将 `LOW` reference 更新为 `CONFIRMED`
- **THEN** 报告生成 SHALL 可以使用该结果

#### Scenario: 人工撤回默认确认结果
- **WHEN** E2E 将默认 `CONFIRMED` reference 更新为 `EXCLUDED`
- **THEN** 报告生成 MUST NOT 使用该结果

#### Scenario: 新流程不导入 SBOM
- **WHEN** E2E 尝试在新流程中导入 `SBOM_RESULT`
- **THEN** API SHALL 返回 deprecated 或拒绝响应
- **AND** 后端 MUST NOT 创建新的 `SBOM_RESULT` migration input reference
