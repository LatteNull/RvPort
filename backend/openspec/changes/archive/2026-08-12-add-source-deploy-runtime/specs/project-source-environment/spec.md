## ADDED Requirements

### Requirement: 环境工作目录必须作为远端源码部署根路径
环境管理能力 SHALL 将 `environments.working_directory` 作为源码部署和后续构建验证的远端工作目录根路径。

#### Scenario: 使用工作目录部署源码
- **WHEN** 用户为某个环境创建源码部署任务
- **THEN** 后端 SHALL 使用该环境的 `working_directory` 作为远端部署根路径
- **AND** 后端 SHALL 在该根路径下生成受控源码部署目录
- **AND** 前端 MUST NOT 通过源码部署 API 覆盖该根路径

#### Scenario: 工作目录缺失时拒绝源码部署
- **WHEN** 环境缺少 `working_directory`
- **AND** 用户尝试将源码部署到该环境
- **THEN** 后端 SHALL 拒绝请求并返回 `ENVIRONMENT_WORKING_DIRECTORY_REQUIRED`
- **AND** 后端 MUST NOT 创建源码部署任务或远端执行命令

#### Scenario: 更新工作目录影响后续部署
- **WHEN** 用户更新环境的 `working_directory`
- **THEN** 后端 SHALL 保留既有源码部署记录中的历史 `remote_path`
- **AND** 后续新建源码部署 SHALL 使用更新后的 `working_directory` 生成新的远端路径
