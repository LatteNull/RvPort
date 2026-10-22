# manual-repair Specification

## Purpose

定义评估报告后的修复路径引导，连接依赖处理、线下源码修复和构建验证，使用户按问题类型返回相应阶段完成修改，并理解更新当前源码后的验证步骤。

## Requirements

### Requirement: 人工修复问题处理引导

人工修复 Drawer SHALL 作为评估报告后的问题处理引导页，帮助用户根据问题类型选择依赖修复或源码修复路径。

#### Scenario: 选择依赖问题处理路径

- **WHEN** 用户需要处理缺失依赖、目标侧未安装或版本不兼容问题
- **THEN** 系统 SHALL 提供前往依赖分析的入口
- **AND** SHALL 说明用户可在依赖分析中确认替代包、目标侧匹配情况和迁移输入

#### Scenario: 选择源码问题处理路径

- **WHEN** 用户需要处理知识库扫描发现的源码问题或在线下修改源码
- **THEN** 系统 SHALL 提供前往源码管理的入口
- **AND** SHALL 说明更新后的当前源码版本将用于后续构建

#### Scenario: 修复后验证

- **WHEN** 用户完成依赖或源码修复
- **THEN** 系统 SHALL 提示用户更新当前源码版本并重新执行构建验证
- **AND** SHALL 提供前往构建验证的入口

### Requirement: 不提供在线修复

人工修复 Drawer SHALL NOT 提供在线代码编辑、自动 patch、一键修复、处理备注或修复记录保存能力。

#### Scenario: 用户需要修复问题

- **WHEN** 用户需要处理迁移问题
- **THEN** Drawer SHALL 引导用户在线下修改源码
- **AND** SHALL 将源码提交行为委托给源码管理阶段

### Requirement: 返回源码管理更新修复版本

人工修复 Drawer SHALL 将源码更新操作导向 `assets` 阶段的源码管理 Drawer，而不在人工修复 Drawer 内嵌上传或 Git 更新表单。

#### Scenario: 前往源码管理

- **WHEN** 用户在人工修复 Drawer 确认“前往源码管理”
- **THEN** 系统 SHALL 关闭当前人工修复 Drawer 并聚焦或打开 `assets` 阶段
