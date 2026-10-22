## ADDED Requirements

### Requirement: 浮点证据步骤必须提供双语标题和说明
新生成的浮点结果 SHALL 在每个 evidenceChain.steps 条目返回非空 title、titleEn、reason、reasonEn，中文为默认展示。标题 SHALL 不超过 512 字符，说明 SHALL 不超过 4096 字符；工具 Schema SHALL 校验这些字段。系统 MUST NOT 仅在 Finding 顶层添加文案来替代步骤说明。

#### Scenario: 多种证据步骤
- **WHEN** 新结果包含源码、IR、绑定、profile、构建上下文、编译选项、评估或结论步骤
- **THEN** 每步 SHALL 包含完整双语标题和说明，严格 Schema 校验通过

#### Scenario: 非法展示字段
- **WHEN** 新生成步骤缺少字段、字段为空或超出长度上限
- **THEN** 校验 SHALL 拒绝将该结果作为合法新协议输出发布

### Requirement: 步骤说明必须基于直接引用的真实证据
生成器 SHALL 根据步骤引用的实际事实和评估生成可读摘要，区分观察、判断与结论；MUST NOT 将所有步骤填为固定类型名或重复最终结论。文本 SHALL 使用项目相对位置，不暴露服务器路径或敏感配置。

#### Scenario: 源码及 IR 对照
- **WHEN** 引用中具有实际运算、位置、LLVM opcode 或浮点属性
- **THEN** 对应说明 SHALL 与这些事实一致，不杜撰缺失的编译选项或确定性失败

#### Scenario: 证据不足
- **WHEN** 有效引用缺少可解释语义或证据为未知、部分、歧义
- **THEN** 步骤 SHALL 提供双语限制说明与稳定原因码，遵守既有状态传播，不将其描述为完整确定证明

#### Scenario: 悬空引用
- **WHEN** 引用无法通过既有闭包校验
- **THEN** 系统 SHALL 保持校验失败语义，不以填充可读文案绕过引用校验

### Requirement: 步骤说明必须贯通现有制品与详情
后端 SHALL 将工具步骤说明完整保存在 Finding detail，并经既有详情 API 和原始 JSON 制品返回；MUST NOT 新增专用说明接口或静默重写历史扫描。系统 SHALL 保留稳定 Finding/step 身份并按既有规则计算新结果摘要。

#### Scenario: 真实新扫描
- **WHEN** worker 完成包含步骤文案的新扫描并导入
- **THEN** 原始结果、落库 detail 及现有详情响应的双语字段 SHALL 一致，继续受项目权限约束

#### Scenario: 历史结果与重复执行
- **WHEN** 读取旧扫描或以同一输入和版本重复生成结果
- **THEN** 历史内容 SHALL 保持原样；新版本重复输出 SHALL 确定，展示字段不得改变稳定身份计算规则

### Requirement: 步骤展示变更必须通过独立测试和覆盖率门禁
工具与受影响后端 SHALL 覆盖正常、异常、边界独立单元测试，mock 外部连接返回值；整体与受影响模块行及可用分支覆盖率 SHALL 至少 90%，统计包含未加载自有源码，并同步工具规范与文档。

#### Scenario: Linux 验收
- **WHEN** 在 Docker 中运行测试与覆盖率
- **THEN** SHALL 验证步骤类型、证据限制、UTF-8、长度、身份稳定性、Schema、预算和后端透传，记录范围、排除项及报告位置

#### Scenario: 门禁失败
- **WHEN** 测试或覆盖率未达要求
- **THEN** 任务 SHALL 保持未完成，不以真实扫描成功替代单元测试验收
