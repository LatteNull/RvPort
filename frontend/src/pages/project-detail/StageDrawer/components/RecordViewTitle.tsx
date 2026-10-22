import { LeftOutlined } from '@ant-design/icons'
import { Button, Flex, Tooltip } from 'antd'

import styles from '../index.module.scss'

export default function RecordViewTitle({
  backLabel,
  disabled,
  title,
  onBack
}: {
  backLabel: string
  disabled?: boolean
  title: string
  onBack: () => void
}) {
  return (
    <Flex align="center" className={styles.drawerTitle} gap={8}>
      <Tooltip title={backLabel}>
        <Button
          aria-label={backLabel}
          className={styles.drawerBackButton}
          disabled={disabled}
          icon={<LeftOutlined />}
          shape="circle"
          type="text"
          onClick={onBack}
        />
      </Tooltip>
      <span className={styles.drawerTitleText}>{title}</span>
    </Flex>
  )
}
