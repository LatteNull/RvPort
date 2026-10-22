## MODIFIED Requirements

### Requirement: 当前知识库扫描

扫描 SHALL 使用 `kb` readiness 的 `ACTIVE_SOURCE`、`X86_BUILD` 条件及扫描 latest；页面状态遵循 project-stage-runtime。

#### Scenario: 开始扫描

- **WHEN** 当前源码和 x86 构建条件满足且用户确认扫描配置
- **THEN** 页面 SHALL 创建扫描任务，返回当前结果视图并提示已启动
- **AND** 页面 SHALL 不因源码导入或进入节点而自动创建扫描

#### Scenario: 浏览结果与历史

- **WHEN** 用户查看成功扫描
- **THEN** 页面 SHALL 提供结果统计、分页筛选、Finding 详情、分析信息和制品入口
- **AND** 历史扫描 SHALL 使用选中记录的上下文，不能修改当前报告输入

#### Scenario: 历史按可用时间排序

- **WHEN** 用户打开扫描历史
- **THEN** frontend SHALL 显式查询跨源码版本记录并按接口支持的 `startedAt desc` 分页
- **AND** SHALL NOT 请求接口不支持的 `createdAt` 排序或伪造尚未开始任务的时间
