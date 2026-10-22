import type {
  ProjectOptimizationCycle,
  ProjectOptimizationCycleStatus,
  ProjectOptimizationStageRunSummary
} from '@/types/project'

const statusText: Record<string, string> = {
  ACTIVE: '当前轮次',
  ARCHIVED: '已归档',
  SUPERSEDED: '已替换',
  PENDING: '等待中',
  QUEUED: '排队中',
  RUNNING: '进行中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
  TIMEOUT: '超时',
  CONSISTENT: '结果一致',
  INCONSISTENT: '存在差异',
  EQUIVALENT: '结果一致',
  DIFFERENT_ACCEPTABLE: '差异可接受',
  DIFFERENT_BLOCKING: '差异需处理',
  INCONCLUSIVE: '暂无法判断',
  UNAVAILABLE: '暂不可比较'
}

export function getOptimizationStatusText(status?: string | null) {
  return status ? (statusText[status] ?? status) : '缺失数据'
}

export function getRevisionLabel(revision?: {
  gitBranch: string | null
  gitCommit: string | null
  versionLabel: string | null
}) {
  return revision?.versionLabel ?? revision?.gitCommit ?? revision?.gitBranch ?? '未标记版本'
}

export function getStageRunDescription(summary: ProjectOptimizationStageRunSummary) {
  if (!summary.total) return '尚未执行'
  return `${summary.total} 次执行${summary.latestStatus ? `，最近${getOptimizationStatusText(summary.latestStatus)}` : ''}`
}

export interface OptimizationNextAction {
  description: string
  label: string
  stageId: 'build' | 'test' | 'archive'
  title: string
}

export function getOptimizationNextAction(cycle: ProjectOptimizationCycle): OptimizationNextAction {
  const buildStatus = cycle.summary.build.latestStatus
  if (buildStatus !== 'SUCCEEDED') {
    return {
      description:
        buildStatus === null
          ? '当前源码尚未完成 RISC-V 构建验证。'
          : `RISC-V 构建当前为${getOptimizationStatusText(buildStatus)}，请处理后重新构建。`,
      label: '前往构建验证',
      stageId: 'build',
      title: buildStatus === null ? '等待构建验证' : '构建验证未通过'
    }
  }

  const testStatus = cycle.summary.test.latestStatus
  if (testStatus !== 'SUCCEEDED') {
    return {
      description:
        testStatus === null
          ? 'RISC-V 构建已通过，尚未完成自动化测试。'
          : `自动化测试当前为${getOptimizationStatusText(testStatus)}，请处理后重新测试。`,
      label: '前往自动化测试',
      stageId: 'test',
      title: testStatus === null ? '等待自动化测试' : '自动化测试未通过'
    }
  }

  const comparison = cycle.summary.testComparison
  const comparisonStatus = comparison?.overallStatus ?? comparison?.status ?? null
  if (comparisonStatus !== 'CONSISTENT' && comparisonStatus !== 'EQUIVALENT') {
    return {
      description: comparison
        ? (comparison.recommendation ??
          comparison.summary ??
          '自动化测试已完成，但双端结果尚未达成一致。')
        : '缺失 x86 与 RISC-V 测试结果对比数据，暂时无法判断本轮是否收敛。',
      label: '查看自动化测试',
      stageId: 'test',
      title: comparison ? '测试结果尚未一致' : '缺失测试结果对比数据'
    }
  }

  return {
    description: '当前源码已通过 RISC-V 构建验证、自动化测试和双端结果对比，可以进入归档。',
    label: '进入归档',
    stageId: 'archive',
    title: '本轮验证通过'
  }
}

export const optimizationCycleStatusOptions: Array<{
  label: string
  value: ProjectOptimizationCycleStatus
}> = [
  { label: '当前轮次', value: 'ACTIVE' },
  { label: '已替换', value: 'SUPERSEDED' },
  { label: '已归档', value: 'ARCHIVED' }
]
