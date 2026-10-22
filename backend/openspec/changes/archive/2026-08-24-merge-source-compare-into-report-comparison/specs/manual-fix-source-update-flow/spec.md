## ADDED Requirements

### Requirement: 人工修复后不再要求独立源码对比节点
人工修复流程 SHALL 在源码更新后引导用户重新执行后续分析和评估报告，并 SHALL 将历史差异查看交给评估报告比较能力。

#### Scenario: 源码更新后进入报告驱动流程
- **WHEN** 用户完成线下修复并上传源码包或执行 Git 更新
- **THEN** 系统 SHALL 创建新的源码版本
- **AND** 主流程 SHALL 引导用户重新执行必要分析并生成新的评估报告
- **AND** 主流程 MUST NOT 要求用户进入独立源码对比节点才能继续

#### Scenario: 查看历史差异
- **WHEN** 用户需要确认本次修复相对历史版本解决了哪些问题
- **THEN** 用户 SHALL 在评估报告页面查看历史报告并发起报告比较
- **AND** 后端 SHALL 使用报告比较 API 返回差异摘要和差异项

#### Scenario: 保留源码比较兼容入口
- **WHEN** 旧前端、E2E 或调试脚本调用源码 latest compare 或 recheck API
- **THEN** 后端 MAY 继续提供兼容响应
- **AND** 该兼容入口 SHALL NOT 作为人工修复主流程的推荐入口
