import { describe, expect, it } from 'vitest'

import type { ProjectTaskLogContent } from '@/types/project/task-log'

import { composeTaskLogContent } from './taskLog'

function page(content: string, offset = 0): ProjectTaskLogContent {
  return {
    content,
    offset,
    returnedLines: content ? content.split('\n').length : 0,
    totalLines: 5,
    lines: 100,
    hasMore: offset === 0,
    logId: 'log-1',
    type: 'merged'
  }
}

describe('completed task log order', () => {
  it('preserves the backend line order and blank lines on the latest page', () => {
    expect(composeTaskLogContent([page('compile\n\nfinished')])).toBe('compile\n\nfinished')
  })

  it('prepends older pages without changing either page or its lines', () => {
    const pages = [page('link\nfinished'), page('configure\ncompile', 2)]
    expect(composeTaskLogContent(pages)).toBe('configure\ncompile\nlink\nfinished')
    expect(pages[0].content).toBe('link\nfinished')
  })

  it('does not add blank lines for empty pages', () => {
    expect(composeTaskLogContent([page('finished'), page('', 1)])).toBe('finished')
    expect(composeTaskLogContent([])).toBe('')
  })
})
