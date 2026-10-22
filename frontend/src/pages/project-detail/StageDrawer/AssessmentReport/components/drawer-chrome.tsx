import { Button, Flex } from 'antd'

import type { ProjectEvaluationReport } from '@/types/project'

import styles from '../index.module.scss'

export function AssessmentReportTitle() {
  return (
    <Flex align="center" className={styles.drawerTitle} gap={12}>
      <span className={styles.drawerTitleText}>评估报告</span>
    </Flex>
  )
}
export function AssessmentReportFooter({
  report,
  onManualRepair
}: {
  report?: ProjectEvaluationReport
  onManualRepair: () => void
}) {
  if (report?.status !== 'SUCCEEDED') return null
  return (
    <Flex justify="flex-end">
      <Button type="primary" onClick={onManualRepair}>
        进入人工修复
      </Button>
    </Flex>
  )
}
