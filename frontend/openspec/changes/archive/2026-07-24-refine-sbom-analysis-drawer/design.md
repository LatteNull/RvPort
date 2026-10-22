## Context

SBOM 分析的用户主任务是查看和判断组件替代结果，分析运行过程是结果的可追溯信息。当前实现以阶段状态为中心，打开即查询两个环境列表，以 Modal 配置，并用 `/components` 构建结果表。

## Goals / Non-Goals

**Goals:**

- 将组件替代结果作为 SBOM Drawer 主内容。
- 统一 Drawer 内视图切换和关闭行为。
- 减少无效环境请求，并只展示可用于分析的环境。
- 使 API 类型、数据转换、测试与已确认的后端契约一致。

**Non-Goals:**

- 不实现后端 API 或迁移输入后端能力。
- 不在前端猜测或聚合完整替代统计。
- 不在本 change 中改造其他流水线 Drawer。

## 知识库扫描对齐

知识库扫描同样以单次扫描为主实体：主视图读取 `GET /projects/{projectId}/kb-scans/latest`，并据此显示无扫描、执行中、失败或“概览 + 最新扫描结果”。`GET /projects/{projectId}/kb-scans` 只用于次级“扫描记录”视图，绝不再以列表第一页推断当前扫描。

知识库扫描配置、Finding 详情和扫描记录均为 Drawer 内次级视图；完成态的“重新扫描”放在概览区，而不是 footer。后端 `latest` 契约未完成期间，Mock 提供相同返回形状。

## Design

### Drawer 视图

```text
overview
  ├─ 空状态 / 运行状态 / 失败状态
  ├─ 概览
  └─ 替代性结果表
configure
analysis-info
result-detail
history
```

`overview` 允许关闭 Drawer。次级视图显示返回入口，并禁止遮罩、Esc 与右上角关闭；`configure` 的 footer 仅承载取消和提交。

### 数据读取

- 主视图调用 `GET /projects/{projectId}/sbom-analyses/latest`。无分析时返回 `analysis: null`。
- 成功分析的结果表按需调用 `GET /sbom-analyses/{analysisId}/results`。
- 结果详情调用 `GET /sbom-analyses/{analysisId}/results/{resultItemId}`。
- 分析信息视图组合既有分析详情、采集详情、产物和分析记录接口。
- 仅 `configure` 视图启用环境列表 query。后端支持后使用 `status=AVAILABLE`，前端再按角色及 `basicInfo.snapshotId` 过滤。

### 契约依赖与降级

`latest`、`results`、结果详情和环境 `status` 筛选必须由后端提供后才可进入真实联调。实现期间 mock 与类型应按目标契约建立；生产请求不得回退至“列表第一条”或 `/components` 伪装正式结果。

当前后端创建分析只接受源/目标环境 ID，并在运行时重新采集快照。前端配置提交将只传这两个环境 ID；检查快照用于环境可选资格，而非提交字段。

## Risks / Trade-offs

- 后端契约尚未到位时，结果主视图无法对真实服务完全联调；需要明确的 mock 边界和接口待接入状态。
- 结果项迁移输入接口未定义，隐藏该操作会减少当前可用操作，但避免前端使用错误的组件 ID 契约。

## Testing

- 覆盖空、运行、失败、完成及重新分析确认状态。
- 覆盖进入/退出配置、延迟单次环境查询和环境可选过滤。
- 覆盖最新分析、结果表、详情和分析信息视图的 API 映射与错误反馈。
