import type { ProjectStagePrerequisite } from '@/types/project'

import type { StageStatePrerequisite } from './components/StageStateNotice'

const conditions: Record<string, [string, string?, string?]> = {
  ACTIVE_SOURCE: ['当前源码', 'assets', '源码管理'],
  SOURCE_ENVIRONMENT: ['x86 源环境', 'env', '环境管理'],
  TARGET_ENVIRONMENT: ['RISC-V 目标环境', 'env', '环境管理'],
  X86_BUILD: ['x86 构建', 'x86-build', 'x86 构建'],
  BUILD_VALIDATION: ['构建验证', 'build', '构建验证'],
  KB_SCAN: ['知识库扫描', 'kb', '知识库扫描'],
  DEPENDENCY_ANALYSIS: ['依赖分析', 'rv-dependency-analysis', '依赖分析'],
  INCLUDED_FINDINGS: ['报告输入', 'kb', '问题纳入'],
  ARCHIVE_CANDIDATES: ['可归档内容', 'optimize', '优化闭环'],
  SPECIALIZED_ANALYZER: ['分析工具']
}
const statuses = {
  SATISFIED: '已满足',
  MISSING: '未满足',
  RUNNING: '进行中',
  FAILED: '失败',
  STALE: '已过期',
  UNAVAILABLE: '不可用'
}
const buildStatuses = {
  SATISFIED: '已完成',
  MISSING: '尚无成功构建',
  RUNNING: 'x86 正在构建',
  FAILED: 'x86 构建失败',
  STALE: '需针对当前版本重新构建',
  UNAVAILABLE: '构建不可用'
}

export function presentPrerequisites(
  prerequisites: (ProjectStagePrerequisite | undefined)[],
  onStageChange?: (stageId: string) => void
): StageStatePrerequisite[] {
  return prerequisites.flatMap((item) => {
    if (!item) return []
    const [label, target, action] = conditions[item.key] ?? [item.key]
    const ready = item.status === 'SATISFIED'
    return [
      {
        key: item.key,
        label,
        ready,
        value:
          ready && item.key === 'ARCHIVE_CANDIDATES'
            ? `已满足（${String(item.details.count ?? 0)} 项）`
            : item.key === 'X86_BUILD'
              ? buildStatuses[item.status]
              : statuses[item.status],
        action:
          !ready && target && onStageChange
            ? {
                label: target === 'x86-build' ? '前往 x86 构建' : `前往${action}`,
                onClick: () => onStageChange(target)
              }
            : undefined
      }
    ]
  })
}

export function isStageActive(status?: string | null) {
  return Boolean(status && ['PENDING', 'QUEUED', 'RUNNING'].includes(status))
}

export function resolveOverviewState(facts: {
  loading: boolean
  error: boolean
  hasData: boolean
  ready: boolean
  status?: string | null
  freshness?: string
  submitting?: boolean
  hasResult: boolean
}) {
  if (!facts.hasData && facts.loading) return 'loading'
  if (!facts.hasData && facts.error) return 'request-error'
  if (!facts.ready) return 'blocked'
  if (facts.submitting) return 'submitted'
  if (isStageActive(facts.status)) return 'running'
  if (facts.freshness === 'STALE' || facts.freshness === 'EMPTY' || !facts.status) return 'ready'
  if (['FAILED', 'CANCELLED', 'TIMEOUT'].includes(facts.status)) return 'failed'
  return facts.hasResult ? 'result' : 'syncing'
}
