## ADDED Requirements

### Requirement: 表格高度测量按需启用

共享表格 SHALL 仅在当前滚动策略使用测量高度时启用布局读取、ResizeObserver 与窗口 resize 监听；不使用测量结果的模式 SHALL 保留其既有 scroll 行为，不执行无效测量。重复测量状态提交遵循本能力既有规则。

#### Scenario: 使用无需测量的表格模式

- **WHEN** 表格处于直接采用传入 scroll 的 autoHeight 模式
- **THEN** 表格 SHALL 不注册高度测量 observer/resize listener，也不执行高度布局读取
- **AND** 传入 scroll 与当前内容滚动行为 SHALL 保持有效

#### Scenario: 切换测量模式或卸载

- **WHEN** 表格从测量模式切换为停用模式或卸载
- **THEN** 测量监听 SHALL 清理，旧测量结果 SHALL 不影响当前滚动策略
- **WHEN** 表格重新进入需要测量的模式
- **THEN** 表格 SHALL 重新读取当前尺寸，保留既有高度计算与相同高度不重复更新的规则
