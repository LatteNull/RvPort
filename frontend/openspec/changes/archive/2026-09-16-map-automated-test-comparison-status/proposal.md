## Why

后端测试比较使用 `EQUIVALENT` 等结果枚举，前端仍按旧枚举映射，导致标签直出英文且比较标题回退为等待状态。

## What Changes

- 映射后端四种测试比较结果为中文标签、标题和语义色。
- 保留旧比较枚举的展示兼容。
- 增加四种后端结果枚举的回归测试。

## Capabilities

### Modified Capabilities

- `automated-test-stage`: 自动比较结果按当前后端枚举显示中文结论。

## Impact

仅影响 frontend 自动化测试比较状态的展示，不改变接口或比较逻辑。
