import { Tag, Tooltip } from 'antd'

import type { ProjectDependencyAnalysis } from '@/types/project/dependency-analysis'
import type { ProjectTaskStatus } from '@/types/project/task'
import { formatDateTime, getTaskStatusPresentation } from '@/utils/display'

import { displayValue } from '../../components/DependencyResultDetail/presentation'

import styles from '../index.module.scss'

export function taskStatusTag(status: ProjectTaskStatus) {
  const { color, label } = getTaskStatusPresentation(status, { labels: { SUCCEEDED: '完成' } })
  return <Tag color={color}>{label}</Tag>
}

export function riskTagLabel(risk: string) {
  return (
    {
      CRITICAL: '严重',
      HIGH: '高',
      MEDIUM: '中',
      LOW: '低',
      INFO: '提示',
      COMMENT: '备注'
    }[risk] ?? risk
  )
}

export function targetMatchStatusLabel(status: string) {
  return (
    {
      TARGET_INSTALLED: '目标已安装',
      PROVIDES_MATCH: '提供能力匹配',
      SAME_MAJOR: '主版本兼容',
      TARGET_NEWER: '目标版本更高',
      REPO_AVAILABLE: '仓库可用',
      TARGET_OLDER: '目标版本较低',
      TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED: '目标包可用，源码未归属',
      SOURCE_BUILD_REQUIRED: '需从源码构建',
      MANUAL_CONFIRM_REQUIRED: '需人工确认',
      NO_TARGET_VERSION_FOUND: '未找到目标版本',
      VERSION_MISMATCH: '版本不匹配',
      MISSING: '目标缺失'
    }[status] ?? status
  )
}

export function targetMatchSummaryTone(status: string) {
  if (['TARGET_INSTALLED', 'PROVIDES_MATCH', 'SAME_MAJOR', 'TARGET_NEWER'].includes(status)) {
    return styles.riskLow
  }
  if (status === 'REPO_AVAILABLE') return styles.riskInfo
  if (
    ['TARGET_OLDER', 'TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED', 'SOURCE_BUILD_REQUIRED'].includes(
      status
    )
  ) {
    return styles.riskMedium
  }
  if (['NO_TARGET_VERSION_FOUND', 'VERSION_MISMATCH', 'MISSING'].includes(status)) {
    return styles.riskHigh
  }
  return styles.riskMuted
}

export function summaryCount(summary: Record<string, unknown>, key: string) {
  const value = summary[key]
  return typeof value === 'number' ? value : 0
}

export function dependencyFailureDescription(analysis: ProjectDependencyAnalysis) {
  for (const key of ['error', 'failureMessage', 'message']) {
    const value = analysis.summary[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return '依赖分析未成功完成，请查看历史记录或重新执行。'
}

export function dependencyFailureTitle(status: ProjectTaskStatus) {
  if (status === 'CANCELLED') return '最近一次依赖分析已取消'
  if (status === 'TIMEOUT') return '最近一次依赖分析已超时'
  return '最近一次依赖分析失败'
}

export function dependencyExecutionTime(analysis: ProjectDependencyAnalysis) {
  if (analysis.status === 'RUNNING') {
    return <span>开始时间：{formatDateTime(analysis.startedAt ?? analysis.createdAt)}</span>
  }
  if (analysis.status === 'PENDING' || analysis.status === 'QUEUED') {
    return <span>创建时间：{formatDateTime(analysis.createdAt)}</span>
  }
  return <span>完成时间：{formatDateTime(analysis.finishedAt)}</span>
}

export function summaryGroupEntries(summary: Record<string, unknown>, key: string) {
  const group = summary[key]
  if (!group || typeof group !== 'object' || Array.isArray(group)) return []
  return Object.entries(group).filter(
    (entry): entry is [string, number] => typeof entry[1] === 'number'
  )
}

export function tooltipTextCell(value: string | null | undefined) {
  const content = displayValue(value)
  return (
    <Tooltip title={content}>
      <span className={styles.ellipsisText}>{content}</span>
    </Tooltip>
  )
}

export function artifactFileExtension(contentType: string) {
  if (contentType.includes('html')) return 'html'
  if (contentType.includes('json')) return 'json'
  return 'txt'
}

export function isCurrentAnalysisContext(analysis: ProjectDependencyAnalysis) {
  return analysis.currentRuntimeEnvironment !== false && analysis.currentSourceRevision !== false
}
