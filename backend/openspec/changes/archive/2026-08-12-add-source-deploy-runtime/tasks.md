## 1. 数据库和生成代码

- [x] 1.1 使用 Liquibase 新增 `source_deploy_runs` 表、外键和索引
- [x] 1.2 更新数据库设计文档中的源码部署表说明
- [x] 1.3 运行 jOOQ 生成脚本并提交生成后的源码
- [x] 1.4 补充部署状态、部署策略和错误码常量

## 2. API 和业务服务

- [x] 2.1 新增源码部署创建接口 `POST /api/projects/{projectId}/source-deployments`，支持 `environmentIds` 批量部署
- [x] 2.2 新增源码部署分页列表接口，支持分页、排序和过滤
- [x] 2.3 新增源码部署详情接口 `GET /api/source-deployments/{sourceDeploymentId}`
- [x] 2.4 新增源码部署取消接口 `POST /api/source-deployments/{sourceDeploymentId}/cancel`
- [x] 2.5 实现项目权限校验、源码版本归属校验、环境归属校验和启用状态校验
- [x] 2.6 实现 `environment.working_directory` 缺失和源码工作副本缺失的错误处理
- [x] 2.7 实现 `force=false` 复用进行中或成功部署，`force=true` 创建新部署

## 3. SOURCE_DEPLOY 运行时

- [x] 3.1 新增 `SOURCE_DEPLOY` 任务类型和 Worker handler 注册
- [x] 3.2 实现远端部署路径生成规则 `<working_directory>/rvport-sources/<sourceRevisionId>`
- [x] 3.3 实现本机源码工作副本统计和 tar 打包输入流
- [x] 3.4 使用 SSH runtime 执行 tar over SSH 传输和远端目录替换
- [x] 3.5 写入任务进度、任务级日志事件、项目级 SSE 事件和 tool run
- [x] 3.6 失败时写入任务和 `source_deploy_runs` 失败状态，并脱敏错误摘要
- [x] 3.7 接入运行中任务取消，尝试终止本机打包和远端 SSH 命令

## 4. 安全和路径边界

- [x] 4.1 禁止源码部署创建请求传入任意 `remotePath`
- [x] 4.2 确保 API 响应、任务输入快照、SSE、日志和错误摘要不暴露后端本机路径
- [x] 4.3 对远端路径和远端 shell 命令参数进行安全 quote
- [x] 4.4 部署失败或取消时尽力清理远端临时目录

## 5. 测试

- [x] 5.1 补充正常流程测试：成功创建部署任务、成功复用部署、强制重新部署
- [x] 5.2 补充异常流程测试：无权限、跨项目源码、跨项目环境、禁用环境、缺少工作目录、缺少工作副本
- [x] 5.3 补充 edge case 测试：重复请求、非法分页排序参数、取消运行中部署、远端 tar 缺失
- [x] 5.4 补充 SSH/tar 传输相关轻量集成测试或可跳过真实环境测试

## 6. E2E 和验证

- [x] 6.1 在 API E2E 模块中新增源码部署用例
- [x] 6.2 使用真实或测试 SSH 环境验证源码版本可部署到远端工作目录
- [x] 6.3 验证部署任务状态、SSE 事件、任务日志和部署记录一致
- [x] 6.4 验证远端目录包含源码内容，并清理测试产生的远端目录和测试数据
- [x] 6.5 运行后端单元测试和相关 E2E 模块
