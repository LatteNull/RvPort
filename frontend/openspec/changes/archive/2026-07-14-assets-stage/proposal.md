## Why

环境管理完成后，项目需要先确定一份当前有效源码，再并行启动全部源码分析支路。现有 `assets` 节点仍使用默认 Drawer，无法展示当前源码来源、更新源码或以正确语义启动下游分析。

## What Changes

- 为 `assets` 节点新增源码制品管理 Drawer，展示当前有效源码的来源、版本标识、来源元数据、版本说明和更新时间。
- 在 Drawer 内提供“上传源码压缩包”和“从 Git 更新代码”子视图；两种操作都直接覆盖当前有效版本，不引入版本历史列表或追溯模型。
- 上传操作支持受限压缩包、版本说明及上传后是否立即启动分析；Git 更新支持仓库地址、Ref 和可选的用户名加 Access Token，敏感凭据不回显。
- 将阶段主操作调整为“启动源码分析”。确认后固定并行启动 SBOM、知识库、纯 AI、内存模型、浮点精度和对齐与布局优化六条分析支路。
- 扩展 workflow 状态契约，使前端能够展示多个并行运行节点、六条活动边，以及源码扫描分组的视觉焦点和“源码分析 · 6 项进行中”的当前阶段摘要。

## Capabilities

### New Capabilities

- `source-artifact-management`: 当前有效源码制品的展示、压缩包上传、Git 更新及启动源码分析。

### Modified Capabilities

- `project-pipeline-workbench`: 支持源码制品确认后六条分析支路的并行状态、活动边和分组聚焦。

## Impact

- 影响 `StageDrawer` 路由、`Assets` 阶段组件、领域类型、`src/api/project.ts` 与 `mock/project.ts`。
- 影响 workflow 状态模型及当前阶段摘要映射，不改变 React Flow 固定拓扑、布局或节点编排能力。
- 不新增运行时依赖；文件上传使用 Ant Design 和浏览器 `File` 能力。
- 不包含二进制制品管理、版本历史/回滚、源码对比基线管理或实时任务订阅。
