## Why

用户要求判断依据直接按后端 steps 展示，不由前端额外判断证据链是否完整或筛选主路径。

## What Changes

- 按 steps 返回顺序显示所有步骤，不再按 primaryPath 筛选和重排。
- 删除路径降级、断点和证据链预算提示，保留 step 自身状态和说明。
- 原始诊断数据仍可查看，空步骤保持中性空态。

## Capabilities

### Modified Capabilities

- `knowledge-base-finding-detail`: 判断依据按服务端步骤完整展示。

- Finding 四处分区图标与主标题行垂直居中，说明文字与标题文字对齐。

## Impact

仅涉及前端 Finding 展示模型、证据组件、样式和测试，不改后端。
