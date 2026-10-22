import { Flex } from 'antd'
import type { ReactNode } from 'react'

import styles from './index.module.scss'

interface DrawerInfoItemProps {
  label: string
  value: ReactNode
}

export function DrawerInfoItem({ label, value }: DrawerInfoItemProps) {
  return (
    <Flex vertical align="flex-start" gap={2} className={styles.drawerInfoItem}>
      <span className={styles.drawerInfoLabel}>{label}</span>
      <span className={styles.drawerInfoValue}>{value}</span>
    </Flex>
  )
}
