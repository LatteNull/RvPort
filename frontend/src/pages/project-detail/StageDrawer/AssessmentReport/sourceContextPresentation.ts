import type {
  ProjectEvaluationReportFileContextBlock,
  ProjectEvaluationReportFileContextLine
} from '@/types/project'

export interface SourceContextGap {
  afterLineNumber: number
  endLine: number
  id: string
  lineCount: number
  loadable: boolean
  reason: string | null
  startLine: number
}

export interface SourceContextPresentation {
  gaps: SourceContextGap[]
  lines: ProjectEvaluationReportFileContextLine[]
}

function missingRanges(
  block: ProjectEvaluationReportFileContextBlock,
  loadedLineNumbers: number[]
) {
  const ranges: Array<{ endLine: number; startLine: number }> = []
  let cursor = block.startLine

  loadedLineNumbers.forEach((lineNumber) => {
    if (lineNumber < cursor || lineNumber > block.endLine) return
    if (lineNumber > cursor) ranges.push({ endLine: lineNumber - 1, startLine: cursor })
    cursor = lineNumber + 1
  })
  if (cursor <= block.endLine) ranges.push({ endLine: block.endLine, startLine: cursor })

  return ranges
}

export function buildSourceContextPresentation(
  blocks: ProjectEvaluationReportFileContextBlock[],
  loadedLines: ProjectEvaluationReportFileContextLine[]
): SourceContextPresentation {
  const linesByNumber = new Map<number, ProjectEvaluationReportFileContextLine>()
  blocks.forEach((block) => {
    if (block.kind === 'CODE') {
      block.lines.forEach((line) => linesByNumber.set(line.lineNumber, line))
    }
  })
  loadedLines.forEach((line) => linesByNumber.set(line.lineNumber, line))

  const lines = [...linesByNumber.values()].sort(
    (left, right) => left.lineNumber - right.lineNumber
  )
  const loadedLineNumbers = loadedLines
    .map((line) => line.lineNumber)
    .sort((left, right) => left - right)
  const gaps = blocks
    .filter((block) => block.kind === 'OMITTED')
    .flatMap((block) =>
      missingRanges(block, loadedLineNumbers).map(({ endLine, startLine }) => ({
        afterLineNumber: lines.findIndex((line) => line.lineNumber >= startLine),
        endLine,
        id: `${startLine}-${endLine}`,
        lineCount: endLine - startLine + 1,
        loadable: block.loadable,
        reason: block.reason,
        startLine
      }))
    )

  return {
    gaps: gaps.map((gap) => ({
      ...gap,
      afterLineNumber: gap.afterLineNumber < 0 ? lines.length : gap.afterLineNumber
    })),
    lines
  }
}
