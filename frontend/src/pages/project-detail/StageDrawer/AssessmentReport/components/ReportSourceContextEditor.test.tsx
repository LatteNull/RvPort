import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import type { MonacoEditorSourceGap } from '@/components/MonacoEditor'
import { renderWithQueryClient } from '@/test/test-utils'
import type { ProjectEvaluationReportFileContext } from '@/types/project'

import ReportSourceContextEditor from './ReportSourceContextEditor'

const { getContext } = vi.hoisted(() => ({ getContext: vi.fn() }))
vi.mock('@/api/project/assessment-report', () => ({
  getProjectEvaluationReportFileContext: getContext
}))
vi.mock('@/components/MonacoEditor', () => ({
  default: ({ sourceGaps, value }: { sourceGaps: MonacoEditorSourceGap[]; value: string }) => (
    <div>
      <pre>{value}</pre>
      {sourceGaps.map((gap) => (
        <button key={gap.id} disabled={gap.loading} onClick={gap.onLoad}>
          {gap.id}
        </button>
      ))}
    </div>
  )
}))

it('tracks overlapping source range loads independently until each settles', async () => {
  const context: ProjectEvaluationReportFileContext = {
    blocks: [10, 20].map((line) => ({
      startLine: line,
      endLine: line,
      lineCount: 1,
      kind: 'OMITTED',
      lines: [],
      loadable: true,
      reason: null
    })),
    contentHash: 'hash',
    contextAvailable: true,
    fileKey: 'file-1',
    findings: [],
    relativePath: 'example.c',
    reportId: 'report-1',
    sourceRevisionId: 'source-1',
    totalLines: 30,
    unavailableReason: null
  }
  const complete = new Map<number, (value: ProjectEvaluationReportFileContext) => void>()
  getContext.mockImplementation(
    (_report, _file, { fromLine }: { fromLine: number }) =>
      new Promise((resolve) => complete.set(fromLine, resolve))
  )
  renderWithQueryClient(
    <ReportSourceContextEditor
      context={context}
      fileKey="file-1"
      reportId="report-1"
      revealFindingKey={0}
    />
  )
  fireEvent.click(screen.getByRole('button', { name: '10-10' }))
  fireEvent.click(screen.getByRole('button', { name: '20-20' }))
  expect(screen.getByRole('button', { name: '10-10' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '20-20' })).toBeDisabled()
  await waitFor(() => expect(getContext).toHaveBeenCalledTimes(2))
  const result = (line: number): ProjectEvaluationReportFileContext => ({
    ...context,
    blocks: [
      {
        startLine: line,
        endLine: line,
        lineCount: 1,
        kind: 'CODE',
        lines: [{ lineNumber: line, text: `line ${line}`, highlights: [] }],
        loadable: false,
        reason: null
      }
    ]
  })
  await act(async () => complete.get(10)!(result(10)))
  expect(screen.getByRole('button', { name: '20-20' })).toBeDisabled()
  expect(screen.getByText('line 10')).toBeInTheDocument()
  await act(async () => complete.get(20)!(result(20)))
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(screen.getByText(/line 10\s+line 20/)).toBeInTheDocument()
})
