## ADDED Requirements

### Requirement: 构建可用性分析展示

前端 SHALL 在固定 Workflow 中展示 x86 构建与依赖分析结果，并以通过、待处理、已失效或无结果的静态示例说明构建可用性。

#### Scenario: 构建可用性通过

- **WHEN** 静态演示数据中的 x86 构建或 RISC-V 依赖分析为通过
- **THEN** 对应节点 Drawer SHALL 展示“可构建”状态

#### Scenario: 存在待处理项

- **WHEN** RISC-V 依赖分析的静态结论包含待处理问题
- **THEN** 对应 Drawer SHALL 展示问题来源、摘要和建议动作
- **AND** SHALL NOT 发起网络请求或写入服务端状态

### Requirement: 构建可用性分析节点 Drawer

前端 SHALL 为 `x86-build` 与 `rv-dependency-analysis` 节点提供独立 Drawer，并以静态演示数据展示对应检查结论、版本范围和问题摘要。

#### Scenario: 打开构建可用性节点

- **WHEN** 用户点击 `x86-build` 或 `rv-dependency-analysis` 节点
- **THEN** 系统 SHALL 打开对应 Drawer
- **AND** SHALL 展示静态的当前源码版本、x86 构建或 RISC-V 环境配置范围及结果摘要
- **AND** SHALL NOT 调用领域 API、创建任务、建立 SSE 连接或轮询

#### Scenario: 静态确认范围失效

- **WHEN** Drawer 展示静态的源码版本、x86 构建记录或 RISC-V 环境配置版本不匹配示例
- **THEN** Drawer SHALL 展示“已失效”状态和重新完成构建前检查的引导
