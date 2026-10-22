## 1. 范围与基线

- [x] 1.1 根据最终澄清撤回候选展示扩展，修订设计/规范：保留 fact、完整证据排除、未知保留。
- [x] 1.2 固定 55 条审校基线，区分人工数据用途与机器可证明范围，不将名单变为规则。

## 2. 分类准入与去重

- [x] 2.1 实现并单元验证只读 semantic-role proof 门禁，覆盖范围闭合、无证明/冲突/引用/配置、confirmed 不降级。
- [x] 2.2 分类过滤保留 facts/Observation 和聚合审计；无证明沿用保守规则，所有未决 candidate completeness 为 unknown。
- [x] 2.3 实现同 fact 完整 identifier 覆盖去重，补齐多 token/位置/配置与原事实需求不变的隔离单元。

## 3. 正确投影

- [x] 3.1 修正同 Evidence 的 intrinsic 标签、主事实选择与无 proof alternative 标签，补齐链/mapper 隔离单元。
- [x] 3.2 验证 V1/V2 schema、unknown suggestion/结论/链、上下文引用；不新增核心结构或候选展示字段。

## 4. 验收

- [x] 4.1 新 inventory 与独立 runner gate，修改业务模块逐个 90% line / 80% branch，纳入完整 runner。
- [x] 4.2 容器运行定向和完整回归，含原生崩溃缩减、AVX/未绑定 Backend::avx2、codec/SHA/CRC fact 保留及三态门禁。
- [x] 4.3 固定 libarchive 两次性能和逐项 55 条差异审校，保留无法判断项，说明没有自动角色证明。
- [x] 4.4 更新性能/审校记录、知识哈希与 OpenSpec 严格验证，不改生产容器或宿主依赖。
