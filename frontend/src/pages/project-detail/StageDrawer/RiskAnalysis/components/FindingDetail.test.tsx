import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { finding } from '../fixtures.test-support'
import { presentFinding } from '../presentation'
import FindingDetail from './FindingDetail'

const editor = vi.hoisted(() => vi.fn())
vi.mock('@/components/MonacoEditor', () => ({
  default: (props: Record<string, unknown>) => {
    editor(props)
    return <pre aria-label="源码证据">{String(props.value)}</pre>
  }
}))
vi.mock('@/components/CodeMirrorEditor', () => ({ default: () => <div>原始 JSON</div> }))

describe('专项分析证据工作区', () => {
  it('切换位置复用覆盖范围内的同文件源码并重新高亮，范围外或不同文件不复用', async () => {
    const user = userEvent.setup()
    const model = presentFinding({
      ...finding,
      detail: {
        primaryOccurrenceId: 'main',
        occurrences: [
          { id: 'main', location: { file: 'a.cpp', line: 101 } },
          { id: 'related', location: { file: 'a.cpp', line: 104 } },
          { id: 'outside', location: { file: 'a.cpp', line: 200 } },
          { id: 'other', location: { file: 'b.cpp', line: 104 } }
        ]
      }
    })
    render(
      <FindingDetail
        finding={model}
        source={{
          data: {
            findingId: finding.id,
            filePath: 'a.cpp',
            lines: [
              { lineNumber: 101, text: 'result += lane;', highlighted: true },
              { lineNumber: 104, text: 'result += left[i] * right[i];', highlighted: false }
            ]
          }
        }}
      />
    )
    const select = async (label: string) => {
      await user.click(screen.getByRole('combobox', { name: '选择分析命中位置' }))
      await user.click(screen.getByText(label, { selector: '.ant-select-item-option-content' }))
    }
    await select('位置 2 · a.cpp:104')
    expect(screen.getByLabelText('源码证据')).toHaveTextContent('result += left[i] * right[i];')
    expect(editor).toHaveBeenLastCalledWith(
      expect.objectContaining({
        lineNumbers: [101, 104],
        highlightedLineNumbers: [2],
        revealLineNumber: 2
      })
    )
    await select('位置 3 · a.cpp:200')
    expect(screen.queryByLabelText('源码证据')).not.toBeInTheDocument()
    await select('位置 4 · b.cpp:104')
    expect(screen.queryByLabelText('源码证据')).not.toBeInTheDocument()
    await select('位置 1 · a.cpp:101')
    expect(editor).toHaveBeenLastCalledWith(
      expect.objectContaining({ highlightedLineNumbers: [1] })
    )
  })
  it.each(['MEMORY_ORDER', 'FLOATING_POINT'] as const)(
    '%s 支持证据步骤联动且不丢失有效源码',
    (analyzerType) => {
      const model = presentFinding({
        ...finding,
        analyzerType,
        detail: {
          evidenceChain: {
            steps: [
              {
                id: 'source',
                kind: 'sourceObservation',
                title: '命中表达式',
                source: {
                  file: 'test.cpp',
                  context: {
                    lines: [{ line: 80, text: 'sum += x;' }],
                    highlights: [{ line: 80, startColumn: 1, endColumn: 9 }]
                  }
                }
              },
              { id: 'conclusion', kind: 'conclusion', title: '分析判断' }
            ]
          }
        }
      })
      const { rerender } = render(<FindingDetail finding={model} />)
      expect(screen.getByRole('region', { name: '证据工作区' })).toBeVisible()
      fireEvent.click(screen.getByRole('button', { name: '源码观察：命中表达式' }))
      expect(screen.getByLabelText('源码证据')).toHaveTextContent('sum += x;')
      fireEvent.click(screen.getByRole('button', { name: '分析结论：分析判断' }))
      expect(screen.getByLabelText('源码证据')).toHaveTextContent('sum += x;')
      expect(screen.getByRole('button', { name: '分析结论：分析判断' })).toHaveAttribute(
        'aria-pressed',
        'true'
      )
      expect(
        within(screen.getByRole('region', { name: '建议下一步' })).getByText(finding.suggestion!)
      ).toBeVisible()
      rerender(<FindingDetail finding={{ ...model, id: 'another' }} />)
      expect(screen.queryByLabelText('源码证据')).not.toBeInTheDocument()
    }
  )
  it('没有结构化证据时提供真实空态，原始数据按需展开', async () => {
    render(<FindingDetail finding={presentFinding({ ...finding, detail: {} })} />)
    expect(screen.getByText('暂无结构化证据路径')).toBeVisible()
    expect(screen.queryByText('原始 JSON')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('原始扫描数据'))
    expect(await screen.findByText('原始 JSON')).toBeVisible()
    const rawPanel = screen.getByText('原始扫描数据').closest('details')!
    expect(within(rawPanel).getByText('收起详情')).toBeVisible()
    fireEvent.click(screen.getByText('原始扫描数据'))
    await waitFor(() => expect(screen.queryByText('原始 JSON')).not.toBeInTheDocument())
    expect(within(rawPanel).getByText('展开详情')).toBeVisible()
    fireEvent.click(screen.getByText('扫描事实'))
    await waitFor(() => expect(screen.getByText('判断可信度')).toBeVisible())
    expect(
      within(screen.getByText('扫描事实').closest('details')!).getByText('收起详情')
    ).toBeVisible()
  })
})
