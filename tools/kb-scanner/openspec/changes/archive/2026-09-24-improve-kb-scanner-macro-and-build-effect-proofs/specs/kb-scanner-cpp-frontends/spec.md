## ADDED Requirements

### Requirement: 宏作用分析输入必须保留调用实参与有序预处理事件
Frontend SHALL 为受支持宏调用采集固定实参 token、序号、形参/定义引用及真实 SourceSpan，并保留 define/undef、include、if/elif/else/endif 的有序结构和完整性；所有记录 SHALL 是 scanner-owned 纯数据，不携带 Node/Tree/Cursor。原 Evidence SHALL 保留，无法绑定的调用 MUST NOT 因项目中同名宏存在而被确认为宏展开。

#### Scenario: 固定实参嵌套传递
- **WHEN** `OUTER(f,x)` 的定义将固定参数传到 `INNER(f,x)`，调用实参为标识符或受支持整数/括号包装
- **THEN** frontend SHALL 提供可独立定位的调用实参、形参、replacement 参数引用和嵌套调用记录
- **AND** 记录 SHALL 不把参数替换结果伪造成原文件中的连续源码

#### Scenario: 宏定义来自头文件
- **WHEN** 调用文件没有本地同名宏定义，但包含可见的本地头文件
- **THEN** frontend SHALL 保留可供下游解析该调用的原始记录，不因本文件宏名集合不包含该名字而漏掉调用
- **AND** 最终宏/普通函数区分 SHALL 由可见性及调用时状态证明

#### Scenario: 不支持的参数语义
- **WHEN** 出现变参、token pasting、stringification、无法确认边界的模板逗号或畸形实参
- **THEN** frontend SHALL 保留原始事实和可定位的不支持原因，不生成 complete 参数替换证明
- **AND** scanner MUST NOT 执行预处理器来补齐本轮缺失语义

### Requirement: 宏事件采集必须安全有界并隔离 producer 配置
事件及 token SHALL 在原生对象有效期内转为稳定标量，保留 producer、TU/configuration 和解析完整性；未配置 Tree-sitter 素材 MUST NOT 冒充任意 Clang configuration 的完整语义。路径、语法、token 或事件预算异常 SHALL 保留 partial/unknown，而不是终止整个项目或解释为无风险。

#### Scenario: 同一头文件具有相反配置
- **WHEN** 两个 TU 对同一头文件使用不同宏定义
- **THEN** 原始源码位置 SHALL 可以共享，但配置增强与后续绑定引用 SHALL 可区分
- **AND** 不同 producer 的冲突 SHALL 不以扫描顺序静默覆盖

#### Scenario: 采集异常和位置边界
- **WHEN** 输入含 UTF-8、CRLF、空实参、语法错误或超过事件/token 预算
- **THEN** frontend SHALL 保持合法的项目相对位置和稳定断点，原生对象不得存入 snapshot
- **AND** 采集模块及两类 adapter 接线 SHALL 具有 fake 原生边界的隔离单元测试，真实 parser 组件测试另行统计
