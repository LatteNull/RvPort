## ADDED Requirements

### Requirement: KB 工作流 API 必须区分执行事实和当前有效性
项目 overview、KB latest、readiness 和 KB 执行写接口 SHALL 复用同一当前构建与扫描上下文规则，不能仅凭源码存在或历史成功扫描认定当前阶段完成。

#### Scenario: 首次上传源码且尚未构建
- **WHEN** 项目已配置环境并上传源码，但没有 x86 构建和 KB 扫描记录
- **THEN** overview 的 KB SHALL 为 `PENDING` 且原因为 `KB_SCAN_MISSING`
- **AND** KB latest SHALL 为 `EMPTY`
- **AND** KB readiness 的 `X86_BUILD` SHALL 为 `MISSING`
- **AND** 创建 KB 扫描 SHALL 返回 `409 PREREQUISITE_NOT_SATISFIED`，错误详情包含 `stageId=kb` 及具有 key、status、reasonCode 的 prerequisite

#### Scenario: 历史成功不能代表当前完成
- **WHEN** 当前只存在旧源码、旧环境版本、旧构建或上下文不完整的成功扫描
- **THEN** overview 的 KB SHALL 为 `PENDING` 且原因为 `KB_SCAN_STALE`
- **AND** KB latest SHALL 返回 `STALE` 并保留历史执行状态
- **AND** readiness SHALL 按当前构建事实独立判断能否发起新扫描

#### Scenario: 当前扫描状态映射
- **WHEN** 存在完整匹配当前成功构建上下文的扫描记录
- **THEN** overview SHALL 将活动扫描映射为 `RUNNING`，成功映射为 `DONE`，失败、取消或超时映射为 `BLOCKED`
- **AND** latest SHALL 返回同一选择规则下的扫描及 `CURRENT`
- **AND** 当前失败扫描 MUST NOT 被更早成功结果覆盖

#### Scenario: 下一步推荐遵守构建顺序
- **WHEN** 环境和源码已就绪，x86 尚未成功，KB 无当前有效执行
- **THEN** overview SHALL 在 KB 之前推荐需要处理的 x86 构建
- **AND** 后端 MUST NOT 将 KB 描述为此时可立即开始的下一步

#### Scenario: 单次响应保持上下文一致
- **WHEN** 生成 overview、KB latest 或 KB readiness 时发生并发上下文变更
- **THEN** 后端 SHALL 通过一致读取或版本重验保证每个响应内部使用同一个上下文判定
- **AND** 不同请求之间真实发生的状态变化 SHALL 通过各自 context 和原因字段表达

#### Scenario: 安全且兼容的结果说明
- **WHEN** API 返回 KB 执行上下文、失效或降级原因
- **THEN** 后端 SHALL 保留既有路径、任务枚举和 latest 外壳，以领域字段表达构建 ID、版本和安全原因码
- **AND** 新增直接展示的说明 SHALL 同时提供中文和英文，例如 `message` 与 `message_en`
- **AND** 响应 MUST NOT 暴露服务器路径、凭据、完整任务输入或对象存储 key
- **AND** 无权限用户 SHALL 在读取这些事实前被拒绝
