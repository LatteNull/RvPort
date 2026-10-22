## Why

`improve-library-provider-resolution` 已完成 provider 证据、仓库 metadata 和架构归一化匹配的实现与主 spec 同步，但归档时仍有真实环境验证、SBOM_ANALYSIS 联通验证、测试数据清理和完整测试执行项未完成。需要用一个独立收尾 change 补齐这些验证工作，避免实现已存在但缺少可复核证据。

## What Changes

- 补齐 x86 与 RISC-V 真实环境采集验证，记录 owner package、repo metadata、whatprovides、warning 和采集摘要。
- 使用真实采集结果触发或复现 `SBOM_ANALYSIS`，确认目标仓库候选不会因为 metadata 未准备而稳定为空。
- 增加或完善可复跑的验证脚本，输出非敏感记录文件，便于审计和问题定位。
- 补齐清理流程，清除 E2E、真实验证和运行时产生的测试数据，仅保留必要的非敏感记录。
- 执行 Maven 单元测试、SBOM analyzer 测试和可用的 API E2E 测试，并记录无法执行的前置条件。
- 不改变 SBOM 分析业务结论算法，除非验证暴露必须修复的缺陷。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `sbom-analysis-runtime`: 明确 SBOM provider resolution 必须有真实环境验证记录、可复跑输入输出和证据完整性检查。
- `api-e2e-test-suite`: 明确 SBOM 相关 E2E/真实验证需要纳入独立 E2E 运行和清理策略。

## Impact

- 影响 `backend/e2e` 下的 SBOM E2E 用例、运行脚本或清理脚本。
- 影响 `backend/runtime/real-records` 或等效非敏感验证记录目录。
- 可能影响 `tools/sbom-analyzer` 的测试 fixture 或验证输入输出样例。
- 可能影响 Java SBOM runtime、环境采集 runtime 的测试覆盖，但不引入新的数据库表或外部服务依赖。
