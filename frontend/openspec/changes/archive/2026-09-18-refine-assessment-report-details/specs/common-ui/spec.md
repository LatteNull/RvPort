## ADDED Requirements

### Requirement: 远程列表搜索交互统一

前端 SHALL 为服务端分页列表提供一致的轻量搜索输入，并 SHALL 避免用户连续输入时为每次按键立即发起请求。

#### Scenario: 输入关键词筛选远程列表

- **WHEN** 用户在远程列表搜索框连续输入关键词
- **THEN** 搜索框 SHALL 使用前置搜索图标且不展示主色提交按钮
- **AND** 系统 SHALL 在用户停止输入后的统一防抖间隔提交最新关键词
- **AND** 新查询 SHALL 回到第一页并保留上一批结果直至新结果返回

#### Scenario: 立即提交搜索

- **WHEN** 用户在远程列表搜索框按下 Enter
- **THEN** 系统 SHALL 取消当前等待中的防抖并立即提交已去除首尾空白的关键词

#### Scenario: 清空搜索

- **WHEN** 用户清空远程列表搜索框
- **THEN** 系统 SHALL 立即移除关键词筛选并回到第一页

#### Scenario: 多个远程列表使用搜索

- **WHEN** 知识库扫描结果、评估报告模块列表或其他服务端分页列表提供关键词搜索
- **THEN** 相同搜索状态 SHALL 使用一致的输入外观、清空能力、键盘行为和请求触发规则

### Requirement: Monaco 工作区边界一致

前端 SHALL 为 Monaco 独立视图和带标题栏的组合工作区提供一致的边框、圆角与内部分隔。

#### Scenario: 独立展示 Monaco

- **WHEN** Monaco 不属于带标题栏的组合工作区
- **THEN** 共享组件 SHALL 提供 `1px` 次级边框和 `12px` 圆角

#### Scenario: 将 Monaco 嵌入组合工作区

- **WHEN** 标题栏、列表或 Tabs 与 Monaco 组成同一工作区
- **THEN** 外层工作区 SHALL 提供 `1px` 次级边框和 `12px` 圆角
- **AND** 内部 Monaco SHALL 移除自身边框与圆角，避免出现双重边框
- **AND** 标题栏与内容区 SHALL 使用单一分隔线区分

#### Scenario: 聚焦只读代码上下文

- **WHEN** 用户聚焦只读 Monaco 或移动代码光标
- **THEN** 缩进参考线 SHALL 保持普通颜色，不加深活动缩进
- **AND** 编辑器 SHALL 不绘制光标所在行的默认边框，并保留业务整行高亮与代码片段下划线
