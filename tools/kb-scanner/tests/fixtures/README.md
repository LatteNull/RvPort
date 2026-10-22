# Rule Fixtures

每个规则都需要在 `tests/fixtures/<ruleset>/` 下有一个对应目录。

目录约定：

```text
tests/fixtures/riscv-porting/<case-name>/
  src/
    *.cpp
  expected.json
```

`expected.json` 至少包含：

```json
{
  "ruleId": "C_CPP.X86.HEADER",
  "count": 1
}
```

新增规则时，如果没有补充对应 fixture，`test_each_riscv_porting_rule_has_fixture` 会失败。
