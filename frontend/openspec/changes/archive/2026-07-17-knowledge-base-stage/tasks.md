## 1. 知识库扫描数据边界

- [x] 1.1 在 `src/types/project.ts` 定义知识库扫描任务、扫描配置、扫描概览、Finding 列表、Finding 详情和加入状态类型。
- [x] 1.2 在 `src/api/project.ts` 增加当前扫描任务、Finding 列表与详情、创建扫描、加入迁移问题清单和导出报告的领域 API。
- [x] 1.3 在 `mock/project.ts` 按正式响应包络提供知识库扫描任务、结果、详情、创建和加入操作的 mock 状态。
- [x] 1.4 为新增领域 API 和 mock 状态流补充 `src/api/project.test.ts` 覆盖。

## 2. 知识库扫描 Drawer

- [x] 2.1 新增 `StageDrawer/KnowledgeBase` 组件、SCSS Module 和 `results`、`config`、`detail` 内部视图状态。
- [x] 2.2 实现扫描结果视图：三项概览、八列表格、横向滚动、临时选择、全选/取消全选和持久的未加入/已加入状态。
- [x] 2.3 实现表格工具栏的批量加入迁移问题清单操作、二次确认、禁用规则与成功后的状态刷新。
- [x] 2.4 实现结果区标题右侧的新建扫描入口，以及 Drawer Footer 的全局导出报告操作。
- [x] 2.5 实现 Drawer 内扫描配置视图，包含规则版本、扫描语言、扫描范围、两类排除规则、字段说明、取消返回和开始扫描提交。
- [x] 2.6 实现 Drawer 内 Finding 详情视图，按需加载只读 Monaco 代码上下文并展示规则来源、风险原因、修改建议和单项加入操作。
- [x] 2.7 为任务的加载、未开始、执行中、失败、空结果和可恢复错误状态提供一致的 UI 与重试路径。

## 3. 工作台与抽屉一致性

- [x] 3.1 在 `StageDrawer/index.tsx` 注册 `kb` 到知识库扫描 Drawer 的映射，并使节点点击传入当前项目上下文。
- [x] 3.2 创建扫描或加入迁移问题清单成功后失效 workflow 状态查询，使 `kb` 节点读取服务端返回的最新状态。
- [x] 3.3 统一现有阶段 Drawer 尺寸：含主结果表格的环境管理、SBOM 分析和知识库扫描为 `1100px`；项目创建和源码制品管理为 `800px`。
- [x] 3.4 确保配置与详情子视图隐藏关闭入口并阻止遮罩或键盘关闭，结果视图保留标准关闭行为。

## 4. 测试与交付记录

- [x] 4.1 为知识库扫描 Drawer 覆盖结果展示、配置提交、选择与加入、Finding 详情及失败/空态交互测试。
- [x] 4.2 在阶段实现完成后对照原型，将尚存的实现差异追加到根目录 `problem.md` 的待确认记录。
- [x] 4.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test` 和 `openspec validate knowledge-base-stage`。
