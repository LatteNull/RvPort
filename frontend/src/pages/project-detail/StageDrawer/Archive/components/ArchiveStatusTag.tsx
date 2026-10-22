import { Tag } from 'antd'

import { getArchiveStatusColor, getArchiveStatusText } from '../presentation'

import styles from '../index.module.scss'

export function ArchiveStatusTag({ status }: { status?: string | null }) {
  return (
    <Tag className={styles.statusTag} color={getArchiveStatusColor(status)}>
      {getArchiveStatusText(status)}
    </Tag>
  )
}
