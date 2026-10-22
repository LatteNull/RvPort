import type { ProjectKnowledgeBaseScan } from '@/types/project/knowledge-base'
import { formatFileSize } from '@/utils/display'

import { asRecord } from '../components/FindingDetail/presentation'

import styles from './index.module.scss'

export const scanArtifactLabels: Record<string, string> = {
  SCAN_LOG: '扫描日志',
  SCAN_REPORT_HTML: '扫描报告（HTML）',
  SCAN_RESULT_JSON: '扫描结果（JSON）'
}

function getNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function getOptionalNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export const backendPendingText = '后端待提供'

export { formatFileSize }

export function getKnowledgeBaseOverview(summary: ProjectKnowledgeBaseScan['summary']) {
  const resultSummary = asRecord(summary.summary)
  const findingCount = getNumber(summary.findingCount) || getNumber(resultSummary.findings)
  const blockingCount = getNumber(resultSummary.blocking)
  const issueCount = getNumber(resultSummary.issues)
  const hintCount = getNumber(resultSummary.hints)
  const incompleteCount = getNumber(resultSummary.incomplete)
  const readiness =
    typeof resultSummary.readiness === 'string' ? resultSummary.readiness : undefined

  return {
    actionableCount: blockingCount,
    blockingCount,
    files: getNumber(resultSummary.files),
    findingCount,
    hintCount,
    incompleteCount,
    inactiveOrGuardedCount: getNumber(resultSummary.inactiveOrGuarded),
    issueCount,
    portabilityGapCount: getOptionalNumber(resultSummary.portabilityGaps),
    readiness,
    status: typeof resultSummary.status === 'string' ? resultSummary.status : undefined,
    conclusion:
      findingCount === 0
        ? '当前静态范围内未发现明确的 x86 迁移阻碍。'
        : blockingCount > 0
          ? `发现 ${findingCount} 个迁移相关项，其中 ${blockingCount} 个会阻塞当前迁移路径。`
          : `发现 ${findingCount} 个迁移相关项，当前没有被标记为阻塞的问题。`,
    outputCounts: [
      {
        key: 'issues',
        label: '问题',
        value: getNumber(resultSummary.issues),
        tone: styles.outputIssue
      },
      {
        key: 'hints',
        label: '提示',
        value: getNumber(resultSummary.hints),
        tone: styles.outputHint
      },
      {
        key: 'portabilityGaps',
        label: '迁移缺口',
        value: getNumber(resultSummary.portabilityGaps),
        tone: styles.outputGap
      },
      {
        key: 'references',
        label: '参考',
        value: getNumber(resultSummary.references),
        tone: styles.outputReference
      },
      {
        key: 'inactiveOrGuarded',
        label: '受保护/未启用',
        value: getNumber(resultSummary.inactiveOrGuarded),
        tone: styles.outputInactive
      },
      {
        key: 'diagnosticCount',
        label: '诊断',
        value: getNumber(summary.diagnosticCount),
        tone: styles.outputDiagnostic
      }
    ]
  }
}
