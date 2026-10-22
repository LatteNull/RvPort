## 1. 运行时可观测性边界

- [x] 1.1 实现集中式 Sentry 配置与初始化，支持 DSN 缺失时安全禁用、环境和 release 标签以及无 PII 默认策略
- [x] 1.2 在应用入口初始化 Sentry，并添加根级 Error Boundary 和可恢复的中文错误界面
- [x] 1.3 为 Sentry 初始化配置和错误恢复界面新增单元测试

## 2. 部署与配置

- [x] 2.1 在生产 Dockerfile 和根 Compose 中传递公开的 Sentry 构建变量，不传递私密令牌
- [x] 2.2 更新前端 README，说明 Sentry 配置、构建期语义、版本标记和验证步骤

## 3. 验证

- [x] 3.1 运行格式、lint、类型检查、单元测试和生产构建
- [x] 3.2 严格校验 OpenSpec change

## 4. React 19 工具链对齐

- [x] 4.1 在 React 19 root 配置未捕获和可恢复错误处理器，保留 Error Boundary 且避免重复采集
- [x] 4.2 让 Vitest 复用 React Compiler 配置，并统一 Node.js 24.18.0 LTS 基线
- [x] 4.3 修正错误恢复操作并补充相关测试与质量验证
