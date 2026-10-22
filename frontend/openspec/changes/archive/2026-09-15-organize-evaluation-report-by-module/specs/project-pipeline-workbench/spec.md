## MODIFIED Requirements

### Requirement: 评估报告信息层级

评估报告 SHALL 以报告结论和代码模块作为主要阅读路径，并统一使用模块、文件和 Finding 的服务端组织事实。

#### Scenario: 展示报告概览

- **WHEN** 评估报告生成成功
- **THEN** 系统 SHALL 展示生成时间、总体风险、代码模块数、影响文件数、代码 Finding 数和高风险问题数
- **AND** SHALL 以模块作为代码迁移的一级主体
- **AND** SHALL NOT 生成工作包、前置依赖或验收标准

#### Scenario: 展示输入构成

- **WHEN** 模块化报告包含代码 Finding 与依赖输入
- **THEN** 系统 SHALL 在代码模块中展示风险与问题类型分布
- **AND** SHALL 在存在依赖输入时将依赖清单作为可展开辅助区展示

#### Scenario: 从模块进入文件

- **WHEN** 用户选择一个代码模块
- **THEN** 系统 SHALL 展示该模块的识别依据、置信度、风险与问题类型分布
- **AND** SHALL 分页展示该模块包含的文件
- **AND** 问题类型 SHALL 作为文件筛选条件而非独立导航层级

#### Scenario: 查看报告文件

- **WHEN** 用户选择模块中的文件
- **THEN** 系统 SHALL 展示该文件的 Finding 列表和报告绑定源码版本的联合上下文
- **AND** 选择 Finding SHALL 突出对应源码行
- **AND** 系统 SHALL 使用代码编辑器展示真实源码行号及接口返回的列范围高亮
- **AND** 结构化省略区间 SHALL 支持按需展开
- **AND** 源码上下文不可用时 SHALL 保留 Finding 列表并说明原因
