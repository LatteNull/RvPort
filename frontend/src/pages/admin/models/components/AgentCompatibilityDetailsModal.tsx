import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons'

import BaseModal from '@/components/BaseModal'

import type { PreparedCompatibilityResult } from './AgentCompatibilitySummary'

import styles from '../index.module.scss'

function renderCapability(label: string, compatible: boolean | null) {
  const passed = compatible === true
  return (
    <div className={styles.compatibilityCapability}>
      <span>{label}</span>
      <span className={passed ? styles.compatibilitySuccess : styles.compatibilityError}>
        {passed ? <CheckCircleFilled /> : <CloseCircleFilled />}
        {passed ? '通过' : '未通过'}
      </span>
    </div>
  )
}

export default function AgentCompatibilityDetailsModal({
  items,
  onCancel
}: {
  items: PreparedCompatibilityResult[]
  onCancel: () => void
}) {
  return (
    <BaseModal
      destroyOnHidden
      footer={null}
      title="Agent 兼容性详情"
      visible
      width={640}
      onCancel={onCancel}
    >
      <div className={styles.compatibilityDetails}>
        {items.map(({ agent, result }) => {
          const hasUnavailableCapability =
            result.basicAvailable !== true || result.agentCompatible !== true

          return (
            <div className={styles.compatibilityDetail} key={result.agentRuntimeId}>
              <div className={styles.compatibilityDetailContent}>
                <div className={styles.compatibilityDetailIdentity}>
                  <div className={styles.compatibilityDetailTitle}>{agent.name}</div>
                  <span className={styles.compatibilityDetailMeta}>{agent.type}</span>
                </div>
                <div className={styles.compatibilityCapabilityGrid}>
                  {renderCapability('基础响应', result.basicAvailable)}
                  {renderCapability('Agent 兼容性', result.agentCompatible)}
                </div>
                {hasUnavailableCapability ? (
                  <div className={`${styles.compatibilityIssue} ${styles.compatibilityError}`}>
                    <span>测试说明</span>
                    <p>{result.message || '暂无测试说明'}</p>
                  </div>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </BaseModal>
  )
}
