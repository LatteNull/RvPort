import type { ProjectTaskLogContent } from '@/types/project/task-log'

export function composeTaskLogContent(logPages: ProjectTaskLogContent[]) {
  // 接口先返回最新页，但页内已按时间正序；只调整分页顺序，将更早内容放在前面。
  return [...logPages]
    .reverse()
    .flatMap((page) => (page.content ? page.content.split('\n') : []))
    .join('\n')
}

export function getTaskLogLineNumberOffset(logPages: ProjectTaskLogContent[]) {
  const totalLines = logPages[0]?.totalLines
  if (!Number.isFinite(totalLines)) return 1

  const loadedLines = logPages.reduce((sum, page) => sum + page.returnedLines, 0)
  return Math.max(1, totalLines - loadedLines + 1)
}
