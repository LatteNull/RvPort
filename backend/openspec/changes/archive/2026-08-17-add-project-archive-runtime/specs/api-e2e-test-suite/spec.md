## ADDED Requirements

### Requirement: E2E 必须覆盖项目归档节点
API E2E 测试套件 SHALL 提供独立归档模块，覆盖归档当前状态、源码版本隔离、归档详情和归档包下载。

#### Scenario: 归档已有候选内容
- **WHEN** E2E 创建项目、激活源码版本并准备可归档候选
- **THEN** 测试 SHALL 调用归档当前状态 API
- **AND** 测试 SHALL 等待归档任务成功
- **AND** 测试 SHALL 验证归档 overview、列表和详情包含本次候选内容

#### Scenario: 下载归档包
- **WHEN** 归档任务成功
- **THEN** E2E SHALL 调用归档包下载 API
- **AND** 测试 SHALL 验证压缩包包含 `manifest.json`、`summary.json` 和候选引用的报告文件
- **AND** 测试 SHALL 验证响应和归档 manifest 不暴露服务器真实路径或对象存储内部 key

#### Scenario: 新源码版本隔离
- **WHEN** E2E 激活第二个源码版本但不为该版本登记候选
- **THEN** 再次归档当前状态 MUST NOT 包含第一个源码版本的候选内容
- **AND** 测试 SHALL 验证旧归档详情仍能查看第一个源码版本的归档项

#### Scenario: 越权访问归档
- **WHEN** 普通用户访问其他项目的归档 overview、列表、详情、单项内容或下载接口
- **THEN** E2E SHALL 验证后端返回访问拒绝错误
- **AND** 响应 MUST NOT 泄漏归档或项目是否存在
