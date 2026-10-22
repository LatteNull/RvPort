## ADDED Requirements

### Requirement: API E2E 必须覆盖构建验证模块
API E2E SHALL 提供可单独运行的构建验证模块，并覆盖正常流程、异常流程和 edge case。

#### Scenario: 构建验证正常流程
- **WHEN** E2E 运行构建验证模块
- **THEN** 测试 SHALL 创建项目、源码版本、环境和成功源码部署记录
- **AND** 测试 SHALL 通过 API 创建构建验证任务
- **AND** 测试 SHALL 等待任务完成并校验 `build_runs.status`、退出码、任务详情和日志可查询

#### Scenario: 构建验证异常流程
- **WHEN** E2E 使用失败源码部署、跨项目源码部署或无权限会话创建构建验证
- **THEN** 后端 SHALL 返回明确错误
- **AND** 测试 SHALL 校验没有创建构建任务、构建运行或队列消息

#### Scenario: 构建验证 edge case
- **WHEN** E2E 提交空脚本、重复源码部署 ID、非法分页排序参数或非零退出码脚本
- **THEN** 后端 SHALL 返回参数错误或稳定失败状态
- **AND** 测试 SHALL 校验错误响应和数据库状态符合预期

#### Scenario: 构建验证清理
- **WHEN** E2E 构建验证模块结束
- **THEN** 清理脚本 SHALL 删除测试创建的项目、任务、构建运行、脚本 payload、日志、源码部署记录和相关运行目录
