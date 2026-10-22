## Context

- 当前工作台有十二个阶段。x86 构建独立成列，知识库扫描与依赖分析并列，结果汇合后进入评估报告。
- 活动 change `inline-project-stage-workspace` 已实现 Workflow Drawer 与 Step Panel 两种载体，路由使用 `/projects/:id/workflow/:stageId` 和 `/projects/:id/steps/:stageId`。本 change 沿用这些实现，不复制阶段内容，也不恢复旧 `panel` 查询参数。
- 两套工具位于 `tools/memory-order-analyzer` 和 `tools/floating-point-precision-scanner`。Java 后端已发布对应任务、readiness、结果与 Workflow 阶段（d64b3362）。
- 后端生产设计将工具安装在 `backend-worker`，由本地子进程运行。各自 `Dockerfile.dev` 用于开发验证；前端无需管理工具镜像或容器。

## Goals / Non-Goals

目标：提供两项分析的可理解入口；沿用现有阶段状态体系；接入真实任务与结果；保持现有流程可用。

非目标：实现分析算法、构建或下载 Bitcode、修改后端部署、猜测接口或风险结论、重设计节点样式、引入移动端布局。

## Decisions

### 1. 四项分析共用 x86 构建后的并行列

显示名称使用“强弱内存序分析”和“浮点精度扫描”。x86 构建保持独立的一列，知识库扫描、依赖分析和两项新分析位于后一列，上下分布并保持间距；分组框、汇合线、反馈线及标签随布局调整，避免交叠。四项分析从上到下依次为依赖分析、知识库扫描、强弱内存序分析、浮点精度扫描；统一 130px 纵向间距，整列围绕 x86 构建的中心对齐。Step 使用同一顺序列出。

两项新分析的输入关系为 `x86-build -> 分析节点`。它们使用当前源码版本的共享 Bitcode；构建成功不保证制品可用，节点展示依赖与实际执行 readiness 分离。BC 的可用状态、profile/capability 和版本兼容性由后端检查，浏览器不自行解析 manifest 或推断扫描可执行。

两项分析与评估报告的汇合关系、输入数量和必需性按后端确认的报告输入规则实现，不能假设四项分析都必须完成。画布拓扑不能替代实际报告 readiness。

### 2. 沿用既有阶段状态

两项分析沿用 `PENDING`、`RUNNING`、`DONE`、`BLOCKED` 阶段事实状态，以及已有 `READY`、`WAITING`、`BLOCKED` 展示辅助状态。节点展示与执行规则保持和现有阶段一致，不新增能力占位状态或单独的服务接入页面。

### 3. 已确认的后端契约（2026-09-30）

- 正式阶段 ID 为 `memory-order-analysis`、`floating-point-analysis`，两个节点未执行时显示 pending。浮点扫描旧的暂定 ID 不再作为有效阶段入口。
- 项目范围下使用 `/projects/{projectId}/memory-order-analyses`、`floating-point-analyses`：POST 无业务参数，返回 TaskResponse；GET 支持分页历史；`/latest` 返回 DomainLatest；`/{runId}` 返回执行详情；`/{runId}/findings` 返回服务端分页和筛选。独立 finding 详情位于 `/projects/{projectId}/memory-order-findings/{id}` 或 `floating-point-findings/{id}`。
- readiness 的前置条件为 ACTIVE_SOURCE、X86_BUILD、SPECIALIZED_ANALYZER。创建服务进一步检查编译数据库、Bitcode v2 manifest/bundle 和 artifactSetId。前端不能通过构建成功推断 Bitcode 可用；创建失败显示服务端原因、刷新 readiness，允许修复后重试。
- 运行状态为 PENDING/QUEUED/RUNNING、COMPLETE/COMPLETE_WITH_RISK/PARTIAL、FAILED/CANCELLED/TIMEOUT。执行完成不表示没有风险；findingCount 与 candidateCount 分开展示。PARTIAL 和 diagnosticCount 提示不完整范围；原始 finding.detail 保留 unknown/skipped/failed 等工具证据。
- 最新记录与历史详情均保留源码版本、构建记录、制品集合、新鲜度。旧源码结果可以查看，不能加入当前源码报告；source/context 变更会失效两项分析和 readiness 查询。
- Cookie/CSRF 和错误处理复用 request-client；创建通过 useSessionMutation 锁定提交和会话。打开页面不创建任务，不用失败回退或示例填充空记录。
- 任务事件消费既有项目 SSE，刷新两项分析查询、readiness 和共享 Overview。日志复用 TaskLogPanel，只在用户展开时订阅或加载；没有第二个 Overview 订阅或常驻轮询。
- `/{runId}/artifacts:download?format=json|html|audit` 下载已有结果。requestArtifactId 只用于身份记录，后端下载接口不支持 request 格式，因此不提供此按钮。
- 后端没有专项分析源码上下文接口，finding.detail 是完整工具 JSON 而不是源文件。界面显示文件/行位置、真实影响与建议，以及只读原始证据；明确提示未提供源码片段，不再拼接演示代码。
- FLOATING_POINT_FINDING、MEMORY_ORDER_FINDING 复用 migration-input 的候选、确认、排除流程。仅发布结果可操作；不自动确认候选，不改变既有报告必需条件和 2/2 汇合计数。报告来源及归档节点增加中文名称。
- Bitcode DTO 补齐 legacy/sourceIdentityDigest/compileContextDigest/bundleSha256；旧协议制品提示重新构建生成 v2。

### 4. 两种载体共享分析内容

两项分析按阶段 ID 配置复用分析业务组件，共享阶段载体、列表与源码证据组件。根页面组合请求 Hook、领域展示模型及子组件，保持现有关闭、刷新、未保存更改、详情返回、分页/筛选与正文滚动规则。

接入真实 API 后，根视图围绕“能否分析、正在执行什么、得到了什么结论、下一步如何处理”组织内容。高风险、未知及部分覆盖明确表达；没有 finding 不等于无风险，也不等于全程序安全。分析执行成功与业务风险分开呈现。

## Delivery Strategy

1. 基于已有工具 Schema 和示例，建立固定数据与展示模型，完成两个节点、导航、历史及结果详情；可先交付示例展示。
2. 真实契约已核对并替换数据源，补齐 readiness、任务创建/取消、任务日志、结果下载、任务事件刷新及可选报告输入。未满足输入的真实任务联调和归档仍保持未完成。
3. 报告汇合变化仅在确认后端纳入规则后启用；示例数据不得改变现有报告计数或门禁。全部接口接入与验证完成后归档本 change。

## Risks

- 前端暂定 ID 与后端实际 ID 不一致：在领域边界统一调整，不保留散落的隐式兼容判断。
- 扩展报告输入误伤现有流程：按确认的输入范围和必需性更新汇合计数、阻塞传播与 readiness 消费，并验证既有报告行为。
- 两节点增加画布高度：检查分组、汇合通道及反馈标签；沿用支持的桌面宽度与平移缩放能力。
- 部分或零风险结果被误读：完整性、分析边界与风险结论分别显示，并以真实响应为依据。

## Verification

文档阶段运行 change 严格校验、文档格式与差异检查。实施阶段遵循 `openspec/project.md` 验证矩阵，覆盖拓扑、既有阶段状态、深链接、双载体、任务失败与恢复、事件刷新、完整性与报告计数，并进行有认证的桌面浏览器验收。未执行的 API 或浏览器验证必须明确记录。

## 2026-09-29 示例展示交付记录

- 暂定前端 ID：`memory-order-analysis`、`floating-point-scan`。后端尚无对应 Java 接口与 stage ID，后续统一核对映射。
- 两节点与知识库、依赖分析位于 x=760 的分析列，x86 构建保留 x=520 的独立列。示例节点只连接 x86 输入，不接入报告汇合。报告前置仍为 `kb`、`rv-dependency-analysis`，计数仍为 n/2。
- 后端缺失新阶段事实时，展示示例 DONE 和“示例结果”/“示例数据”；后端明确提供阶段事实时，节点优先采用该事实。示例不会进入 Overview、真实任务或报告缓存。
- 数据层 `StageDrawer/RiskAnalysis/exampleProvider.ts` 提供固定结果，`types.ts` 定义前端展示模型，不作为 Java DTO。三个记录覆盖候选风险、部分分析/未知/跳过、零风险。
- Workflow Drawer 与 Step Panel 复用同一懒加载组件。支持搜索、等级筛选、风险详情与只读源码证据，返回保留筛选，关闭/阶段切换重置预览状态。没有模拟启动、重试或真实任务日志。
- 已在登录态 Chrome 检查 Workflow、报告 0/2、内存序抽屉与部分/空结果、浮点 Step 和详情返回，检查 1920、1440、1280 桌面宽度；真实接口、任务及报告纳入规则待后端发布。

验证结果：格式检查、全量 lint、typecheck、生产构建、OpenSpec 严格校验和 `git diff --check` 通过；全量单测 98 文件 / 519 用例通过。构建有现有大 chunk 提示，jsdom 有 Ant Design 的伪元素计算提示。后端目录没有代码差异。

### 示例分析页的展示调整

风险列表使用可通过键盘打开的完整条目，按等级、风险标题、迁移影响与源码位置建立阅读顺序；搜索、等级筛选和分页保持不变。顶部以自然语言摘要表达分析结论，范围和输入作为次要信息；不直接堆放工具包名、Schema 名称或原始 verdict。示例来源保留简短标签及可访问的说明。

风险详情优先呈现问题描述和源码证据，在足够宽的正文中将源码与影响/修复/验证建议并排；较窄的正文自动上下排列。证据复用统一主视口和只读编辑器，标出相关行。分析边界使用可展开区域，用户可以查阅假设与限制。Workflow Drawer 与 Step Panel 共用此布局，保留详情返回筛选状态与阶段关闭重置行为。

本次展示调整已在登录态浏览器验收内存序 Drawer、浮点 Step 及 1920/1440/1280 宽度；筛选往返与边界展开正常。本阶段 7 用例及调整后的全量 98 文件 / 519 用例通过，生产构建通过。最后一次全局 typecheck、lint、format 检查受到工作区并行新增的 `frontend-diagnosis-*` 测试文件影响（未使用导入、环境输入字段类型和缺失 `hasMore` 等）；本阶段文件的 lint 和格式检查通过，诊断测试文件没有修改。

展示层次补充：摘要用浅底色和语义风险图标建立重点，空结果使用中性检索图标；风险条目默认柔和底色，悬停加强反馈。详情将修复建议优先放在右侧浅蓝区域，迁移影响/验证保持辅助层级；源码使用完整的阅读底色与文件头。保持现有字体与阶段布局，不增加指标格或装饰阴影。

### 与现有阶段的排版一致性

对照依赖分析、评估报告、知识库扫描及公共阶段标题样式，摘要与区域标题采用 16px / 600 / 24px，详情正文采用 14px / 22px，列表说明采用 13px / 20px，辅助信息采用 12px / 20px。区域间距收敛为 24px，内容内边距与详情建议间距为 16px，标题与正文间距为 8px，列表内部文本间距为 4px；移除此前 18、22、28、32px 的自定义间距。文字颜色复用 Ant Design 主题变量，保留已确认的浅色分组和源码布局。

本次仅调整分析模块样式，浏览器检查 1920、1440、1280 桌面宽度的 Workflow / Step 列表与详情；阶段 7 项测试、生产构建、模块 lint、格式检查及 OpenSpec 严格校验通过。

继续对照测试项目 38 的真实知识库扫描列表与源码详情：分析结果入口复用公共 20px 阶段标题；列表使用“概览标题与记录选择、摘要、风险列表标题、左对齐筛选、列表”的排列。示例标识并入概览标题行及详情状态行，取消详情独立工具栏。风险等级改用 Ant Design Tag，与风险标题同行，正文和源码位置统一左对齐。详情区域间距采用 16px，保留源码与建议并排。浏览器确认 1920/1440 的 Workflow 与 1280 的 Step 展示；typecheck、模块 lint、7 项测试、构建通过。

源码证据展示改为复用公共 FindingDetail 的 `evidenceWorkspace`、顶部文件位置栏与 `findingCodeEditor` 样式，使用知识库扫描及报告源码区相同的 MonacoEditor。移除独立的浅灰外层、16px 外包内边距及第二层文件卡片；文件路径与行号放在同一紧凑顶部栏，编辑器贴合面板，保留只读、相关行高亮与统一主视口。测试替身同步切换为 MonacoEditor，阶段 7 项测试、typecheck、lint 与构建通过。

公共标题层级减重：阶段/记录标题由 20px / 600 调整为 18px / 500 / 24px，并同步各阶段已有的标题覆盖。公共源码证据栏标题使用 15px / 500 / 22px，文件路径使用 13px / 400 / 20px 与次要文字颜色。浏览器检查浮点详情的实际显示，生产构建通过。

## 2026-09-30 真实接口接入验证

- 独立检查正式 API 路径、请求参数、服务端分页及 TaskResponse。没有运行时示例数据或旧浮点 stage ID。
- 全套前端测试 121 文件、650 项通过；最后补充任务取消、浮点报告来源、零 finding 和失败恢复后，相关 5 文件、70 项增量回归通过。
- lint、typecheck、生产构建、format:check、OpenSpec strict 和 git diff --check 通过。构建仍有既有的大 chunk 提示。
- 在已认证 Chrome 中访问当前测试项目的两个正式 Workflow 深链接和浮点 Step 深链接：十四阶段顺序正确，专门分析从 x86 构建获得输入，报告显示 0/2；readiness、最新执行及历史接口可以读取，未配置源码/构建时展示真实阻塞与空状态，启动禁用。
- 当前测试项目没有源码及成功的 v2 构建制品，因此未启动真实分析，也未完成 worker 产物、任务日志、结果下载和报告写入的完整联调。任务 4.2 的这部分及 4.3 归档保留未完成。后端和 tools 未修改。

### 阶段样式一致性修正

前置条件、就绪空状态和请求失败改用依赖分析等阶段已有的 StageStateNotice，沿用其标题、正文、条件行、操作与 380px 初始状态区域；不再单独使用黄色 Alert 展示整块前置条件。刷新移到 StageSurface 的标题栏图标按钮。没有执行记录时隐藏记录选择器和重复空状态，未满足条件时不显示启动操作。Workflow Drawer 与 Step Panel 复用相同实现。
