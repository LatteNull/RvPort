## Why

构建、x86 构建、自动化测试等相邻模块存在相同的状态展示、环境变量解析和时间区间格式化实现。重复实现会让同一数据在不同抽屉中出现不一致的显示与边界处理，后续维护也需要重复修改。

## What Changes

- 合并已验证语义一致的 TypeScript 类型、常量和纯展示/解析函数到职责明确的共享模块。
- 以领域类型约束共享状态配置，删除不再需要的局部实现与测试 mock。
- 保留业务特有的状态文案和操作流程，不为仅名称相似的代码建立过度抽象。

## Capabilities

### New Capabilities

- `frontend-code-reuse`: 定义前端共享类型、常量和纯函数的复用边界。

### Modified Capabilities

<!-- 无。现有业务流程与 API 契约保持不变。 -->

## Impact

- 受影响区域：`src/config/`、`src/utils/`、构建相关 Stage Drawer 与对应测试。
- 不新增依赖，不修改路由、后端 API 或业务状态机。
