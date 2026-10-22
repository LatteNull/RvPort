import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons'
import { Tag } from 'antd'

import type { ProjectTestComparison } from '@/types/project'
import { getTaskStatusPresentation } from '@/utils/display'

import styles from './index.module.scss'

const comparisonOutcomes: Record<
  string,
  { color?: string; headline: string; label: string; tone: string }
> = {
  EQUIVALENT: {
    color: 'success',
    headline: '双端测试结果等价',
    label: '结果等价',
    tone: 'success'
  },
  DIFFERENT_ACCEPTABLE: {
    color: 'warning',
    headline: '双端测试结果存在可接受差异',
    label: '差异可接受',
    tone: 'warning'
  },
  DIFFERENT_BLOCKING: {
    color: 'error',
    headline: '双端测试结果存在阻断性差异',
    label: '阻断性差异',
    tone: 'error'
  },
  INCONCLUSIVE: {
    color: 'warning',
    headline: '暂无法得出一致性结论',
    label: '暂无法判断',
    tone: 'neutral'
  },
  CONSISTENT: {
    color: 'success',
    headline: '双端测试结果一致',
    label: '结果一致',
    tone: 'success'
  },
  INCONSISTENT: {
    color: 'warning',
    headline: '双端测试结果存在差异',
    label: '存在差异',
    tone: 'warning'
  }
}

export function renderTestStatusTag(status?: string) {
  const { color, label } = getTaskStatusPresentation(status, { fallbackLabel: '未运行' })
  return (
    <Tag className={styles.statusTag} color={color}>
      {label}
    </Tag>
  )
}

export function renderComparisonStatusTag(status?: string) {
  const presentation: Record<string, { color?: string; label: string }> = {
    PENDING: { color: 'processing', label: '等待比较' },
    QUEUED: { color: 'processing', label: '等待比较' },
    RUNNING: { color: 'processing', label: '比较中' },
    SUCCEEDED: { color: 'success', label: '已完成' },
    FAILED: { color: 'error', label: '比较失败' },
    UNAVAILABLE: { label: '暂不可比较' }
  }
  const item = comparisonOutcomes[status ?? ''] ?? presentation[status ?? '']
  return (
    <Tag className={styles.statusTag} color={item?.color}>
      {item?.label ?? status ?? '等待比较'}
    </Tag>
  )
}

export function renderTestRiskTag(riskLevel?: string | null) {
  const presentation: Record<string, { color?: string; label: string }> = {
    CRITICAL: { color: 'error', label: '严重' },
    HIGH: { color: 'error', label: '高' },
    MEDIUM: { color: 'warning', label: '中' },
    LOW: { color: 'success', label: '低' },
    INFO: { color: 'processing', label: '提示' },
    NONE: { color: 'success', label: '无风险' }
  }
  const item = presentation[riskLevel ?? '']
  return riskLevel ? (
    <Tag className={styles.statusTag} color={item?.color}>
      {item?.label ?? riskLevel}
    </Tag>
  ) : null
}

export function getComparisonPresentation(comparison?: ProjectTestComparison) {
  if (comparison?.status === 'FAILED') {
    return { headline: '测试结果对比失败', icon: <ExclamationCircleOutlined />, tone: 'error' }
  }
  const status = comparison?.overallStatus ?? comparison?.status
  const outcome = comparisonOutcomes[status ?? '']
  if (outcome) {
    return {
      headline: outcome.headline,
      icon:
        outcome.tone === 'success' ? (
          <CheckCircleOutlined />
        ) : outcome.tone === 'neutral' ? (
          <InfoCircleOutlined />
        ) : (
          <ExclamationCircleOutlined />
        ),
      tone: outcome.tone
    }
  }
  if (status === 'RUNNING' || status === 'QUEUED' || status === 'PENDING') {
    return { headline: '正在生成对比结论', icon: <LoadingOutlined />, tone: 'processing' }
  }
  return { headline: '等待双端测试结果', icon: <InfoCircleOutlined />, tone: 'neutral' }
}

export function getComparisonSummary(comparison: ProjectTestComparison) {
  if (comparison.status === 'FAILED') return '对比任务执行失败，请刷新信息或重新运行自动化测试。'
  return comparison.summary ?? comparison.unavailableMessage ?? '比较结果等待生成。'
}
