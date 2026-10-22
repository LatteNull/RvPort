## 1. 恢复项目 Overview 最近任务

- [x] 1.1 扩展 `ProjectOverviewResponse`，恢复非空 `recentTasks` 字段并保持现有 overview 字段不变
- [x] 1.2 在 `ProjectService` 中复用任务仓储读取当前项目最近 5 条任务，保持 `createdAt DESC, id DESC` 的稳定排序
- [x] 1.3 更新 overview API 文档、服务单元测试和无任务 edge case 测试

## 2. 修正归档候选安全校验

- [x] 2.1 将敏感字段名判断收敛到凭据和对象存储内部字段，不再因字段名包含 `path` 拒绝候选
- [x] 2.2 保留对嵌套字符串值中绝对服务器路径、目录穿越、凭据和秘密内容的递归拒绝
- [x] 2.3 补充空 `paths`、安全相对路径、Windows/Unix 绝对路径、目录穿越及嵌套集合的正常、异常和 edge case 单元测试

## 3. 修正 KB 结果脱敏和导入状态

- [x] 3.1 为 `scan-result.json` 实现基于 Jackson JSON tree 的结构化路径脱敏和重新序列化
- [x] 3.2 区分路径语义字段与源码文本，保留相对 include、matched text 和代码上下文，仅脱敏服务器真实路径
- [x] 3.3 调整 HTML、scan log、任务日志和 tool run 摘要的脱敏策略，避免结构化制品使用无结构全文替换
- [x] 3.4 在保存脱敏 JSON 前后执行解析有效性校验，失败时返回明确的导入阶段错误且不保存损坏制品
- [x] 3.5 调整 KB 扫描完成顺序和异常边界，使归档候选登记失败仅记录安全 warning/后处理摘要，不反转扫描和任务成功状态或触发完整 Scanner 重试

## 4. 验证与回归

- [x] 4.1 扩展 KB runtime 测试，覆盖合法 `scope.paths`、嵌套绝对路径脱敏、`#include "../compat/header.h"` 保真和脱敏后 JSON 可解析
- [x] 4.2 扩展 KB runtime 异常测试，分别验证 Scanner、JSON/schema、导入、制品保存和归档登记失败的终态与错误分类
- [x] 4.3 运行相关 Java 单元测试及完整 Maven 测试，确认正常流程、异常流程和 edge case 全部通过
- [x] 4.4 更新并运行 overview 与 KB 模块 API E2E，验证最近任务响应、真实 KB 扫描成功、artifact 可下载及归档候选登记
- [x] 4.5 重新构建后端容器并使用此前失败场景回归，确认任务不再在 `IMPORT_RESULT` 阶段因合法 `paths` 失败
