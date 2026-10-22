## MODIFIED Requirements

### Requirement: 详情复用所属扫描上下文

系统 SHALL 复用进入详情前已经加载的当前或历史 scan，并避免为渲染 Finding 详情重复获取同一 scan。

#### Scenario: 从当前扫描结果进入详情

- **WHEN** 当前结果页已通过 latest 接口取得 scan 且用户打开 Finding
- **THEN** 系统 SHALL 复用该 scan 判断报告操作资格并提供 `sourceRevisionId`
- **AND** 系统 SHALL NOT 因进入详情再次调用 `GET /kb-scans/{scanId}`

#### Scenario: 展示完整证据路径

- **WHEN** evidenceChain.steps 非空
- **THEN** 系统 SHALL 按服务端返回顺序展示全部步骤，不按 primaryPath 筛选或重排
- **AND** 每一步 SHALL 展示自身标题、依据和完整度，并支持选择查看

#### Scenario: 证据存在断点或预算截断

- **WHEN** primaryPath 缺失或无效，或证据链包含 breaks 或 budget.truncated=true
- **THEN** 系统 SHALL 继续按 steps 展示所有步骤
- **AND** 系统 SHALL NOT 在判断依据区域额外生成路径不完整、断点阶段或证据链预算提醒
- **AND** 原始扫描数据 SHALL 保留这些服务端字段供诊断

#### Scenario: 主路径缺失但存在证据步骤

- **WHEN** primaryPath 缺失或无法解析且 steps 非空
- **THEN** 系统 SHALL 按服务端返回顺序展示全部步骤
- **AND** 系统 SHALL NOT 根据主路径是否可解析追加完整性判断

#### Scenario: 结构化字段缺失

- **WHEN** Finding 的部分结构化字段为空但旧版投影字段或原始 `evidence` 中存在等价信息
- **THEN** 系统 SHALL 使用明确且可测试的兼容优先级展示可用信息
- **AND** 系统 SHALL 对无法恢复的信息使用中性缺失说明，不展示内部字段名或开发占位语

#### Scenario: 分区图标与主标题对齐

- **WHEN** 判断依据、建议下一步、扫描事实和原始扫描数据标题同时包含图标、主标题和说明
- **THEN** 图标 SHALL 与主标题行垂直居中，说明文字 SHALL 与主标题文字左侧对齐
- **AND** 装饰图标 SHALL NOT 改变标题的可访问名称

#### Scenario: 建议正文随容器宽度排版

- **WHEN** 建议下一步展示建议正文
- **THEN** 正文 SHALL 使用常规字重，随外框可用宽度自动换行，不限制固定最大宽度
- **AND** 正文 SHALL 缩进至主标题文字起点，长文本不得溢出外框
