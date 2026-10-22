import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { KnowledgeBaseEvidenceStep } from '@/types/project/knowledge-base'

import type { FindingDetailModel } from './findingDetailPresentation'
import { EvidencePath, SourceEvidence } from './FindingEvidence'

const monacoProps = vi.hoisted(() => vi.fn())

vi.mock('@/components/MonacoEditor', () => ({
  default: (props: Record<string, unknown>) => {
    monacoProps(props)
    return <div data-testid="finding-source-editor" />
  }
}))

const steps: KnowledgeBaseEvidenceStep[] = [
  { id: 'first', title: '服务端步骤一', reason: '服务端说明一', status: 'partial' },
  { id: 'second', title: '服务端步骤二', reason: '服务端说明二', status: 'complete' }
]

function model(): FindingDetailModel {
  return {
    conclusion: {},
    fact: {},
    occurrences: [],
    defaultOccurrenceIndex: 0,
    evidenceChain: {
      steps,
      primaryPath: ['missing'],
      breaks: [{ stage: 'source-upstream', reasonCode: 'missing_input' }],
      budget: { truncated: true }
    },
    evidencePath: { steps }
  }
}

describe('backend evidence steps', () => {
  it('shows every step and its explanation without additional chain warnings', async () => {
    const onSelect = vi.fn()
    render(<EvidencePath model={model()} selectedIndex={null} onSelect={onSelect} />)

    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('服务端说明一')).toBeInTheDocument()
    expect(screen.getByText('服务端说明二')).toBeInTheDocument()
    expect(screen.getByText('分析不完整')).toBeInTheDocument()
    expect(screen.queryByText(/证据链存在断点/)).not.toBeInTheDocument()
    expect(screen.queryByText(/主证据路径未完整确认/)).not.toBeInTheDocument()
    expect(screen.queryByText(/证据搜索达到分析预算上限/)).not.toBeInTheDocument()
    expect(screen.queryByText('source-upstream')).not.toBeInTheDocument()
    expect(screen.queryByText('缺少完成判断所需的输入')).not.toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole('button', { name: /服务端步骤二/ }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('shows a neutral empty state when no steps are returned', () => {
    const empty = model()
    empty.evidencePath.steps = []
    render(<EvidencePath model={empty} selectedIndex={null} onSelect={vi.fn()} />)
    expect(screen.getByText('暂无结构化证据路径')).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })
})

describe('Finding source presentation', () => {
  it('keeps the hit line highlighted and underlines the exact matched code', () => {
    render(
      <SourceEvidence
        codeContext={{
          endLine: 12,
          highlightEndLine: 11,
          highlightStartLine: 11,
          lines: [
            { highlighted: false, lineNumber: 10, text: 'function add() {' },
            {
              highlighted: true,
              lineNumber: 11,
              text: '  return _mm256_add_ps(a, b);'
            },
            { highlighted: false, lineNumber: 12, text: '}' }
          ],
          startLine: 10
        }}
        highlightText="_mm256_add_ps"
        location={{ file: 'src/simd.c', span: { start: { line: 11 }, end: { line: 11 } } }}
        preferCodeContext
        showingEvidenceSource={false}
        onShowPrimaryContext={vi.fn()}
      />
    )

    expect(screen.getByTestId('finding-source-editor')).toBeInTheDocument()
    expect(monacoProps).toHaveBeenLastCalledWith(
      expect.objectContaining({
        highlightedLineNumbers: [2],
        highlightedRanges: [
          {
            endColumn: 23,
            endLineNumber: 2,
            startColumn: 10,
            startLineNumber: 2
          }
        ],
        language: 'cpp',
        revealLineNumber: 2,
        wordWrap: 'off'
      })
    )
  })
})
