import { useCallback, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { getProjectEvaluationReportFileContext } from '@/api/project/assessment-report'
import MonacoEditor, {
  type MonacoEditorHighlightRange,
  type MonacoEditorSourceGap
} from '@/components/MonacoEditor'
import type {
  ProjectEvaluationReportCodeFinding,
  ProjectEvaluationReportFileContext,
  ProjectEvaluationReportFileContextLine
} from '@/types/project'

import { projectQueryKeys } from '../../../queryKeys'
import { buildSourceContextPresentation, type SourceContextGap } from '../sourceContextPresentation'

import styles from '../index.module.scss'

function sourceLanguage(relativePath: string) {
  const extension = relativePath.split('.').pop()?.toLowerCase()
  if (extension === 'json') return 'json'
  if (extension === 'sh' || extension === 'bash') return 'shell'
  if (['c', 'cc', 'cpp', 'cxx', 'h', 'hh', 'hpp', 'hxx'].includes(extension ?? '')) return 'cpp'
  return 'plaintext'
}

function sourceHighlightRange(
  line: ProjectEvaluationReportFileContextLine,
  editorLineNumber: number,
  finding: ProjectEvaluationReportCodeFinding
): MonacoEditorHighlightRange | undefined {
  let startColumn: number
  let requestedEndColumn: number
  const findingStartLine = finding.lineStart ?? line.lineNumber
  const findingEndLine = finding.lineEnd ?? findingStartLine
  if (finding.columnStart) {
    startColumn =
      line.lineNumber === findingStartLine
        ? Math.max(1, Math.min(finding.columnStart, line.text.length + 1))
        : 1
    requestedEndColumn =
      line.lineNumber === findingEndLine
        ? (finding.columnEnd ?? startColumn + 1)
        : line.text.length + 1
  } else {
    const evidence = finding.sourceDetail.evidence
    const matchedText =
      evidence && typeof evidence === 'object' && !Array.isArray(evidence)
        ? (evidence as Record<string, unknown>).matchedText
        : undefined
    const candidates = [typeof matchedText === 'string' ? matchedText : undefined, finding.symbol]
    const lineOffset = line.lineNumber - findingStartLine
    const matchedLine = candidates
      .filter((candidate): candidate is string => Boolean(candidate?.trim()))
      .map((candidate) => candidate.split(/\r?\n/)[lineOffset]?.trim())
      .find((candidate) => candidate && line.text.includes(candidate))
    if (!matchedLine) return undefined
    startColumn = line.text.indexOf(matchedLine) + 1
    requestedEndColumn = startColumn + matchedLine.length
  }

  return {
    endColumn: Math.max(startColumn + 1, Math.min(requestedEndColumn, line.text.length + 1)),
    endLineNumber: editorLineNumber,
    startColumn,
    startLineNumber: editorLineNumber
  }
}

export default function ReportSourceContextEditor({
  context,
  fileKey,
  reportId,
  revealFindingKey,
  selectedFinding
}: {
  context: ProjectEvaluationReportFileContext
  fileKey: string
  reportId: string
  revealFindingKey: number
  selectedFinding?: ProjectEvaluationReportCodeFinding
}) {
  const queryClient = useQueryClient()
  const [loadedLines, setLoadedLines] = useState<ProjectEvaluationReportFileContextLine[]>([])
  const pendingRanges = useRef(new Set<string>())
  const [loadingRanges, setLoadingRanges] = useState<ReadonlySet<string>>(() => new Set())
  const [rangeErrors, setRangeErrors] = useState<Record<string, boolean>>({})
  const { gaps, lines } = useMemo(
    () => buildSourceContextPresentation(context.blocks, loadedLines),
    [context.blocks, loadedLines]
  )
  const highlightedLineNumbers = useMemo(
    () =>
      selectedFinding
        ? lines.flatMap((line, index) =>
            (selectedFinding.lineStart ?? -1) <= line.lineNumber &&
            (selectedFinding.lineEnd ?? selectedFinding.lineStart ?? -1) >= line.lineNumber
              ? [index + 1]
              : []
          )
        : lines.flatMap((line, index) => (line.highlights.length ? [index + 1] : [])),
    [lines, selectedFinding]
  )
  const highlightedRanges = useMemo<MonacoEditorHighlightRange[]>(() => {
    if (!selectedFinding) return []
    return lines.flatMap((line, index) => {
      if (
        line.lineNumber < (selectedFinding.lineStart ?? -1) ||
        line.lineNumber > (selectedFinding.lineEnd ?? selectedFinding.lineStart ?? -1)
      ) {
        return []
      }
      const range = sourceHighlightRange(line, index + 1, selectedFinding)
      return range ? [range] : []
    })
  }, [lines, selectedFinding])

  const loadRange = useCallback(
    async (gap: SourceContextGap) => {
      const key = gap.id
      if (pendingRanges.current.has(key)) return
      pendingRanges.current.add(key)
      setLoadingRanges(new Set(pendingRanges.current))
      setRangeErrors((current) => ({ ...current, [key]: false }))
      try {
        const rangeParams = { fromLine: gap.startLine, lines: Math.min(gap.lineCount, 2000) }
        const range = await queryClient.fetchQuery({
          queryKey: projectQueryKeys.evaluationReportFileContext(reportId, fileKey, rangeParams),
          queryFn: () => getProjectEvaluationReportFileContext(reportId, fileKey, rangeParams)
        })
        const nextLines = range.blocks.flatMap((block) =>
          block.kind === 'CODE' ? block.lines : []
        )
        if (!nextLines.length) throw new Error('SOURCE_CONTEXT_RANGE_EMPTY')
        setLoadedLines((current) => [...current, ...nextLines])
      } catch {
        setRangeErrors((current) => ({ ...current, [key]: true }))
      } finally {
        pendingRanges.current.delete(key)
        setLoadingRanges(new Set(pendingRanges.current))
      }
    },
    [fileKey, queryClient, reportId]
  )
  const sourceGaps = useMemo<MonacoEditorSourceGap[]>(
    () =>
      gaps.map((gap) => ({
        ...gap,
        error: rangeErrors[gap.id],
        loading: loadingRanges.has(gap.id),
        onLoad: () => void loadRange(gap)
      })),
    [gaps, loadRange, loadingRanges, rangeErrors]
  )

  return (
    <div className={styles.sourceContextEditor}>
      <MonacoEditor
        ariaLabel={`${context.relativePath} 联合源码上下文`}
        className={styles.sourceMonaco}
        height="auto"
        highlightedLineNumbers={highlightedLineNumbers}
        highlightedRanges={highlightedRanges}
        language={sourceLanguage(context.relativePath)}
        lineNumbers={lines.map((line) => line.lineNumber)}
        readOnly
        revealLineKey={revealFindingKey}
        revealLineNumber={selectedFinding ? highlightedLineNumbers[0] : 1}
        sourceGaps={sourceGaps}
        totalLines={context.totalLines ?? undefined}
        value={lines.map((line) => line.text).join('\n')}
        wordWrap="off"
      />
    </div>
  )
}
