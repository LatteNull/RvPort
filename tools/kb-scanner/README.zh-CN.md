# KB Scanner

[English](README.md) | 简体中文

面向 C/C++ x86 → RISC-V 迁移的静态知识扫描器。读取源码、可选编译数据库、已有构建信息及版本化 knowledge bundle；不执行被扫描工程的构建或测试。

## Docker 运行

从仓库根目录执行：

```powershell
docker compose -f tools/kb-scanner/compose.test.yml build kb-scanner-test
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test -m kb_scanner --help
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

扫描命令在开发容器内执行，输入只读挂载，输出使用独立可写目录：

```sh
python -m kb_scanner scan --input /input/project --rules rulesets/riscv-porting --output /tmp/scan --format json,html
```

默认输出 schema 2.0，可显式传入 `--schema-version 1.0`。一次发布 `scan-result.json`、`scan-report.html`、`scan.log`；版本失败不静默回退。`--exclude` 按逗号分隔的目录名称排除，`--exclude-path` 按项目相对目录精确排除并可重复指定。

## 结果解释

Finding 自包含事实、结论、occurrence 与证据链。缺失输入、关系歧义和预算耗尽必须保留 unknown/partial。readiness 只针对静态输入，固定 `staticScopeOnly=true`、`compiled=false`、`testsExecuted=false`；零 blocker 不表示已通过迁移编译。

## 文档

- [完整文档索引](docs/README.zh-CN.md)
- [能力与支持边界](docs/analysis-capabilities.zh-CN.md)
- [结果协议](docs/schema-v2-design.zh-CN.md)
- [知识维护](docs/knowledge.zh-CN.md)
- [开发与质量验证](docs/development.zh-CN.md)

设计与 change 见 [OpenSpec](openspec)。
