# source-artifact-management Specification

## Purpose

定义当前有效源码的查看、压缩包导入、Git 更新及来源锁定。当前源码事实遵循 project-overview-current-context。

## Requirements

### Requirement: 当前源码与来源展示

源码 Drawer SHALL 从 overview 的 `currentContext.activeSourceRevision` 读取当前源码，展示版本、来源、文件或仓库、Git 分支/Commit 和更新时间。

#### Scenario: 查看当前源码

- **WHEN** 当前源码存在
- **THEN** 页面 SHALL 展示可追溯信息和更新入口，仓库地址可跳转
- **AND** 无其他下钻入口的信息 SHALL 完整展示，必要时换行

#### Scenario: 尚无有效源码

- **WHEN** 当前源码为空且没有刚提交的导入任务
- **THEN** 页面 SHALL 展示可用导入表单，不从源码历史列表推断当前版本

### Requirement: 导入方式保持一致

项目源码导入方式 SHALL 以项目配置、已保存源码类型或本次成功提交的来源确定；未确定来源前允许选择压缩包或 Git。

#### Scenario: 更新已有来源

- **WHEN** 项目已确定 ARCHIVE 或 GIT 来源
- **THEN** 后续更新 SHALL 使用该来源，不允许通过切换表单更改来源类型

### Requirement: 上传源码压缩包

页面 SHALL 接收 `.zip` 文件，通过 multipart/form-data 上传源码。

#### Scenario: 上传成功

- **WHEN** 服务端返回上传后的源码制品
- **THEN** 页面 SHALL 将其合并至 overview 当前源码、清空表单并反馈成功

#### Scenario: 上传失败

- **WHEN** 文件格式不合法或服务端拒绝上传
- **THEN** 页面 SHALL 展示错误，不把失败上传显示为当前源码

### Requirement: Git 更新与凭据保护

页面 SHALL 接收仓库地址、Ref 和可选用户名/Access Token，并将 Git 更新作为服务端任务提交。

#### Scenario: 提交 Git 更新

- **WHEN** 用户提交合法 Git 配置且创建请求成功
- **THEN** 页面 SHALL 提示任务已提交、清空表单，并由项目事件刷新当前源码
- **AND** 请求成功 SHALL 不被当作源码拉取已经完成

#### Scenario: Git 更新失败

- **WHEN** 提交失败或任务失败
- **THEN** 系统 SHALL 提供失败反馈，不以待导入版本覆盖有效源码
- **AND** Access Token SHALL 不进入读取模型、浏览器持久化数据或日志

### Requirement: 更新源码后显式执行分析

上传或 Git 更新 SHALL 不自动启动扫描、依赖分析或构建；用户从对应阶段显式执行。

#### Scenario: 更新成功后继续工作

- **WHEN** 当前源码发生变化
- **THEN** 下游事实 SHALL 由服务端 Context 与 freshness 表达是否仍有效
- **AND** 页面 SHALL 不伪造后续分析完成状态
