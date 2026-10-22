## ADDED Requirements

### Requirement: 项目领域 API 保持稳定公共出口

系统 SHALL 将项目领域 API 的内部实现按领域模块组织，同时继续通过 `@/api/project` 提供现有的公共函数名称、参数与返回语义。

#### Scenario: 既有调用方访问项目领域 API

- **WHEN** 页面、hook 或测试从 `@/api/project` 导入既有项目领域函数
- **THEN** 导入路径、函数签名、请求 URL、请求体与响应映射保持不变

### Requirement: 重构后保留静态质量基线

系统 SHALL 在本 change 完成后不保留由未使用代码或 import 排序导致的 lint 错误，并保持项目 API 的既有单元测试意图。

#### Scenario: 执行前端静态检查与项目 API 测试

- **WHEN** 开发者执行 `pnpm lint` 与项目 API 相关单元测试
- **THEN** lint 以成功退出码完成，且 API 契约测试验证既有领域请求边界
