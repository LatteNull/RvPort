import { describe, expect, it } from 'vitest'

import type { ProjectEvaluationReportFileContextBlock } from '@/types/project'

import { buildSourceContextPresentation } from './sourceContextPresentation'

const blocks: ProjectEvaluationReportFileContextBlock[] = [
  {
    endLine: 1433,
    kind: 'CODE',
    lineCount: 1,
    lines: [{ highlights: [], lineNumber: 1433, text: 'before' }],
    loadable: false,
    reason: null,
    startLine: 1433
  },
  {
    endLine: 4131,
    kind: 'OMITTED',
    lineCount: 2698,
    lines: [],
    loadable: true,
    reason: 'DISTANT_FINDING_GAP',
    startLine: 1434
  },
  {
    endLine: 4132,
    kind: 'CODE',
    lineCount: 1,
    lines: [{ highlights: [], lineNumber: 4132, text: 'after' }],
    loadable: false,
    reason: null,
    startLine: 4132
  }
]

describe('sourceContextPresentation', () => {
  it('keeps an omitted block between its surrounding model lines', () => {
    const presentation = buildSourceContextPresentation(blocks, [])

    expect(presentation.lines.map((line) => line.lineNumber)).toEqual([1433, 4132])
    expect(presentation.gaps).toEqual([
      expect.objectContaining({
        afterLineNumber: 1,
        endLine: 4131,
        lineCount: 2698,
        startLine: 1434
      })
    ])
  })

  it('keeps the unreturned remainder after a 2000-line partial load', () => {
    const loadedLines = Array.from({ length: 2000 }, (_, index) => ({
      highlights: [],
      lineNumber: 1434 + index,
      text: `loaded ${index}`
    }))
    const presentation = buildSourceContextPresentation(blocks, loadedLines)

    expect(presentation.gaps).toEqual([
      expect.objectContaining({
        afterLineNumber: 2001,
        endLine: 4131,
        lineCount: 698,
        startLine: 3434
      })
    ])
    expect(presentation.lines).toHaveLength(2002)
  })

  it('removes the gap only after every omitted line has been returned', () => {
    const loadedLines = Array.from({ length: 2698 }, (_, index) => ({
      highlights: [],
      lineNumber: 1434 + index,
      text: `loaded ${index}`
    }))

    expect(buildSourceContextPresentation(blocks, loadedLines).gaps).toEqual([])
  })
})
