import { DownloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Button, Flex, Popconfirm, Tag, Tooltip } from 'antd'

import type { ProjectDependencyAnalysis } from '@/types/project/dependency-analysis'
import { formatDateTime } from '@/utils/display'

import CountDistribution from '../../components/CountDistribution'
import ResultOverview from '../../components/ResultOverview'
import type { useAnalysisArtifacts } from '../useAnalysisArtifacts'
import {
  summaryCount,
  summaryGroupEntries,
  targetMatchStatusLabel,
  targetMatchSummaryTone,
  taskStatusTag
} from './presentation'

import styles from '../index.module.scss'
export default function AnalysisOverview({
  analysis,
  artifacts,
  isReadOnly,
  isCreating,
  onAutoFix,
  onViewHistory,
  onRerun
}: {
  analysis: ProjectDependencyAnalysis
  artifacts: ReturnType<typeof useAnalysisArtifacts>
  isReadOnly: boolean
  isCreating?: boolean
  onAutoFix: () => void
  onViewHistory?: () => void
  onRerun?: () => void
}) {
  const { artifactsQuery, downloadArtifactMutation } = artifacts
  const canModify = !isReadOnly
  const total = summaryCount(analysis.summary, 'total')
  const riskDistribution = summaryGroupEntries(analysis.summary, 'byRisk')
  const targetMatchDistribution = summaryGroupEntries(analysis.summary, 'byTargetMatchStatus')
  const riskCounts = [
    { key: 'CRITICAL', label: '严重', tone: styles.riskCritical },
    { key: 'HIGH', label: '高', tone: styles.riskHigh },
    { key: 'MEDIUM', label: '中', tone: styles.riskMedium },
    { key: 'LOW', label: '低', tone: styles.riskLow },
    { key: 'INFO', label: '提示', tone: styles.riskInfo },
    { key: 'COMMENT', label: '备注', tone: styles.riskMuted }
  ].map((item) => ({
    ...item,
    value: riskDistribution.find(([risk]) => risk === item.key)?.[1] ?? 0
  }))
  const targetMatchCounts = targetMatchDistribution.map(([status, value]) => ({
    key: status,
    label: targetMatchStatusLabel(status),
    tone: targetMatchSummaryTone(status),
    value
  }))
  return (
    <section className={styles.section}>
      <div className={styles.sectionTitleRow}>
        <h3>分析概览</h3>
        <Flex align="center" gap={8}>
          {isReadOnly ? <Tag>只读记录</Tag> : null}
          {canModify ? (
            <Button icon={<SafetyCertificateOutlined />} type="primary" onClick={onAutoFix}>
              自动修复依赖
            </Button>
          ) : null}
          {onRerun ? (
            <Popconfirm
              cancelText="取消"
              description="重新分析会生成一条新的依赖分析记录。"
              okText="继续"
              title="确认重新分析？"
              onConfirm={onRerun}
            >
              <Button loading={isCreating}>重新分析</Button>
            </Popconfirm>
          ) : null}
          {onViewHistory ? (
            <Button type="link" onClick={onViewHistory}>
              查看历史记录
            </Button>
          ) : null}
        </Flex>
      </div>
      <ResultOverview
        status={taskStatusTag(analysis.status)}
        metadata={[
          { label: '创建时间', value: formatDateTime(analysis.createdAt) },
          { label: '完成时间', value: formatDateTime(analysis.finishedAt) }
        ]}
      >
        <div className={styles.summaryPanel}>
          <div className={styles.summaryMetrics}>
            <div className={styles.summaryMetric}>
              <span>分析依赖</span>
              <strong>{total}</strong>
            </div>
            <div className={styles.summaryDistributions}>
              <div className={styles.summaryDistribution}>
                <CountDistribution entries={riskCounts} title="风险分布" />
              </div>
              <div className={styles.summaryDistribution}>
                <CountDistribution entries={targetMatchCounts} title="目标侧匹配" />
              </div>
            </div>
          </div>
          <div className={styles.artifactDownloads}>
            <div className={styles.artifactMeta}>
              <span>分析制品</span>
              <small>
                {artifactsQuery.isLoading
                  ? '正在读取可下载制品'
                  : artifactsQuery.data?.length
                    ? `已生成 ${artifactsQuery.data.length} 份制品`
                    : '本次分析未生成可下载制品'}
              </small>
            </div>
            {artifactsQuery.data?.length ? (
              <Flex className={styles.artifactActions} gap={4} wrap>
                {artifactsQuery.data.map((artifact) => (
                  <Tooltip key={artifact.id} title={`下载 ${artifact.artifactType}`}>
                    <Button
                      aria-label={`下载 ${artifact.artifactType}`}
                      icon={<DownloadOutlined />}
                      loading={
                        downloadArtifactMutation.isPending &&
                        downloadArtifactMutation.variables?.id === artifact.id
                      }
                      size="small"
                      type="text"
                      onClick={() => downloadArtifactMutation.mutate(artifact)}
                    >
                      {artifact.artifactType}
                    </Button>
                  </Tooltip>
                ))}
              </Flex>
            ) : null}
          </div>
        </div>
      </ResultOverview>
    </section>
  )
}
