# 分析缓存维护说明

归约粒度修复使用 facts **1.5**、mapper **1.2**、evidence **1.2** 和 rule registry **1.3**。
facts 保存最近循环与累加器的稳定身份；source-facts key 随 schema/mapper 变化而失效。
evidence key 显式包含 evidence schema，旧绑定缓存不能复用。归约 binding ID 由自身关联
身份生成，bundle digest 仍用于来源校验，但不再让无关候选的变化扰动本候选 ID。

[English](analysis-cache.md) | 简体中文

schema 1.4 提供 `off`、`read-only`、`write-only` 和 `read-write` 四种模式。缓存根目录必须是
项目根目录内的绝对路径。缓存对象仅限 `source-facts`、`ir-facts` 和 `evidence`；最终 finding、
assessment、suppression 与 scan result 不缓存。

每个 key 固定包含 cache schema、对象类型及会影响语义的输入：源码与编译上下文、profile、
producer/Clang/LLVM 版本、artifact digest、mapping 配置和相关逻辑预算。条目包络校验 kind、
schema、key、payload 字节数、SHA-256 及依赖摘要。读取拒绝软链接、越界路径、超大、损坏或
不兼容条目，并以双语诊断降级为 miss；无法重新计算时沿用原分析失败语义。

发布采用同目录临时文件、flush、fsync 和原子 replace。相同 key 的并发 writer 只能发布相同
payload digest；冲突或发布失败不覆盖既有有效条目。缓存统计进入
`org.rvport.floating-point-scanner.runtime.cache`，但冷热命中计数不进入扫描 semantic digest。
回滚时把请求模式设为 `off`，缓存目录可作为派生数据安全移除。

单元测试覆盖命中/未命中、四种模式、输入变化、损坏包络、摘要冲突、大小限制、软链接、
fsync 失败、发布冲突以及源码/IR/evidence 冷热缓存语义一致性。

facts 1.4 / mapper 1.1 调整了来源分类、canonical scalar type 和 blocking dependency，因此
source-facts key 额外包含 facts schema、mapper version 与 source-location revision 4。旧 facts
1.3 条目必须表现为普通 miss，不能原地补字段或复用为新 assessment。冷缓存重算和新版本热缓存
的 assessments、findings、diagnostics、稳定 ID、排序及 semantic digest 必须完全一致。
