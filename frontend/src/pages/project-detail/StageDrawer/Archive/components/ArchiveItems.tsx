import { DownloadOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Button, Dropdown } from 'antd'

import { getProjectArchiveItemDownloadUrl } from '@/api/project/archive'
import type { ProjectArchiveItem } from '@/types/project'

import {
  formatArchiveMetadataLabel,
  formatArchiveMetadataValue,
  getArchiveCandidateTypeLabel,
  getArchiveItemTitle,
  getArchiveNodeTypeLabel
} from '../presentation'

import styles from '../index.module.scss'

export function ArchiveItems({
  archiveId,
  items
}: {
  archiveId: string
  items: ProjectArchiveItem[]
}) {
  if (!items.length) return <div className={styles.missingState}>缺失归档交付项数据</div>

  return (
    <div className={styles.itemList}>
      {items.map((item, index) => {
        const title = getArchiveItemTitle(item)
        const nodeLabel = getArchiveNodeTypeLabel(item.nodeType)
        const formats = [...new Set([...item.artifactRefs.map((ref) => ref.format), 'JSON'])]
        const downloads: MenuProps['items'] = formats.map((format) => ({
          key: format,
          label: (
            <a
              href={getProjectArchiveItemDownloadUrl(archiveId, item.id, format)}
              rel="noreferrer"
              target="_blank"
            >
              {format} 文件
            </a>
          )
        }))

        return (
          <article key={item.id} className={styles.item}>
            <div className={styles.itemMain}>
              <span className={styles.itemIndex}>{String(index + 1).padStart(2, '0')}</span>
              <div className={styles.itemIdentity}>
                <strong>{title}</strong>
                <div className={styles.itemMeta}>
                  {title === nodeLabel ? null : <span>{nodeLabel}</span>}
                  <span>{getArchiveCandidateTypeLabel(item.candidateType)}</span>
                  <span>{formats.join(' / ')}</span>
                </div>
              </div>
              <Dropdown menu={{ items: downloads }} placement="bottomRight" trigger={['click']}>
                <Button aria-label={`下载 ${title}`} icon={<DownloadOutlined />} size="small">
                  下载
                </Button>
              </Dropdown>
            </div>
            <details className={styles.itemDetails}>
              <summary>查看归档详情</summary>
              <div className={styles.itemDetailGrid}>
                <div>
                  <span>来源阶段</span>
                  <strong>{getArchiveNodeTypeLabel(item.nodeType)}</strong>
                </div>
                <div>
                  <span>内容类型</span>
                  <strong>{getArchiveCandidateTypeLabel(item.candidateType)}</strong>
                </div>
                {Object.entries(item.metadata).map(([key, value]) => (
                  <div key={key}>
                    <span>{formatArchiveMetadataLabel(key)}</span>
                    <strong>{formatArchiveMetadataValue(key, value)}</strong>
                  </div>
                ))}
              </div>
            </details>
          </article>
        )
      })}
    </div>
  )
}
