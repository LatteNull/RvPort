import { Tag } from 'antd'

import styles from './index.module.scss'

export const knowledgeBaseSeverityLevels = [
  { key: 'critical', label: '严重', tagColor: '#a8071a', tone: styles.riskCritical },
  { key: 'high', label: '高', tagColor: 'error', tone: styles.riskHigh },
  { key: 'medium', label: '中', tagColor: 'warning', tone: styles.riskMedium },
  { key: 'low', label: '低', tagColor: 'success', tone: styles.riskLow },
  { key: 'info', label: '提示', tagColor: 'processing', tone: styles.riskInfo }
] as const

export type KnowledgeBaseSeverity = (typeof knowledgeBaseSeverityLevels)[number]['key']

const severityByKey = new Map(knowledgeBaseSeverityLevels.map((item) => [item.key, item]))

export const knowledgeBaseSeverityOptions = knowledgeBaseSeverityLevels.map(({ key, label }) => ({
  label,
  value: key
}))

export function normalizeKnowledgeBaseSeverity(
  value: string | null | undefined
): KnowledgeBaseSeverity | undefined {
  const severity = value?.toLowerCase() as KnowledgeBaseSeverity | undefined
  return severity && severityByKey.has(severity) ? severity : undefined
}

export function renderSeverityTag(value: string | null) {
  const severity = normalizeKnowledgeBaseSeverity(value)
  const definition = severity ? severityByKey.get(severity) : undefined
  return definition ? <Tag color={definition.tagColor}>{definition.label}</Tag> : (value ?? '--')
}

export function renderFindingStatusTag(value: string | null) {
  if (value === 'DETECTED') return <Tag color="processing">已发现</Tag>
  if (value === 'SUPPRESSED') return <Tag>已抑制</Tag>
  return value ?? '--'
}
