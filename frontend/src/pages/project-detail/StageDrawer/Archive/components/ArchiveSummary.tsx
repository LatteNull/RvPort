import {
  CheckCircleFilled,
  ClockCircleFilled,
  CloseCircleFilled,
  SafetyCertificateOutlined
} from '@ant-design/icons'
import { Typography } from 'antd'
import type { ReactNode } from 'react'

import type { ProjectArchive } from '@/types/project'
import { formatDateTime } from '@/utils/display'

import { formatBytes, getSourceRevisionLabel } from '../presentation'
import { ArchiveStatusTag } from './ArchiveStatusTag'

import styles from '../index.module.scss'

function getArchiveConclusion(
  archive: ProjectArchive,
  isCurrentSource: boolean,
  currentSourceLabel?: string
) {
  if (!isCurrentSource) {
    const archivedSourceLabel = archive.sourceRevision
      ? getSourceRevisionLabel(archive.sourceRevision)
      : '缺失源码版本数据'
    return {
      description: currentSourceLabel
        ? `最近归档基于 ${archivedSourceLabel}；当前激活源码 ${currentSourceLabel} 尚未生成交付归档。`
        : `最近归档基于 ${archivedSourceLabel}；当前源码尚未生成交付归档。`,
      title: '当前源码尚未归档',
      tone: 'warning'
    }
  }
  if (archive.status === 'SUCCEEDED' && archive.storedArtifactId) {
    return {
      description: `归档包已生成，包含 ${archive.items.length} 项可交付内容。`,
      title: '归档已就绪',
      tone: 'success'
    }
  }
  if (archive.status === 'SUCCEEDED') {
    return {
      description: '归档任务已完成，但缺失可下载的归档包数据。',
      title: '归档包数据缺失',
      tone: 'warning'
    }
  }
  if (['PENDING', 'QUEUED', 'RUNNING'].includes(archive.status)) {
    return {
      description: '系统正在汇集交付内容并生成不可变归档包。',
      title: '正在生成归档',
      tone: 'warning'
    }
  }
  return {
    description: '归档任务未成功生成交付包，请确认当前源码后重新创建。',
    title: '归档创建失败',
    tone: 'error'
  }
}

export function ArchiveSummary({
  actions,
  archive,
  currentSourceLabel,
  isCurrentSource = true
}: {
  actions?: ReactNode
  archive: ProjectArchive
  currentSourceLabel?: string
  isCurrentSource?: boolean
}) {
  const conclusion = getArchiveConclusion(archive, isCurrentSource, currentSourceLabel)
  const facts = [
    {
      kind: 'source',
      label: isCurrentSource ? '源码版本' : '归档源码版本',
      value: archive.sourceRevision
        ? getSourceRevisionLabel(archive.sourceRevision)
        : '缺失源码版本数据'
    },
    { kind: 'count', label: '交付内容', value: `${archive.items.length} 项` },
    {
      kind: 'size',
      label: '归档包大小',
      value: archive.sizeBytes === null ? '缺失归档包大小数据' : formatBytes(archive.sizeBytes)
    },
    { kind: 'time', label: '生成时间', value: formatDateTime(archive.updatedAt) }
  ]
  const traceability = [
    { label: 'SHA-256', value: archive.sha256 ?? '缺失完整性校验数据' },
    { label: '归档记录 ID', value: archive.id || '缺失归档记录 ID 数据' },
    {
      label: '源码记录 ID',
      value: archive.sourceRevisionId || '缺失源码记录 ID 数据'
    },
    { label: '任务 ID', value: archive.taskId || '缺失归档任务 ID 数据' }
  ]
  const statusIcon =
    conclusion.tone === 'success' ? (
      <CheckCircleFilled />
    ) : conclusion.tone === 'error' ? (
      <CloseCircleFilled />
    ) : (
      <ClockCircleFilled />
    )

  return (
    <div className={styles.archiveSummary}>
      <section className={styles.archiveOverview} data-tone={conclusion.tone}>
        <div className={styles.archiveConclusion}>
          <span className={styles.conclusionIcon}>{statusIcon}</span>
          <div className={styles.conclusionMain}>
            <span className={styles.eyebrow}>项目交付归档</span>
            <strong>{conclusion.title}</strong>
            <p>{conclusion.description}</p>
          </div>
          <div className={styles.conclusionAside}>
            <ArchiveStatusTag status={archive.status} />
            {actions}
          </div>
        </div>
        <div className={styles.deliveryFacts}>
          {facts.map((fact) => (
            <div className={styles.deliveryFact} data-kind={fact.kind} key={fact.label}>
              <span>{fact.label}</span>
              <Typography.Text
                className={styles.deliveryFactValue}
                copyable={
                  fact.kind === 'source' && !fact.value.startsWith('缺失')
                    ? { text: fact.value }
                    : false
                }
                ellipsis={fact.kind === 'source' ? { tooltip: fact.value } : false}
              >
                {fact.value}
              </Typography.Text>
            </div>
          ))}
        </div>
      </section>

      <details className={styles.traceability}>
        <summary>
          <SafetyCertificateOutlined />
          <span className={styles.traceabilityHeading}>
            <strong>校验与追溯</strong>
            <small>查看归档名称、校验值及关联记录</small>
          </span>
        </summary>
        <div className={styles.traceabilityContent}>
          <div className={styles.archiveName}>
            <span>归档名称</span>
            <strong>{archive.name || '缺失归档名称数据'}</strong>
          </div>
          <div className={styles.integrityList}>
            {traceability.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <Typography.Text
                  copyable={item.value.startsWith('缺失') ? false : { text: item.value }}
                >
                  {item.value}
                </Typography.Text>
              </div>
            ))}
            {archive.sourceRevision?.gitBranch ? (
              <div>
                <span>Git 分支</span>
                <Typography.Text copyable={{ text: archive.sourceRevision.gitBranch }}>
                  {archive.sourceRevision.gitBranch}
                </Typography.Text>
              </div>
            ) : null}
            {archive.sourceRevision?.gitCommit ? (
              <div>
                <span>Git 提交</span>
                <Typography.Text copyable={{ text: archive.sourceRevision.gitCommit }}>
                  {archive.sourceRevision.gitCommit}
                </Typography.Text>
              </div>
            ) : null}
          </div>
        </div>
      </details>
    </div>
  )
}
