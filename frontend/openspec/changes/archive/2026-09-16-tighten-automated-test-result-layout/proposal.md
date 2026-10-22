## Why

自动化测试 Drawer 的当前结果卡片和结果对比卡片纵向留白偏大，单侧日志操作独占一行，降低了同屏信息密度。

## What Changes

- 收紧当前测试结果卡片的行间距，并将日志与取消操作放到统计行右侧。
- 收紧当前结果和结果对比两个区块的标题与内容间距。
- 调整结果对比卡片的内边距和内部行间距。

## Capabilities

### Modified Capabilities

- `automated-test-stage`: 自动化测试结果以更紧凑的卡片布局展示，日志操作不再单独占用一行。

## Impact

仅影响 frontend 自动化测试 Drawer 的结果展示布局，不改变接口、数据或交互能力。
