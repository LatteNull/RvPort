## ADDED Requirements

### Requirement: 前端必须提供候选相关使用结构并保留原事实

C/C++ Frontend SHALL 为用途分析提供可定位的声明/引用绑定、读写、简单赋值、比较、控制体、调用参数和逃逸记录。普通无属性函数 SHALL 可被分析；原宏/枚举/函数多版本 Evidence 的值、身份和位置 MUST NOT 被用途标签重写。

#### Scenario: 普通函数中使用局部枚举

- **WHEN** 无 target 属性的函数包含候选枚举及其比较、赋值和后续使用
- **THEN** Frontend SHALL 提供同作用域、真实字节范围的使用记录与完整性信息
- **AND** 不得因函数多版本 inventory 的属性快速路径而漏掉该需求

#### Scenario: 重名或不完整语法

- **WHEN** 同名声明遮蔽、Clang/语法绑定冲突、模板依赖、ERROR/MISSING 或不支持结构影响当前使用范围
- **THEN** SHALL 保留可定位记录并显式 unknown/partial，不按名称任意绑定
- **AND** 无关范围的独立完整记录 SHALL 保留，原 fact 不被删除

#### Scenario: 普通枚举函数不消耗候选用途记录预算

- **WHEN** 文件包含大量非候选枚举或宏，但只有少数函数包含正式知识匹配得到的候选 fact
- **THEN** 默认管线 SHALL 先用正式归一化及候选需求规则选择锚点，仅提取候选所在函数的完整用途记录
- **AND** SHALL 复用本次语法树而不逐 Finding 重解析；不相关函数不生成 usage_scope，不消耗全扫描 usage record 额度，原始事实仍全部保留

### Requirement: 使用结构必须保持原生安全与规范化引用完整性

Frontend SHALL 在 native tree 生命周期内一次提取标量记录，使用既有 SourceByteIndex 而非原生 Point；Node/Tree/Cursor MUST NOT 进入 snapshot。Normalizer SHALL 校验声明、owner、使用端点、span 和配置来源并保留不同配置。

#### Scenario: UTF-8 和多个配置

- **WHEN** 同一文件含 UTF-8/CRLF，且有不同 compile context 或未知基线配置
- **THEN** SHALL 输出精确位置、独立绑定与完整性，不合并成虚假的完整配置
- **AND** 增补语义不得改变已有事实哈希或引入机器根路径身份

#### Scenario: 无效 owner 或原生范围

- **WHEN** 新使用记录引用不存在的声明或不合法范围
- **THEN** Normalizer SHALL 拒绝该记录并产生诊断，不能生成完整用途证明
- **AND** 原生崩溃回归、未释放对象检查及预算反例 SHALL 纳入组件与隔离测试
