import { RobotOutlined } from '@ant-design/icons'
import { Button, Popconfirm, Spin, Tag } from 'antd'

import type {
  KnowledgeBaseAiExtensionReadiness,
  KnowledgeBaseAiExtensionRun,
  KnowledgeBaseAiExtensionStatus
} from '@/types/project/knowledge-base'

import styles from '../index.module.scss'

const ACTIVE_STATUSES = new Set<KnowledgeBaseAiExtensionStatus>(['PENDING', 'QUEUED', 'RUNNING'])

const statusConfig: Record<KnowledgeBaseAiExtensionStatus, { color?: string; label: string }> = {
  PENDING: { color: 'processing', label: '等待生成' },
  QUEUED: { color: 'processing', label: '排队中' },
  RUNNING: { color: 'processing', label: '生成中' },
  SUCCEEDED: { color: 'success', label: '已生成' },
  PARTIAL_SUCCESS: { color: 'warning', label: '部分完成' },
  FAILED: { color: 'error', label: '生成失败' },
  CANCELLED: { label: '已取消' },
  TIMEOUT: { color: 'error', label: '已超时' }
}

const readinessReason: Record<string, string> = {
  KB_SCAN_NOT_SUCCEEDED: '知识库扫描尚未成功完成',
  MODEL_NOT_CONFIGURED: '尚未配置可用的知识库 AI 扩展模型',
  NO_FINDINGS: '当前扫描没有可生成建议的 Finding'
}

function resultCount(run?: KnowledgeBaseAiExtensionRun) {
  const value = run?.summary.validResultCount
  return typeof value === 'number' ? value : null
}

export interface AiSuggestionStatusProps {
  creating: boolean
  error: boolean
  loading: boolean
  readiness?: KnowledgeBaseAiExtensionReadiness
  run?: KnowledgeBaseAiExtensionRun
  onGenerate: () => void
  onRetry: () => void
}

export function AiSuggestionStatus({
  creating,
  error,
  loading,
  readiness,
  run,
  onGenerate,
  onRetry
}: AiSuggestionStatusProps) {
  const active = creating || Boolean(run && ACTIVE_STATUSES.has(run.status))
  const count = resultCount(run)
  const canGenerate = readiness?.ready === true && !active
  const disabledReason = readiness?.reason
    ? (readinessReason[readiness.reason] ?? '当前暂不能生成 AI 建议')
    : null

  let description = '基于扫描证据补充修改方式和验证建议。'
  if (active) description = 'AI 正在分析本次扫描的 Finding，期间仍可继续查看静态结果。'
  else if (run?.status === 'SUCCEEDED')
    description =
      count === null ? '本次 AI 建议已经生成。' : `已为 ${count} 条 Finding 生成补充建议。`
  else if (run?.status === 'PARTIAL_SUCCESS')
    description =
      count === null
        ? '部分 Finding 已生成 AI 建议。'
        : `已为 ${count} 条 Finding 生成建议，其余结果需要复核。`
  else if (run?.status === 'FAILED') description = '上次生成失败，可以重新尝试。'
  else if (run?.status === 'CANCELLED') description = '上次生成已取消，可以重新尝试。'
  else if (run?.status === 'TIMEOUT') description = '上次生成超时，可以重新尝试。'
  else if (disabledReason) description = disabledReason

  return (
    <div aria-label="AI 补充建议" className={styles.aiSuggestionStatus} role="group">
      <div className={styles.aiSuggestionIdentity}>
        <span className={styles.aiSuggestionIcon} aria-hidden="true">
          <RobotOutlined />
        </span>
        <strong>AI 补充建议</strong>
        {run ? (
          <Tag color={statusConfig[run.status].color}>{statusConfig[run.status].label}</Tag>
        ) : null}
        <span className={styles.aiSuggestionSummary}>{error ? '状态加载失败' : description}</span>
      </div>
      <div className={styles.aiSuggestionAction}>
        {loading ? <Spin size="small" aria-label="正在读取 AI 建议状态" /> : null}
        {error ? (
          <Button size="small" type="link" onClick={onRetry}>
            重新读取
          </Button>
        ) : (
          <Popconfirm
            cancelText="取消"
            disabled={!canGenerate}
            description="AI 将读取本次扫描的 Finding 和相关代码上下文。"
            okText="开始生成"
            title={run ? '重新生成 AI 建议？' : '生成 AI 建议？'}
            onConfirm={onGenerate}
          >
            <Button disabled={!canGenerate} loading={creating} size="small" type="link">
              {active ? '生成中' : run ? '重新生成' : '生成 AI 建议'}
            </Button>
          </Popconfirm>
        )}
      </div>
    </div>
  )
}
