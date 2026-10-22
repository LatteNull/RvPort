## Why

当前 `backend/e2e/runner.js` 只能串行运行全部 E2E case。新增或调试某个模块的 API 时，会被环境、任务、SBOM 等无关 case 的耗时和外部依赖影响，导致反馈周期过长，也增加了定位失败原因的成本。

## What Changes

- 为 E2E runner 增加按模块、按 case、按 tag 选择运行的能力。
- 为每个 E2E case 增加稳定 metadata，包括 `id`、`module`、`tags`、依赖说明和可选 post-run assertion 策略。
- 增加 `list` 命令，用于查看可运行模块、case 和 tag。
- 保留当前全量运行能力，默认行为仍可运行全部 E2E。
- 调整 runner 的公共 setup，使单独运行任意模块时仍会完成基础设施检查、管理员登录、临时解除 `must_change_password`、清理和恢复。
- 更新 E2E README 和覆盖矩阵，说明模块化运行命令和适用场景。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `api-e2e-test-suite`: E2E 测试套件需要支持模块化选择运行，并保证单模块运行具备独立 setup、清理和结果校验能力。

## Impact

- 影响 `backend/e2e/runner.js`、`backend/e2e/cases/*.js`、`backend/e2e/README.md`、`backend/docs/api-e2e-coverage.md`。
- 不改变后端业务 API、数据库 schema、生产运行逻辑或 Docker 基础设施。
- 不新增 npm 依赖；继续使用现有 Node.js 脚本和内置模块。
