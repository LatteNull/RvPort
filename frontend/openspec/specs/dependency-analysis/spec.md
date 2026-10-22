# dependency-analysis Specification

## Purpose

定义 rv-dependency-analysis 节点如何根据当前构建分析目标侧依赖、展示证据、安装候选包并选择报告输入。

## Requirements

### Requirement: 当前依赖分析与执行输入

依赖分析 SHALL 使用 `rv-dependency-analysis` readiness 和领域 latest，读取当前源码、源端构建和目标环境事实，不由历史首条推断当前分析。

#### Scenario: 创建分析

- **WHEN** 所需 readiness 条件满足且用户确认执行
- **THEN** 页面 SHALL 创建分析任务并展示提交反馈，后续状态由项目事件刷新
- **AND** 不满足条件时 SHALL 为缺失源码、环境或构建提供相应恢复入口

#### Scenario: 查看历史分析

- **WHEN** 用户打开历史列表或记录
- **THEN** 页面 SHALL 使用服务端分页和选中记录读取结果、证据与制品
- **AND** 历史结果 SHALL 保持只读，不影响当前执行资格

### Requirement: 依赖分析阶段详情

依赖分析 Drawer SHALL 以依赖分析结果为中心展示后端聚合、映射结果、制品和迁移输入入口。

#### Scenario: 展示依赖分析概览

- **WHEN** 依赖分析完成且存在结果
- **THEN** 系统 SHALL 展示分析依赖总数、风险分布和目标侧匹配分布
- **AND** 风险分布 SHALL 使用与知识库扫描一致的等级计数展示
- **AND** 风险分布与目标侧匹配 SHALL 在宽屏并列展示

#### Scenario: 展示依赖结果列表

- **WHEN** 用户查看依赖分析结果
- **THEN** 系统 SHALL 将依赖和风险列固定在左侧
- **AND** SHALL 映射风险、依赖类型和目标侧匹配状态
- **AND** SHALL NOT 在列表中展示置信度、版本证据或来源位置
- **AND** SHALL 在右侧固定操作列提供迁移输入操作

#### Scenario: 查看依赖结果详情

- **WHEN** 用户点击依赖名称打开详情
- **THEN** 系统 SHALL 打开二级依赖结果详情视图
- **AND** SHALL 提供返回依赖分析的图标入口
- **AND** SHALL 隐藏关闭按钮并禁止通过遮罩关闭 Drawer

### Requirement: 依赖分析必须提供受控自动修复入口

当前 Context 的成功依赖分析结果 MAY 提供自动修复操作，该操作 SHALL 只在当前 RISC-V 目标环境安装后端返回的候选软件包，不得暗示修改源码。

#### Scenario: 加载候选项

- **WHEN** 用户打开自动修复
- **THEN** frontend SHALL 请求 GET `/api/dependency-analyses/{analysisId}/auto-fix-candidates`
- **AND** 默认选择 SHALL 使用后端 `defaultSelected`
- **AND** 页面 SHALL 展示依赖、风险、安装包和选择依据

#### Scenario: 提交自动修复

- **WHEN** 用户确认至少一个候选项
- **THEN** frontend SHALL 请求 POST `/api/dependency-analyses/{analysisId}/auto-fixes`
- **AND** 默认 SHALL 设置 `rerunDependencyAnalysis=true`
- **AND** 用户 MAY 在提交前关闭修复后重新分析

#### Scenario: 历史分析或候选项不可用

- **WHEN** 分析不属于当前 Context、候选列表为空或候选请求失败
- **THEN** 页面 SHALL 禁止提交自动修复
- **AND** 历史分析 SHALL 保持只读
- **AND** 请求失败 SHALL 提供重新加载操作

### Requirement: 当前依赖结果的报告输入

当前成功分析的结果 SHALL 支持互斥的纳入报告/排除操作，操作规则遵循 assessment-report 的输入规范。

#### Scenario: 查看分析结果操作

- **WHEN** 用户查看可操作的当前依赖结果
- **THEN** 自动修复 SHALL 作为结果页主要业务动作，重新分析与历史入口保持次级层级
- **AND** 结果详情 SHALL 可查看证据、建议和报告纳入状态
