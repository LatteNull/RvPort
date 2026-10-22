# 双语建议合同样例

- `expected-pairs.json` 是人工编写的七组成对预期，单测逐字核验，不由运行时模板生成。
- `test_bilingual_suggestions.py` 将这些文案应用到既有 `schema-v2/complete.json` 的副本，作为当前双语正例执行真实 Schema/引用合同检查；原始文件仍用于历史缺省兼容。显式非法值和生产遗漏另有反例，不回写原文件。
- `report-differential.json` 来自独立容器对四组固定输入逐字段/逐字节审校后的结果。`strippedSha256` 是仅删除两段建议后的 V2 规范化哈希；规范化为 `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` 的 UTF-8 字节。
- `before` 保留旧 producer 的哈希；`after` 是当前 producer golden。旧 `source-evidence-chain/report-differential.json` 原样保留。V1 三份 artifact 字节相等，V2 日志字节相等，V2 HTML 仅对应建议段落变化。
- 全部样例是静态分析，不意味着执行了输入项目的编译或测试。测试与覆盖率记录见本 change 的 `verification.md`。
