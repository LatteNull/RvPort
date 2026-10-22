## 1. 文档与契约

- [x] 1.1 更新 `backend/docs/API_DESIGN.md`，补充人工修复节点、latest compare API、响应结构和错误空态。
- [x] 1.2 后端 change 不修改根目录 `docs/product/MVP_PAGE_STRUCTURE_AND_FLOW.md`；前端/产品文档按本 change 的 API 契约后续处理。
- [x] 1.3 后端 change 不修改根目录 `docs/product/MVP_INTERACTION_SPEC.md`；前端/产品文档按本 change 的 API 契约后续处理。

## 2. 后端 latest compare API

- [x] 2.1 新增 `GET /api/projects/{projectId}/source/compare/latest` 路由，并接入项目权限校验。
- [x] 2.2 实现 active source revision 和 previous source revision 的后端选择逻辑。
- [x] 2.3 返回 `NO_PREVIOUS_REVISION`、`NOT_STARTED`、`RUNNING`、`SUCCEEDED`、`FAILED` 等状态。
- [x] 2.4 复用 `recheck_runs` 和 `diff_items` 生成差异摘要与分页入口，不返回服务器真实路径。
- [x] 2.5 对无 active source revision、无权限项目、跨项目数据异常返回安全错误。

## 3. 源码更新后流程

- [x] 3.1 确认源码包上传成功后响应包含新 `sourceRevision` 摘要和 active 状态。
- [x] 3.2 确认 Git 同步成功后通过任务 summary/SSE 提供新 `sourceRevisionId`、commit 和 active 状态；创建接口保持返回任务。
- [x] 3.3 当前实现没有自动复检触发逻辑；latest compare 支持已有复检记录的 `RUNNING`、`SUCCEEDED`、`FAILED` 状态恢复。
- [x] 3.4 当前实现没有自动复检时，latest compare 返回 `NOT_STARTED` 且前端可展示空态。

## 4. Prototype

- [x] 4.1 Prototype 位于 backend allowed edit roots 之外，本 change 不实施；后续由前端/prototype change 按契约处理。
- [x] 4.2 Prototype 位于 backend allowed edit roots 之外，本 change 不实施；后续由前端/prototype change 按契约处理。
- [x] 4.3 Prototype 位于 backend allowed edit roots 之外，本 change 不实施；后续由前端/prototype change 按契约处理。
- [x] 4.4 Prototype 位于 backend allowed edit roots 之外，本 change 不实施；后续由前端/prototype change 按契约处理。

## 5. 测试与验证

- [x] 5.1 补充 latest compare 正常流程单元测试：存在 current/previous 且有已完成复检记录。
- [x] 5.2 补充 latest compare 异常流程单元测试：无权限、无 active revision、跨项目数据异常。
- [x] 5.3 补充 latest compare edge case 单元测试：只有一个源码版本、比较任务运行中、比较尚未生成。
- [x] 5.4 更新 API E2E 模块，覆盖源码更新后调用 latest compare 的主流程。
- [x] 5.5 运行后端单元测试和相关 E2E 模块，记录实际结果：`mvn test` 通过 317 个测试，跳过 2 个既有真实环境测试；`node e2e/runner.js run --module=project` 通过。
