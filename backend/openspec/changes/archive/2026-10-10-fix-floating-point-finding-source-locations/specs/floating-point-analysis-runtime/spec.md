## ADDED Requirements

### Requirement: 专项 Finding 可读取版本绑定的源码上下文
后端 SHALL 在浮点和内存序 Finding 的现有详情响应中直接内嵌 codeContext，不提供独立 code-context API；使用 Finding 的 sourceRevisionId 读取源码，不回退到当前版本。主位置前后 SHALL 各展示最多 20 行，返回真实行号、片段起止、高亮范围及逐行 highlighted 标记。列表 SHALL 不批量加载源码。

#### Scenario: 历史结果源码读取
- **WHEN** 当前源码版本已更新但历史 Finding 对应工作副本仍存在
- **THEN** SHALL 返回历史版本的源码及 sourceRevisionId，不能把当前代码拼入历史结果

#### Scenario: 上下文边界及安全
- **WHEN** 请求无权限或跨项目/类型
- **THEN** SHALL 拒绝整个请求，不读取源码

#### Scenario: 上下文不可用不影响结果详情
- **WHEN** 路径越界、无有效位置、文件已清理、编码错误或超过 8 MiB
- **THEN** SHALL 保留 Finding 详情，codeContext 返回 null，并提供不泄漏服务器路径的 codeContextUnavailableReason；合法短文件 SHALL 仅返回已有行

### Requirement: 浮点源码位置必须兼容 Clang 省略字段
扫描器 SHALL 在文件归属可证明时结合翻译单元、AST 文件上下文和源码字节偏移恢复位置，输出项目相对路径及 1-based 行列，并正确恢复内部源码范围。系统 MUST NOT 因 Clang 合法省略 file 或 line 而丢失本可恢复的位置，也 MUST NOT 伪造坐标。

#### Scenario: 表达式只包含偏移和列
- **WHEN** 浮点表达式节点只有合法 offset、col，所属项目文件可确定
- **THEN** 扫描器 SHALL 根据该文件字节内容恢复准确文件和行列并传递到 Finding

#### Scenario: 多字节与换行边界
- **WHEN** 表达式之前存在 UTF-8 多字节字符、CRLF、制表符或多行内容
- **THEN** 恢复位置 SHALL 使用 Clang 字节偏移语义并准确指向表达式，不能使用 Unicode 字符计数替代字节索引

#### Scenario: 宏与头文件位置
- **WHEN** AST 含项目头文件、外部头文件和宏的 spelling/expansion 位置
- **THEN** 扫描器 SHALL 分别解析真实来源并维持项目边界，不能把外部文件偏移应用到主源码

#### Scenario: 位置无法安全恢复
- **WHEN** 文件缺失、归属不明、偏移越界或路径超出授权边界
- **THEN** 扫描器 SHALL 保留未知位置并提供脱敏双语诊断，不读取未授权文件，不默认填充第 1 行，不删除风险结论

### Requirement: 浮点聚合位置必须完整一致
扫描器 SHALL 以直接证据对应的去重位置集合生成稳定主位置和关联 occurrences；主位置 SHALL 属于该集合，其他可用位置 SHALL 在预算内保留，预算不足 SHALL 显式说明。

#### Scenario: 同类结果包含多个位置
- **WHEN** 同类结果包含重复位置、不同位置和未知位置
- **THEN** 主位置 SHALL 优先取可用位置，关联位置 SHALL 去重且不能漏掉任一预算内的不同位置，也不能重复主位置

### Requirement: 浮点位置修复必须贯通现有结果接口
后端 SHALL 将工具提供的位置一致地保存到 Finding 索引字段和 detail，并通过现有列表、详情和 HTML 返回；系统 SHALL 保持 schema v2 与历史结果不可变。

#### Scenario: 新扫描位置贯通
- **WHEN** 新扫描 JSON 包含非空合法主位置及关联位置
- **THEN** 数据库和列表/详情/HTML SHALL 与原始结果一致，列表按该路径行号过滤排序有效

#### Scenario: 历史空位置结果
- **WHEN** 部署修复后读取已有空位置扫描
- **THEN** 历史结果 SHALL 保持原状，新的准确位置 SHALL 通过重新扫描产生

### Requirement: 指针比较不得误判为浮点标量比较
扫描器 SHALL 根据比较操作数的实际标量类型识别浮点比较，支持 typedef 展开；MUST NOT 仅因指针指向浮点类型就产生浮点比较风险。

#### Scenario: 空指针及指针间比较
- **WHEN** float/double 指针与 nullptr、零值空指针常量或另一个指针比较
- **THEN** SHALL 不产生浮点 comparison 事实及对应的浮点比较 Finding

#### Scenario: 解引用及别名标量比较
- **WHEN** 指针解引用、数组元素、引用值或 typedef 浮点标量执行数值比较
- **THEN** SHALL 保留真实浮点比较事实并继续按现有规则判断风险

### Requirement: 位置恢复必须通过独立测试与真实 AST 验证
修复 SHALL 覆盖正常、异常、边界单测，纳入未加载自有源码；整体与受影响模块行及可用分支覆盖率 SHALL 至少 90%。真实 Clang 集成测试和项目 API E2E SHALL 补充验证真实位置，但不能替代单测。

#### Scenario: 验证真实位置
- **WHEN** Linux Docker 中运行测试及真实 Clang fixture
- **THEN** 测试 SHALL 断言具体路径行列、宏和头文件边界、聚合完整性与 v2 合法性，单测不依赖外部服务

#### Scenario: 质量门禁不通过
- **WHEN** 测试失败或整体/模块覆盖率未达门槛
- **THEN** 本 change SHALL 保持未完成并记录差距，不能通过排除自有业务代码降低统计范围
