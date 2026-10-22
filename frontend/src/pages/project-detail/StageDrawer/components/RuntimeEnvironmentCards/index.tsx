import { CloudServerOutlined } from '@ant-design/icons'
import { Flex, Tag } from 'antd'

import type { ProjectRuntimeEnvironments } from '@/types/project'

import styles from './index.module.scss'

interface RuntimeEnvironmentCardsProps {
  environments?: ProjectRuntimeEnvironments
  showConnectionStatus?: boolean
}

export default function RuntimeEnvironmentCards({
  environments,
  showConnectionStatus = true
}: RuntimeEnvironmentCardsProps) {
  const items = [
    { label: 'x86 源环境', tone: 'source', value: environments?.sourceEnvironment },
    { label: 'RISC-V 目标环境', tone: 'target', value: environments?.targetEnvironment }
  ]

  return (
    <div className={styles.cards}>
      {items.map(({ label, tone, value }) => (
        <section
          key={label}
          className={`${styles.card} ${tone === 'source' ? styles.source : styles.target}`}
        >
          <Flex align="center" className={styles.cardHeader} gap={8}>
            <CloudServerOutlined />
            <strong>{label}</strong>
          </Flex>
          <div className={styles.identity} data-show-connection-status={showConnectionStatus}>
            <div>
              <span>环境名称</span>
              <strong>{value?.name ?? '待配置'}</strong>
            </div>
            <div>
              <span>架构</span>
              <strong>{value?.architecture ?? '-'}</strong>
            </div>
            {showConnectionStatus ? (
              <div>
                <span>环境状态</span>
                <Tag
                  className={styles.statusTag}
                  color={
                    !value?.enabled
                      ? 'default'
                      : value.connectionStatus === 'SUCCESS'
                        ? 'success'
                        : value.connectionStatus === 'FAILED'
                          ? 'error'
                          : 'default'
                  }
                >
                  {!value?.enabled
                    ? '已禁用'
                    : value.connectionStatus === 'SUCCESS'
                      ? '连接成功'
                      : value.connectionStatus === 'FAILED'
                        ? '连接失败'
                        : '未检查'}
                </Tag>
              </div>
            ) : null}
          </div>
        </section>
      ))}
    </div>
  )
}
