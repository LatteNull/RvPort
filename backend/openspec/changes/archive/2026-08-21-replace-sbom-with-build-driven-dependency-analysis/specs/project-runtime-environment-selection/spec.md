## ADDED Requirements

### Requirement: 项目运行环境必须支持依赖分析环境来源
项目运行环境配置 SHALL 继续维护 source 和 target 双环境，并 SHALL 为依赖分析提供 source 构建环境与 target 能力查询环境。

#### Scenario: 依赖分析读取双环境配置
- **WHEN** 用户创建依赖分析任务
- **THEN** 后端 SHALL 读取项目当前运行环境配置
- **AND** source 环境 SHALL 用于定位成功 x86 构建事实
- **AND** target 环境 SHALL 用于执行 RISC-V 能力查询

#### Scenario: 缺少目标环境时拒绝依赖分析
- **WHEN** 项目运行环境配置缺少 source 或 target 环境
- **THEN** 后端 SHALL 返回运行环境未配置完整错误
- **AND** 后端 MUST NOT 创建依赖分析运行、任务或队列消息

#### Scenario: 环境配置变更后依赖分析过期
- **WHEN** 用户更新项目运行环境配置
- **THEN** 旧环境配置版本下的依赖分析结果 SHALL 保留历史记录
- **AND** 查询响应 SHALL 标识这些结果不属于当前运行环境配置版本
