## ADDED Requirements

### Requirement: 内存序源码位置必须来自关联的真实证据
系统 SHALL 为新生成的正式 Finding、源码候选和已消解审计投影解析真实关联的源码位置；位置 SHALL 受 scope、翻译单元和编译上下文约束，MUST NOT 用首个文件或同名符号猜测位置。存在多处可信位置时 SHALL 保留关联位置并确定性选择主位置；步骤只引用自己的证据。

#### Scenario: 正式风险具有访问证据
- **WHEN** publication 或 advanced-atomic 评估关联的源码或 IR 访问具有可信位置
- **THEN** 工具 SHALL 输出非空 primaryLocation、对应 occurrence 和属于相关步骤的 source，后端 SHALL 导入主位置并保留 detail

#### Scenario: 多文件及已消解审计结果
- **WHEN** 一个结论关联多个项目文件或结论属于 discharged 审计结果
- **THEN** 投影 SHALL 保留可信位置及角色，不把主位置复制到无关步骤，不改变原有结论分类和风险判断

#### Scenario: 无法唯一追溯证据
- **WHEN** 引用缺失、歧义或 IR 无可用调试位置且无法可信绑定 AST
- **THEN** 系统 SHALL 保留未知位置、稳定原因码和双语说明，MUST NOT 伪造片段或提高证明完整性

### Requirement: 内存序源码上下文必须与实际文件匹配
系统 SHALL 根据证据所属文件及可信源码快照生成上下文，校验文件路径和摘要；MUST NOT 把头文件行号应用到主翻译单元。宏位置 SHALL 明确区分 expansion 与 spelling，跨文件范围 MUST NOT 被当作单文件范围。

#### Scenario: 头文件与宏展开
- **WHEN** 候选位于项目头文件或宏中
- **THEN** 系统 SHALL 使用实际文件快照，优先选择可信项目内 expansion，并保留不同的可信 spelling 关联；没有 expansion 时显式使用可信 spelling

#### Scenario: 范围及预算
- **WHEN** 位置具有有效源码范围
- **THEN** 上下文 SHALL 默认包含前后各 20 行并正确高亮 end-exclusive 范围，文件边界处返回实际可用行，预算截断 SHALL 结构化标记

#### Scenario: 文件不可安全读取
- **WHEN** 路径越界、链接不安全、摘要不符、文件缺失、编码不支持或坐标无效
- **THEN** 系统 SHALL 返回明确不可用原因，不返回其他文件片段、不泄露服务端路径，不把源码读取问题伪装成并发证明

### Requirement: 内存序详情必须一次返回主位置代码上下文
现有内存序 Finding 详情 API SHALL 在权限校验后随响应返回 codeContext 和 codeContextUnavailableReason，使用 Finding 绑定的源码版本；工具嵌入的关联位置上下文 SHALL 保留在 detail。系统 MUST NOT 为此新增专用取代码 API，也 MUST NOT 静默回填历史扫描。

#### Scenario: 有效位置详情
- **WHEN** 用户有项目权限且 Finding 主位置和绑定源码可用
- **THEN** 同一次详情请求 SHALL 返回路径、代码行、起止行号及高亮，codeContextUnavailableReason 为 null

#### Scenario: 未知位置及历史记录
- **WHEN** 位置或源码不可用，或者读取没有新位置字段的历史结果
- **THEN** 详情 SHALL 继续返回 Finding 及明确不可用原因，不猜测位置，不改写历史 detail

#### Scenario: 跨项目请求
- **WHEN** 用户无项目权限或 Finding 不属于请求项目/分析类型
- **THEN** 系统 SHALL 拒绝请求，不读取或返回代码

### Requirement: 内存序位置修复必须通过独立测试和真实链路验证
后端与工具 SHALL 覆盖正常、异常、边界独立单测，mock 外部连接返回值，在 Linux Docker 中执行；全部自有源码含未加载模块的整体及受影响模块行/可用分支覆盖率 SHALL 至少 90%。系统 SHALL 同步工具规范与中文文档，并保留真实编译器/API 的验证记录。

#### Scenario: 端到端位置一致
- **WHEN** 对 AST-only 和 AST+BC 样本执行验证
- **THEN** 验证 SHALL 对照真实源码、工具 JSON、落库位置和详情的文本/高亮，覆盖头文件、宏、多位置、正式风险、源码候选及不可用负例，且不得以成功退出替代语义断言

#### Scenario: 质量门禁不足
- **WHEN** 单测失败或覆盖率不达标
- **THEN** 验收 SHALL 保持未完成，记录命令、统计范围、排除依据和报告路径，不以集成测试代替独立单测
