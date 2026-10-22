## ADDED Requirements

### Requirement: E2E 测试必须覆盖迁移报告 API
API E2E 测试套件 SHALL 增加迁移报告模块，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常生成迁移评估报告
- **WHEN** E2E 创建项目、创建源码版本、写入 KB/SBOM 来源结果、导入迁移输入并确认其中至少一条
- **THEN** E2E SHALL 调用报告创建 API
- **AND** E2E SHALL 等待报告任务成功
- **AND** E2E SHALL 校验报告详情、报告输入快照、HTML 下载和 JSON 下载均可用
- **AND** E2E SHALL 校验报告输出制品已写入对象存储元数据
- **AND** API 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 未确认输入生成失败
- **WHEN** E2E 在源码版本下只存在 `CANDIDATE` 或 `EXCLUDED` 迁移输入
- **THEN** 报告生成任务 SHALL 失败
- **AND** 失败错误 SHALL 表达没有 confirmed 输入

#### Scenario: 报告快照不可变
- **WHEN** E2E 成功生成报告后修改原迁移输入状态或备注
- **THEN** 后续查询报告输入快照和下载 JSON 报告 SHALL 保持生成时内容不变

#### Scenario: 越权访问报告失败
- **WHEN** E2E 使用普通用户访问其他用户项目的报告详情、输入快照或下载接口
- **THEN** 后端 SHALL 拒绝访问

#### Scenario: 非法下载格式失败
- **WHEN** E2E 调用报告下载接口并提交不支持的 `format`
- **THEN** 后端 SHALL 返回统一业务错误
