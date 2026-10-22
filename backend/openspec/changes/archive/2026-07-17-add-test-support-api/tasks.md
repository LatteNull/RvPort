## 1. 构建隔离

- [x] 1.1 新建 `src/test-support/java` 源码目录，并约定 test-support 代码只放在该目录下
- [x] 1.2 在 Maven 中新增 `test-support` profile，仅显式启用时加入 `src/test-support/java`
- [x] 1.3 验证默认 `mvn package` 不编译、不打包 test-support 类和资源
- [x] 1.4 验证 `mvn -Ptest-support package` 可以编译 test-support 源码

## 2. 安全边界

- [x] 2.1 从生产源码中移除或迁移现有 `DevSessionController`
- [x] 2.2 移除生产安全配置中 `/api/dev/session` 的 permit-all 规则
- [x] 2.3 在 test-support 源码中实现 test-support token 配置和校验
- [x] 2.4 为 `/api/test-support/**` 建立统一安全入口，缺失或错误 token 时拒绝请求
- [x] 2.5 增加测试确认 test-support API 不提供任意 SQL、任意 shell 或通用 Bean 调用入口

## 3. Test-support API 实现

- [x] 3.1 实现 `POST /api/test-support/session`，用于按用户名创建测试 session
- [x] 3.2 实现任务事件 fixture 和 SSE 推送触发接口
- [x] 3.3 实现 SSE heartbeat 触发接口
- [x] 3.4 实现用户 action token fixture 创建接口
- [x] 3.5 实现用户 action token 清理触发接口
- [x] 3.6 实现 pending task dispatch repair 触发接口
- [x] 3.7 实现可选的指定任务直接处理接口，并限制只能处理已存在任务
- [x] 3.8 实现测试邮件 outbox 分页查询和按 run id 清理接口
- [x] 3.9 实现 SBOM 轻量 fixture 创建接口
- [x] 3.10 实现任务队列、retry 队列和 dead-letter 队列状态摘要查询接口
- [x] 3.11 实现按 run id 或测试前缀清理 runtime 测试数据的接口

## 4. E2E 接入

- [x] 4.1 更新 E2E runner，支持配置 test-support base URL 和 token
- [x] 4.2 将需要稳定内部触发的 SSE、action token cleanup、mail outbox、task repair 用例接入 test-support API
- [x] 4.3 保留认证、任务创建、项目访问守卫和 SBOM 查询等真实主链路 E2E
- [x] 4.4 更新 E2E 清理流程，优先按 run id 调用 test-support runtime 清理
- [x] 4.5 增加 test-support 不可用时的明确失败或 skip 说明

## 5. 测试覆盖

- [x] 5.1 补充默认构建产物不包含 test-support 类的验证
- [x] 5.2 补充启用 `test-support` profile 后 API 可用的验证
- [x] 5.3 补充 test-support token 正常、缺失和错误场景测试
- [x] 5.4 补充 session 创建、用户不存在和敏感字段不泄露测试
- [x] 5.5 补充 SSE 事件触发、heartbeat 和任务项目不匹配测试
- [x] 5.6 补充 action token fixture、清理有效 token 不受影响和历史 token 清理测试
- [x] 5.7 补充 runtime 清理正常、空范围拒绝和不误删真实数据测试

## 6. 文档和验证

- [x] 6.1 更新后端 README 或 E2E 文档，说明生产构建与 test-support 构建命令差异
- [x] 6.2 更新 E2E 文档，说明 test-support token、运行命令、模块化用例和清理方式
- [x] 6.3 运行 `mvn test`
- [x] 6.4 运行默认 `mvn package` 并检查 jar 不包含 test-support 类
- [x] 6.5 运行 `mvn -Ptest-support package`
- [x] 6.6 使用 test-support 构建启动后端并运行相关 E2E 模块
