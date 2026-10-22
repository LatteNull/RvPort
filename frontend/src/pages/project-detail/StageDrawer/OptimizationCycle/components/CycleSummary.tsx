import { Tooltip } from 'antd'
import type { ReactNode } from 'react'

import type { ProjectOptimizationCycle } from '@/types/project'
import { formatDateTime } from '@/utils/display'

import {
  getOptimizationNextAction,
  getRevisionLabel,
  getStageRunDescription
} from '../presentation'
import { OptimizationStatusTag } from './OptimizationStatusTag'

import styles from '../index.module.scss'

interface CycleSummaryProps {
  actions?: ReactNode
  cycle: ProjectOptimizationCycle
}

function countByStatus(values: Record<string, number>, status: string) {
  return values[status] ?? values[status.toLowerCase()] ?? 0
}

function getConclusionTone(cycle: ProjectOptimizationCycle) {
  const statuses = [
    cycle.summary.recheck?.status,
    cycle.summary.build.latestStatus,
    cycle.summary.test.latestStatus,
    cycle.summary.testComparison?.status
  ]
  if (statuses.some((status) => ['FAILED', 'CANCELLED', 'TIMEOUT'].includes(status ?? '')))
    return 'error'
  return getOptimizationNextAction(cycle).stageId === 'archive' ? 'success' : 'warning'
}

export function CycleSummary({ actions, cycle }: CycleSummaryProps) {
  const nextAction = getOptimizationNextAction(cycle)
  const { migrationInputs, recheck, report, build, test, testComparison } = cycle.summary
  const comparisonStatus = testComparison?.overallStatus ?? testComparison?.status ?? null
  const highRiskCount =
    report?.highRiskCount ??
    (recheck
      ? countByStatus(recheck.bySeverity, 'CRITICAL') + countByStatus(recheck.bySeverity, 'HIGH')
      : null)
  const metrics = [
    {
      label: '已纳入处理',
      value: countByStatus(migrationInputs.byStatus, 'CONFIRMED')
    },
    { label: '待确认', value: countByStatus(migrationInputs.byStatus, 'CANDIDATE') },
    { label: '已排除', value: countByStatus(migrationInputs.byStatus, 'EXCLUDED') },
    { label: '复检差异', value: recheck?.diffTotal ?? '缺失数据' }
  ]
  const checkpoints = [
    {
      description: recheck ? `发现 ${recheck.diffTotal} 处检测结果变化` : '缺失问题复检数据',
      label: '问题复检',
      status: recheck?.status
    },
    {
      description: getStageRunDescription(build),
      label: 'RISC-V 构建',
      status: build.latestStatus
    },
    {
      description: getStageRunDescription(test),
      label: '自动化测试',
      status: test.latestStatus
    },
    {
      description: testComparison
        ? (testComparison.summary ?? '缺失测试结果对比摘要')
        : '缺失测试结果对比数据',
      label: '结果对比',
      status: comparisonStatus
    }
  ]
  const pendingItems = [
    highRiskCount && highRiskCount > 0
      ? {
          description: report?.workloadSummary ?? '建议先处理高风险项再继续验证。',
          label: `仍有 ${highRiskCount} 项高风险`
        }
      : null,
    nextAction.stageId !== 'archive'
      ? { description: nextAction.description, label: nextAction.title }
      : null,
    testComparison?.recommendation &&
    comparisonStatus !== 'CONSISTENT' &&
    comparisonStatus !== 'EQUIVALENT'
      ? { description: testComparison.recommendation, label: '测试对比建议' }
      : null
  ]
    .filter((item): item is { description: string; label: string } => Boolean(item))
    .filter(
      (item, index, items) =>
        items.findIndex((candidate) => candidate.description === item.description) === index
    )

  return (
    <div className={styles.cycleSummary}>
      <section className={styles.conclusion} data-tone={getConclusionTone(cycle)}>
        <div className={styles.conclusionMain}>
          <span className={styles.eyebrow}>
            第 {cycle.cycleNumber} 轮优化 · {getRevisionLabel(cycle.sourceRevision)}
          </span>
          <strong>{nextAction.title}</strong>
          <p>{nextAction.description}</p>
        </div>
        <div className={styles.conclusionAside}>
          {actions}
          <div className={styles.cycleTimes}>
            <span>开始时间</span>
            <time>{formatDateTime(cycle.startedAt)}</time>
          </div>
        </div>
      </section>

      <section className={styles.sectionBlock}>
        <div className={styles.sectionHeading}>
          <h3>验证路径</h3>
          <p>从源码变化开始，依次确认构建、测试和双端结果。</p>
        </div>
        <div className={styles.checkpointRail}>
          {checkpoints.map((checkpoint, index) => (
            <article className={styles.checkpoint} key={checkpoint.label}>
              <div className={styles.checkpointHeading}>
                <span className={styles.checkpointIndex}>{index + 1}</span>
                <OptimizationStatusTag status={checkpoint.status} />
              </div>
              <div className={styles.checkpointContent}>
                <strong>{checkpoint.label}</strong>
                <Tooltip placement="topLeft" title={checkpoint.description}>
                  <span>{checkpoint.description}</span>
                </Tooltip>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className={styles.detailGrid}>
        <section className={styles.convergenceBlock}>
          <div className={styles.sectionHeading}>
            <h3>本轮问题范围</h3>
            <p>只统计进入当前优化轮次的问题处理状态。</p>
          </div>
          <dl className={styles.metricList}>
            {metrics.map((metric) => (
              <div className={styles.metric} key={metric.label}>
                <dt>{metric.label}</dt>
                <dd>{metric.value}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.riskSummary}>
            {highRiskCount === null
              ? '缺失风险收敛数据'
              : highRiskCount > 0
                ? `当前仍有 ${highRiskCount} 项高风险需要关注`
                : '当前未发现高风险遗留项'}
          </p>
        </section>

        <section className={styles.pendingBlock}>
          <div className={styles.sectionHeading}>
            <h3>待处理事项</h3>
            <p>只保留影响本轮继续或归档的事项。</p>
          </div>
          {pendingItems.length ? (
            <div className={styles.pendingList}>
              {pendingItems.map((item) => (
                <article className={styles.pendingItem} key={item.label}>
                  <span className={styles.pendingMarker} />
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.description}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className={styles.readyState}>当前没有阻塞归档的事项。</div>
          )}
        </section>
      </div>
    </div>
  )
}
