## ADDED Requirements

### Requirement: API E2E 必须覆盖依赖自动修复
API E2E 测试套件 SHALL 覆盖依赖自动修复候选项、任务创建、远端安装、修复结果查询、自动重跑依赖分析、异常流程和 edge case。

#### Scenario: 覆盖自动修复正常流程
- **WHEN** E2E 准备一个包含中风险可安装依赖的依赖分析结果
- **THEN** E2E SHALL 调用候选项查询 API
- **AND** E2E SHALL 验证中风险候选项 `defaultSelected=true`
- **AND** E2E SHALL 调用创建自动修复 API
- **AND** E2E SHALL 等待 `DEPENDENCY_AUTO_FIX` 任务进入终态
- **AND** E2E SHALL 验证修复运行、修复条目、任务事件和任务日志副作用

#### Scenario: 覆盖高风险默认不选中
- **WHEN** E2E 准备一个高风险且存在 `sourceProviderPackage` 的依赖分析结果
- **THEN** 候选项查询 SHALL 返回该条目
- **AND** 该条目 SHALL 设置 `defaultSelected=false`
- **AND** E2E SHALL 验证只有显式提交该条目时才会创建安装计划

#### Scenario: 覆盖自动重跑依赖分析
- **WHEN** 自动修复任务至少有一个条目安装成功或已满足
- **THEN** E2E SHALL 验证后端创建新的 `DEPENDENCY_ANALYSIS` 任务
- **AND** E2E SHALL 等待新依赖分析进入终态或验证其任务已被正确入队
- **AND** E2E SHALL 验证自动修复运行记录中保存重跑分析 ID 和任务 ID

#### Scenario: 覆盖越权访问
- **WHEN** 普通用户尝试查询或创建其他项目的依赖自动修复
- **THEN** E2E SHALL 验证 API 返回拒绝访问或资源不存在
- **AND** 后端 MUST NOT 创建修复运行、修复条目或任务

#### Scenario: 覆盖非法候选项
- **WHEN** E2E 使用不可自动修复的 result item 创建修复任务
- **THEN** API SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 执行远端安装命令

#### Scenario: 覆盖安装失败和清理
- **WHEN** E2E 模拟目标包管理器失败、包不存在或不支持的 package manager
- **THEN** 自动修复运行 SHALL 进入失败或部分失败终态
- **AND** 修复条目 SHALL 保存失败状态和脱敏错误摘要
- **AND** E2E 清理脚本 SHALL 清理测试项目、任务、修复运行、修复条目和远端测试包副作用
