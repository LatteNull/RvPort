## ADDED Requirements

### Requirement: Worker 镜像必须固定安装两个分析工具
backend-worker 镜像 SHALL 安装固定版本的浮点精度扫描 Python 包、memory-order Python 模块、`fp-ir-worker`、`moa-worker`、`memory-order-source-worker` 以及所需 LLVM/Clang 21 运行库；API-only 进程 MAY 不安装这些工具。

#### Scenario: 构建 Worker 镜像
- **WHEN** 构建 backend-worker 镜像
- **THEN** 多阶段构建 SHALL 编译并复制三个 C++ worker
- **AND** Python 依赖 SHALL 安装到固定只读隔离环境或固定模块目录

#### Scenario: 离线运行
- **WHEN** Worker 执行专项分析
- **THEN** 工具 MUST NOT 在运行时从网络安装依赖
- **AND** MUST NOT 依赖宿主机源码挂载或 Docker socket

### Requirement: Worker 必须暴露分析工具健康状态
Worker SHALL 在启动时执行版本和 doctor 检查，并 SHALL 将每个分析器的可用性、版本和失败原因提供给 readiness 使用。

#### Scenario: 工具完整可用
- **WHEN** Python CLI、锁定 schema、LLVM 动态库和对应 C++ worker 均可用
- **THEN** 该分析器健康状态 SHALL 为 AVAILABLE

#### Scenario: 缺少运行组件
- **WHEN** CLI、动态库或 C++ worker 缺失或版本不兼容
- **THEN** 健康状态 SHALL 为 UNAVAILABLE 并包含安全原因码
- **AND** 创建分析任务 SHALL 被阻止

### Requirement: 分析运行资源必须可配置且受限
系统 SHALL 为 workspace、cache、执行超时、输出大小、解压大小、文件数量和并发设置安全默认值与环境变量配置。

#### Scenario: 输出超过预算
- **WHEN** 工具输出或解压内容超过配置预算
- **THEN** Worker SHALL 停止导入并清理临时目录
- **AND** 任务 SHALL 以明确资源限制原因失败

#### Scenario: cache 不共享
- **WHEN** 多个 Worker 使用各自本地 cache
- **THEN** cache miss MAY 导致重复计算
- **AND** MUST NOT 改变分析语义或结果身份
