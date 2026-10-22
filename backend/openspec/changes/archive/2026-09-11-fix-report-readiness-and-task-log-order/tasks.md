## 1. 修正报告 readiness

- [x] 1.1 修改报告阶段 readiness 计算：存在有效源码版本时让 `INCLUDED_FINDINGS` 始终为 `SATISFIED`，并在 `details.count` 中保留真实 confirmed 输入数量。
- [x] 1.2 保持缺少有效源码版本时的阻塞状态和稳定原因码，并确认报告创建入口与 readiness 使用相同事实判断。
- [x] 1.3 补充报告 readiness 与创建入口单元测试，覆盖有 confirmed 输入、零 confirmed 输入、缺少源码版本和非法跨项目源码版本等正常、边界及异常流程。

## 2. 修正完成态日志分页顺序

- [x] 2.1 重构 `TaskLogTailReader`，按“文件头最旧、文件尾最新”的追加日志格式实现从尾部计算 offset 的分页读取，并保持单页内容时间正序。
- [x] 2.2 保持 `merged`、`stdout`、`stderr` 独立 offset/lines、`returnedLines`、`totalLines` 和 `hasMore` 的现有响应结构与含义。
- [x] 2.3 补充读取器和日志服务单元测试，覆盖最新页、连续更早页、部分页、offset 越界、空文件、缺失文件、LF、CRLF、无末尾换行、UTF-8 多字节文本、超长单行及大型日志文件。
- [x] 2.4 确认任务级 SSE 和 `/log-increments` 不受修改影响，增量日志继续按事件顺序正序返回。

## 3. 同步契约与文档

- [x] 3.1 修正后端 API 文档中“最新日志位于文件头”以及“零 confirmed 输入阻塞报告”的过期描述。
- [x] 3.2 明确前端消费契约：更早页面整体前插，禁止反转单页日志行，并记录前端独立适配项而不在本后端 change 中修改前端代码。

## 4. 验证与质量门禁

- [x] 4.1 运行受影响的 readiness、报告服务、日志读取器和日志内容服务单元测试，确认正常流程、异常流程和 edge case 全部通过。
- [ ] 4.2 运行后端完整单元测试和覆盖率统计，将未被测试加载的项目自有源码纳入统计，确保项目整体及受影响模块行覆盖率至少 90%，工具提供分支覆盖率时分支覆盖率也至少 90%，并记录报告位置与合理排除项。
- [x] 4.3 使用已完成且超过两页的自动化测试任务执行 API/E2E 验证，确认首屏是最新页、页内正序、向前翻页无重复或缺失，并确认零输入评估报告可创建且生成全零成功报告。
- [x] 4.4 执行 `openspec validate fix-report-readiness-and-task-log-order --type change --strict`，确认 change artifacts 严格校验通过。
