# build-validation Specification

## Purpose

定义 build 节点的双端构建配置、服务端门禁、分页构建记录及日志。共享执行与刷新规则由 project-stage-runtime 定义。

## Requirements

### Requirement: 双端构建前置条件

构建验证 SHALL 使用 `build` readiness 的 `ACTIVE_SOURCE`、`SOURCE_ENVIRONMENT` 和 `TARGET_ENVIRONMENT`，展示当前源码及双端环境，前置条件和配置区可独立收起。

#### Scenario: 前置条件未满足

- **WHEN** 源码或任一运行环境条件未满足
- **THEN** 页面 SHALL 阻止构建并提供前往源码管理或环境管理的恢复入口
- **AND** readiness 请求失败 SHALL 展示重新加载，不将错误伪装成条件缺失

### Requirement: 双端构建提交

构建验证 SHALL 以一份公共脚本、超时和可选环境变量提交 `buildScope=BOTH` 及 readiness Context 的源码版本。

#### Scenario: 开始构建

- **WHEN** 条件满足且用户提交有效配置
- **THEN** 页面 SHALL 创建双端构建任务并说明任务会自行准备源码后执行脚本
- **AND** 提交期间 SHALL 防止重复请求，成功后由 SSE 刷新记录

#### Scenario: 初始化命令

- **WHEN** `VALIDATION latest` 为 CURRENT 且含有最近构建命令
- **THEN** 页面 SHALL 用其初始化配置，否则使用默认命令
- **AND** 后续刷新 SHALL 不覆盖用户已编辑的命令

### Requirement: 构建验证必须与 x86 构建统一记录结构

构建验证 SHALL 直接展示 `BOTH` 分页记录，并使用 `VALIDATION latest` 标记当前记录，不增加“当前结果到历史记录”的二级导航。

#### Scenario: 展示构建验证记录

- **WHEN** 构建验证 Drawer 打开
- **THEN** ID、状态、创建时间、操作、筛选、状态 Tag、当前标识和行密度 SHALL 与 x86 构建一致
- **AND** 构建验证 SHALL 额外展示环境列区分 x86 与 RISC-V
- **AND** 退出码 SHALL 只在日志详情中展示

### Requirement: 构建记录操作

记录 SHALL 展示 ID、环境、状态、创建时间、当前标识和操作，支持状态筛选、分页、日志与确认取消。

#### Scenario: 查看日志

- **WHEN** 用户选择一条构建记录
- **THEN** Drawer SHALL 展示紧凑任务摘要和 task-log-viewer，并提供返回构建记录入口
- **AND** 退出码 SHALL 在日志摘要中展示而不是占用列表列
