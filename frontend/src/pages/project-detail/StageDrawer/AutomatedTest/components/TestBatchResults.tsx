import { Fragment } from 'react'
import { Button, Flex, Popconfirm, Tag } from 'antd'

import type { ProjectAutomatedTest, ProjectTestComparison } from '@/types/project'

import CurrentExecutionResult, {
  CurrentExecutionResultGrid
} from '../../components/CurrentExecutionResult'
import {
  getComparisonPresentation,
  getComparisonSummary,
  renderComparisonStatusTag,
  renderTestRiskTag,
  renderTestStatusTag
} from '../presentation'
import { isTerminalTestStatus } from '../useAutomatedTestDrawer'

import styles from '../index.module.scss'

export default function TestBatchResults({
  tests,
  comparison,
  readOnly,
  onShowHistory,
  onShowTestLog,
  onShowComparisonLog,
  onCancel
}: {
  tests: ProjectAutomatedTest[]
  comparison?: ProjectTestComparison
  readOnly: boolean
  onShowHistory?: () => void
  onShowTestLog: (test: ProjectAutomatedTest) => void
  onShowComparisonLog: (comparison: ProjectTestComparison) => void
  onCancel: (id: string) => void
}) {
  const comparisonPresentation = getComparisonPresentation(comparison)
  return (
    <Fragment>
      <section className={`${styles.section} ${styles.compactSection}`}>
        <Flex align="center" className={styles.sectionHeader} justify="space-between">
          <h3>{readOnly ? '批次测试结果' : '当前测试结果'}</h3>
          {readOnly ? (
            <Tag>只读记录</Tag>
          ) : (
            <Button type="link" onClick={onShowHistory}>
              查看历史记录
            </Button>
          )}
        </Flex>
        <CurrentExecutionResultGrid>
          {(['SOURCE', 'TARGET'] as const).map((role) => {
            const item = tests.find((test) => test.testBatchRole === role)
            return (
              <CurrentExecutionResult
                actions={
                  item ? (
                    <Fragment>
                      <Button type="link" size="small" onClick={() => onShowTestLog(item)}>
                        日志
                      </Button>
                      {!readOnly && !isTerminalTestStatus(item.status) ? (
                        <Popconfirm title="确认取消测试？" onConfirm={() => onCancel(item.id)}>
                          <Button type="link" size="small">
                            取消
                          </Button>
                        </Popconfirm>
                      ) : null}
                    </Fragment>
                  ) : undefined
                }
                key={role}
                status={renderTestStatusTag(item?.status)}
                subtitle={item?.environmentName ?? '尚未创建'}
                title={role === 'SOURCE' ? 'x86' : 'RISC-V'}
              >
                <div className={styles.testCounts}>
                  <span>
                    通过 <strong>{item?.passedCount ?? '--'}</strong>
                  </span>
                  <span>
                    失败 <strong>{item?.failedCount ?? '--'}</strong>
                  </span>
                  <span>
                    跳过 <strong>{item?.skippedCount ?? '--'}</strong>
                  </span>
                </div>
              </CurrentExecutionResult>
            )
          })}
        </CurrentExecutionResultGrid>
      </section>
      <section className={`${styles.section} ${styles.compactSection}`}>
        <h3>测试结果对比</h3>
        <div className={styles.comparison} data-tone={comparisonPresentation.tone}>
          <div className={styles.comparisonHeader}>
            <span className={styles.comparisonIcon}>{comparisonPresentation.icon}</span>
            <strong>{comparisonPresentation.headline}</strong>
            <div className={styles.comparisonTags}>
              {comparison
                ? renderComparisonStatusTag(comparison.overallStatus ?? comparison.status)
                : null}
              {renderTestRiskTag(comparison?.riskLevel)}
            </div>
          </div>
          {comparison ? (
            <Fragment>
              <p className={styles.comparisonSummary}>{getComparisonSummary(comparison)}</p>
              {comparison.recommendation ? (
                <div className={styles.recommendation}>
                  <span>处理建议</span>
                  <p>{comparison.recommendation}</p>
                </div>
              ) : null}
              <div className={styles.comparisonActions}>
                <Button size="small" type="link" onClick={() => onShowComparisonLog(comparison)}>
                  查看对比日志
                </Button>
              </div>
            </Fragment>
          ) : (
            <p className={styles.comparisonSummary}>两侧测试完成后，系统将自动生成对比结论。</p>
          )}
        </div>
      </section>
    </Fragment>
  )
}
