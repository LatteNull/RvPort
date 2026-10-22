## ADDED Requirements

### Requirement: 缓存只能保存 canonical 中间产物
扫描器 SHALL 只缓存通过 schema 和摘要校验的 source facts、LLVM IR facts 与 AST↔IR evidence，不得缓存最终 findings、assessments、suppressions 或完整 scan result。每个 cache key MUST 包含对象 kind/schema/producer、源码和 compile-context digest、相关 profile/build-context fingerprints、Clang/LLVM/reader/extractor 版本、artifact digest、mapping 配置以及影响该层语义的预算。

#### Scenario: 规则版本变化
- **WHEN** canonical facts/evidence 输入不变但规则版本或 suppression 政策变化
- **THEN** 中间缓存可以命中，但规则、finding 和 suppression 必须重新计算

#### Scenario: 编译上下文变化
- **WHEN** 宏、标准、目标选项或响应文件展开后的语义参数变化
- **THEN** source facts cache key 变化且旧条目不得命中

### Requirement: 缓存读写必须完整、原子且限制在允许根
缓存读取 SHALL 校验路径边界、最大字节数、包络 schema、cache key、payload SHA-256 和依赖摘要。缓存写入 MUST 在目标同目录使用唯一临时文件，完整序列化、flush/fsync 后原子替换；并发 writer 只能发布相同 key 的相同 payload digest。软链接、路径穿越、未完成临时文件和根外绝对路径 MUST 被拒绝。

#### Scenario: 缓存文件摘要损坏
- **WHEN** cache key 对应文件的 payload 与声明 SHA-256 不一致
- **THEN** 条目按 cache miss 处理、发布聚合双语诊断并从可信输入重新计算，不消费损坏 payload

#### Scenario: 缓存原子替换失败
- **WHEN** 新条目 fsync 或 replace 失败且已有有效条目
- **THEN** 已有条目字节保持不变，新条目不得以正式名称出现

### Requirement: 缓存故障不得改变扫描结论
cache miss、损坏、不兼容、越界或并发发布冲突 SHALL 优先安全降级为重新计算；只有底层可信输入也不可用时，才按对应 source/IR/evidence 失败语义产生 partial/failed。缓存 hit/miss/corrupt 计数 MUST 与扫描语义摘要分离，冷缓存和热缓存 MUST 产生相同 assessments、findings、stable IDs、排序、diagnostics 语义和 scan semantic digest。

#### Scenario: 删除全部缓存后重扫
- **WHEN** 有效热缓存被完全删除后以相同请求重新扫描
- **THEN** 重新计算结果与此前热缓存结果语义等价，不要求恢复任何持久业务状态

#### Scenario: 只有缓存副本且原输入缺失
- **WHEN** 缓存损坏且生成该对象所需的源码或 BC 也不可用
- **THEN** 对应范围为 failed/unknown，不能把旧缓存内容当作成功结果

### Requirement: 缓存模式和统计必须显式
schema 1.4 请求 SHALL 支持 `off`、`read-only`、`write-only` 和 `read-write` 模式以及受边界校验的 cache root。结果 metadata SHALL 记录非语义性的对象级 hit/miss/corrupt/write 计数和 cache schema/version，但不得输出本地绝对 cache root。

#### Scenario: 缓存关闭
- **WHEN** 请求选择 `off`
- **THEN** 扫描器不读取或写入缓存，缓存目录的存在与内容不影响结果
