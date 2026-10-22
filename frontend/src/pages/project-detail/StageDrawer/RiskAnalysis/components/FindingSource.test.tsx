import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import FindingSource, { type FindingSourceState } from './FindingSource'

const editor = vi.hoisted(() => vi.fn())
vi.mock('@/components/MonacoEditor', () => ({
  default: (props: Record<string, unknown>) => {
    editor(props)
    return <pre aria-label="源码证据">{String(props.value)}</pre>
  }
}))
const finding = { id: 'finding-1', location: 'src/example.cpp' }
function source(): FindingSourceState {
  return {
    data: {
      findingId: finding.id,
      filePath: finding.location,
      lines: [
        { lineNumber: 80, text: 'float sum = 0;', highlighted: false },
        { lineNumber: 81, text: 'sum += value;', highlighted: true },
        { lineNumber: 85, text: 'return sum;', highlighted: true }
      ]
    }
  }
}
describe('专项源码展示', () => {
  it('显示真实源码行号，高亮及滚动使用片段内部行号', () => {
    render(<FindingSource finding={finding} source={source()} />)
    expect(editor).toHaveBeenLastCalledWith(
      expect.objectContaining({
        value: 'float sum = 0;\nsum += value;\nreturn sum;',
        lineNumbers: [80, 81, 85],
        highlightedLineNumbers: [2, 3],
        revealLineNumber: 2,
        readOnly: true
      })
    )
  })
  it('切换结果不展示上一条缓存片段', () => {
    render(<FindingSource finding={{ ...finding, id: 'finding-2' }} source={source()} />)
    expect(screen.queryByLabelText('源码证据')).not.toBeInTheDocument()
    expect(screen.getByText('分析结果未提供源码片段')).toBeVisible()
  })
  it('区分空结果与尚未提供源码，缺少位置时不引导按位置查找', () => {
    const state = source()
    state.data!.lines = []
    const { rerender } = render(<FindingSource finding={finding} source={state} />)
    expect(screen.getByText('本条结果没有可用的源码上下文')).toBeVisible()
    rerender(<FindingSource finding={{ ...finding, location: '未提供位置' }} />)
    expect(screen.getByText('分析结果未提供源码片段')).toBeVisible()
    expect(screen.getByText(/本条结果未提供源码位置/)).toBeVisible()
  })
})
