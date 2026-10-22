## MODIFIED Requirements

### Requirement: KB scanner 输出路径必须统一脱敏
KB scanner 的 result、evidence、stdout、stderr、scan log、tool run summary 和失败摘要 SHALL 通过与数据类型匹配的路径脱敏逻辑处理后才能进入 API 可见数据，并 MUST 保持结构化结果有效和源码证据语义完整。

#### Scenario: 脱敏 scanner evidence
- **WHEN** scanner finding evidence 中包含源码根目录、scanner 输出目录或其他服务器绝对路径
- **THEN** 后端 SHALL 在写入 `findings.evidence` 前脱敏服务器路径
- **AND** `findings.evidence` MUST NOT 保存服务器真实路径
- **AND** 后端 MUST NOT 修改 matched text、代码上下文或建议文本中的安全相对路径和源码表达式

#### Scenario: 脱敏 scanner 日志和错误摘要
- **WHEN** scanner stdout、stderr、scan log 或异常消息包含服务器路径
- **THEN** 后端 SHALL 在写入任务日志事件、tool run summary 或任务错误摘要前脱敏路径
- **AND** API 和 SSE MUST NOT 推送服务器真实路径

#### Scenario: 结构化脱敏 JSON 制品
- **WHEN** scanner 生成合法的 `scan-result.json`
- **THEN** 后端 SHALL 将其解析为 JSON 结构后递归处理路径语义字段并重新序列化
- **AND** 脱敏后的 `scan-result.json` SHALL 仍能被 JSON parser 成功读取
- **AND** 安全的项目相对路径 SHALL 保持不变
- **AND** 后端 MUST NOT 通过对完整 JSON 文本运行通用路径正则完成脱敏

#### Scenario: 保留源码中的相对 include
- **WHEN** finding matched text 或代码上下文包含 `#include "../compat/header.h"` 等相对源码表达式
- **THEN** 脱敏后的 finding evidence 和 `scan-result.json` SHALL 保留该源码文本
- **AND** 后端 MUST NOT 将其中的相对 include 替换为服务器路径占位符

#### Scenario: 嵌套 JSON 路径脱敏
- **WHEN** scanner 输出中的服务器绝对路径出现在嵌套 JSON object、array 或路径语义字符串中
- **THEN** 后端 SHALL 递归脱敏这些路径
- **AND** 后端 MUST NOT 只处理顶层字段

## ADDED Requirements

### Requirement: KB 扫描成功事实不得被归档候选登记异常反转
KB 扫描运行时 SHALL 区分 Scanner 执行、结果导入和制品保存失败与归档候选登记失败，避免把成功扫描误报为 Scanner 失败。

#### Scenario: Scanner 和结果导入成功
- **WHEN** Scanner 成功退出、schema v2 结果通过解析、findings 完成入库且必要制品保存成功
- **THEN** KB 扫描和对应任务 SHALL 进入 `SUCCEEDED`
- **AND** 后端 SHALL 尝试登记 KB 扫描归档候选

#### Scenario: 成功扫描后的归档候选登记失败
- **WHEN** Scanner、结果导入和制品保存已经成功，但归档候选登记发生异常
- **THEN** KB 扫描 SHALL 保持 `SUCCEEDED`
- **AND** 对应任务 MUST NOT 因该异常重新执行完整 Scanner
- **AND** 后端 SHALL 写入不包含敏感内容和服务器真实路径的 warning 或 tool run 后处理摘要
- **AND** 后端 MUST NOT 将错误信息概括为“KB Scanner 扫描失败”

#### Scenario: Scanner 或结果导入失败
- **WHEN** Scanner 失败、JSON 无效、schema 不兼容、findings 导入失败或必要制品保存失败
- **THEN** KB 扫描 SHALL 按实际失败阶段进入 `FAILED`
- **AND** 后端 SHALL 保留可诊断且已脱敏的阶段摘要

### Requirement: KB 导入安全修复必须覆盖三类测试
KB 导入、路径脱敏和归档登记修复 SHALL 具备正常流程、异常流程和 edge case 自动化测试。

#### Scenario: 正常流程覆盖
- **WHEN** 测试执行包含空 `paths`、安全相对路径和相对 include 的合法 schema v2 结果
- **THEN** 扫描 SHALL 成功导入并登记归档候选
- **AND** JSON 制品 SHALL 保持合法且源码证据不变

#### Scenario: 异常流程覆盖
- **WHEN** 测试输入包含服务器绝对路径、目录穿越、秘密字段或无效 JSON
- **THEN** 后端 SHALL 按对应安全或导入错误拒绝内容
- **AND** 错误响应、日志和摘要 MUST NOT 泄露被拒绝的敏感值

#### Scenario: edge case 覆盖
- **WHEN** 测试输入包含空数组、嵌套路径集合、Windows 与 Unix 路径、源码字符串中的斜杠以及归档登记异常
- **THEN** 后端 SHALL 保持安全相对内容、脱敏服务器路径并维持正确扫描终态
