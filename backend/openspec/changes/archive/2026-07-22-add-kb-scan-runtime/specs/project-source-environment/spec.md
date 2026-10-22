## ADDED Requirements

### Requirement: 源码版本必须可作为 KB 扫描输入
项目源码管理 SHALL 为 KB 扫描提供后端本机可读的源码工作副本，并 SHALL 防止跨项目扫描源码。

#### Scenario: 当前启用源码版本用于 KB 扫描
- **WHEN** 项目存在当前启用源码版本且用户创建 KB 扫描未指定 `sourceRevisionId`
- **THEN** 后端 SHALL 使用当前启用源码版本作为扫描输入
- **AND** 后端 SHALL 校验该源码版本的工作副本可用
- **AND** API 响应和任务输入快照 MUST NOT 暴露 `working_copy_path`

#### Scenario: 指定源码版本用于 KB 扫描
- **WHEN** 用户创建 KB 扫描并指定 `sourceRevisionId`
- **THEN** 后端 SHALL 校验源码版本属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验该源码版本不是失败导入产生的无效版本
- **AND** 后端 SHALL 校验工作副本可供后端本机 scanner 读取

#### Scenario: 源码工作副本不可用
- **WHEN** 源码版本缺少工作副本、工作副本被清理或后端不可读取
- **THEN** 后端 SHALL 拒绝创建 KB 扫描任务或将任务安全失败
- **AND** 错误摘要 MUST NOT 暴露服务器真实路径
- **AND** 后端 MUST NOT 投递无法执行的 scanner 任务，除非失败只能在 worker 阶段发现

### Requirement: KB 扫描不得修改源码版本事实
KB 扫描 SHALL 只读取源码工作副本，不得修改源码版本记录、当前启用版本或源码来源锁定状态。

#### Scenario: KB 扫描成功
- **WHEN** KB_SCAN 任务成功完成
- **THEN** 后端 MUST NOT 修改 `source_revisions` 的源码内容事实
- **AND** 后端 MUST NOT 修改项目 `sourceInputType`
- **AND** 后端 MUST NOT 自动切换当前启用源码版本

#### Scenario: KB 扫描失败
- **WHEN** KB_SCAN 任务失败或取消
- **THEN** 后端 MUST NOT 回滚或删除被扫描的源码版本
- **AND** 后端 MUST NOT 改变当前启用源码版本
