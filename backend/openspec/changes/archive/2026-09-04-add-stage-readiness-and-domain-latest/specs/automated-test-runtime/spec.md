## ADDED Requirements

### Requirement: 自动化测试必须提供 latest
自动化测试领域 SHALL 提供当前 Context 下的 latest 接口，返回最新测试批次和测试结果比较摘要。

#### Scenario: 查询自动化测试 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/automated-tests/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `execution` SHALL 指向当前源码版本和当前运行环境版本下最新自动化测试批次
- **AND** `result` SHALL 包含 x86 与 RISC-V 测试运行摘要、日志入口、报告目标和最近测试结果比较摘要

#### Scenario: 自动化测试 latest 无比较结果
- **WHEN** 自动化测试已完成但模型或 agent 配置不可用导致比较未执行
- **THEN** latest SHALL 仍返回测试执行结果
- **AND** `result` SHALL 明确比较不可用原因

### Requirement: 自动化测试 readiness 必须依赖构建验证
项目级 readiness 在 `stageId=test` 时 SHALL 返回自动化测试所需的构建验证前置条件。

#### Scenario: 构建验证已成功
- **WHEN** 当前 Context 下存在成功的双环境构建验证
- **THEN** `BUILD_VALIDATION` prerequisite SHALL 返回 `SATISFIED`
- **AND** `referenceId` SHALL 指向构建验证记录或批次

#### Scenario: 构建验证缺失
- **WHEN** 当前 Context 下没有双环境构建验证记录
- **THEN** `BUILD_VALIDATION` prerequisite SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `BUILD_VALIDATION_MISSING`

#### Scenario: 构建验证失败
- **WHEN** 当前 Context 下最近一次双环境构建验证失败
- **THEN** `BUILD_VALIDATION` prerequisite SHALL 返回 `FAILED`
- **AND** `reasonCode` SHALL 为 `BUILD_VALIDATION_FAILED`
