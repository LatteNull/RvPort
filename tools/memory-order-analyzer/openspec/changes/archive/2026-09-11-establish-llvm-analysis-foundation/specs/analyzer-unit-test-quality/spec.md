## ADDED Requirements

### Requirement: Unit test all owned executable logic

项目 SHALL 为新增、修改、复用及现有自有可执行代码提供有有效断言的单元测试，覆盖正常、边界、异常和未知状态；范围 SHALL 包含 C++、Python、runner/cache/schema/report/质量脚本及 `doc/experiments/probe_bc.py` 自有逻辑。集成、编译冒烟、第三方扫描和文档检查 SHALL 不替代单元测试。

#### Scenario: Reuse an existing helper

- **WHEN** 从现有项目复用参数解析或产物校验代码
- **THEN** 记录来源并在本项目提供相应单元测试，不以原项目测试或历史运行成功代替

#### Scenario: Existing probe remains executable in this project

- **WHEN** 本项目仍提供 probe_bc.py 作为实验工具
- **THEN** 其自有逻辑纳入测试/覆盖范围，必要时可作可测性重构但保留历史证据含义

### Requirement: Enforce whole-project and module coverage thresholds

单元测试行覆盖率 SHALL 在项目整体、每个实现语言及本次受影响模块达到至少 90%；工具支持分支覆盖时对应分支覆盖率 SHALL 同样至少 90%。全项目 SHALL 按命中数/总数合并而非平均百分比，纳入未被加载或未被调用的自有源码；集成 profile SHALL 不混入单元覆盖统计。

#### Scenario: A new module is never imported by tests

- **WHEN** 某个自有 Python 模块没有被任何测试加载
- **THEN** 其可执行行仍计入总数，不能通过未加载而获得虚高覆盖率

#### Scenario: Line coverage passes but branch coverage fails

- **WHEN** 行覆盖率达到 95% 而可用分支覆盖率为 89%
- **THEN** 质量门槛失败，以非零退出且任务不能标记验收完成

#### Scenario: Integration tests increase measured coverage

- **WHEN** 集成测试命中了单元测试未触达的逻辑
- **THEN** 单元测试门槛仍只用单元 profile 计算，不能合并集成 profile 使其达标

### Requirement: Make coverage accounting auditable

质量报告 SHALL 列出统计源文件范围、排除项和理由、行/分支命中与总数、模块结果、命令和报告位置；只允许有依据地排除第三方、生成代码、测试框架和纯被测输入夹具，不得排除自有业务/工具逻辑。指标不支持 SHALL 明确注明，不得借此关闭原本可用的分支统计。

#### Scenario: A difficult error-handling file is excluded

- **WHEN** 覆盖配置试图把自有错误处理或 runner 逻辑排除
- **THEN** 验收拒绝该统计范围并要求补测，不以缩小范围或降低门槛通过

### Requirement: Provide a repeatable quality gate and exercise its failures

项目 SHALL 提供开发镜像内可重复执行的构建、单元测试、覆盖统计、门槛和独立集成测试入口；验收 SHALL 实际运行并记录结果。门槛逻辑本身 SHALL 有测试覆盖边界和缺失报告，不能在覆盖不足、测试失败或环境阻塞时声称完成。

#### Scenario: Coverage report is missing

- **WHEN** 质量入口无法获得任一自有语言或模块的预期报告
- **THEN** 以失败退出并指出缺失项，不跳过该语言/模块后声称通过

#### Scenario: Threshold boundary is tested

- **WHEN** 使用合成报告分别输入 89.99%、90% 和分支不足数据
- **THEN** 单元测试验证门槛分别失败、通过和失败，并检验全项目/模块范围均被执行
