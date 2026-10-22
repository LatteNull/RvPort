import { lazy, Suspense, useState } from 'react'

import { getProjectDependencyAnalysisResults } from '@/api/project/dependency-analysis'
import BaseTable from '@/components/BaseTable'
import type {
  ProjectDependencyAnalysis,
  ProjectDependencyAnalysisResult,
  ProjectDependencyAnalysisResultListParams
} from '@/types/project/dependency-analysis'

import { projectQueryKeys } from '../../../queryKeys'
import { useAnalysisArtifacts } from '../useAnalysisArtifacts'
import AnalysisOverview from './AnalysisOverview'
import { isCurrentAnalysisContext } from './presentation'
import { useDependencyResultColumns } from './useDependencyResultColumns'

import styles from '../index.module.scss'

const DependencyAutoFixModal = lazy(() => import('../DependencyAutoFixModal'))

type DependencyResultFilters = Pick<
  ProjectDependencyAnalysisResultListParams,
  'keyword' | 'riskLevel' | 'targetMatchStatus'
>

export default function AnalysisResults({
  analysis,
  isCreating,
  onViewHistory,
  onRerun,
  onOpenResult,
  projectId,
  readOnly = false
}: {
  analysis: ProjectDependencyAnalysis
  isCreating?: boolean
  onViewHistory?: () => void
  onRerun?: () => void
  onOpenResult: (resultId: string) => void
  projectId: string
  readOnly?: boolean
}) {
  const [autoFixOpen, setAutoFixOpen] = useState(false)
  const { artifactsQuery, downloadArtifactMutation } = useAnalysisArtifacts(analysis)
  const isReadOnly = readOnly || !isCurrentAnalysisContext(analysis)
  const canModify = !isReadOnly
  const columns = useDependencyResultColumns(analysis, projectId, canModify, onOpenResult)
  return (
    <div className={styles.content}>
      <AnalysisOverview
        analysis={analysis}
        artifacts={{ artifactsQuery, downloadArtifactMutation }}
        isReadOnly={isReadOnly}
        isCreating={isCreating}
        onAutoFix={() => setAutoFixOpen(true)}
        onRerun={onRerun}
        onViewHistory={onViewHistory}
      />
      <section className={styles.section}>
        <h3>结果列表</h3>
        <BaseTable<ProjectDependencyAnalysisResult, DependencyResultFilters>
          autoHeight
          columns={columns}
          emptyDescription="暂无依赖结果"
          pagination={{ initialPageSize: 20 }}
          queryKey={projectQueryKeys.dependencyAnalysisResults(analysis.id)}
          request={(query) =>
            getProjectDependencyAnalysisResults(analysis.id, {
              keyword: query.keyword,
              page: query.page,
              pageSize: query.pageSize,
              riskLevel: query.riskLevel,
              targetMatchStatus: query.targetMatchStatus
            })
          }
          rowKey="id"
          scroll={{ x: 1200 }}
          size="small"
          tableLayout="fixed"
          toolbar={{
            filters: {
              fields: [
                { name: 'keyword', placeholder: '搜索依赖或来源位置', type: 'search' },
                {
                  name: 'riskLevel',
                  options: [
                    { label: '高风险', value: 'HIGH' },
                    { label: '中风险', value: 'MEDIUM' },
                    { label: '低风险', value: 'LOW' }
                  ],
                  placeholder: '风险等级',
                  type: 'select'
                },
                {
                  name: 'targetMatchStatus',
                  options: [
                    { label: '目标已安装', value: 'TARGET_INSTALLED' },
                    { label: '提供能力匹配', value: 'PROVIDES_MATCH' },
                    { label: '仓库可用', value: 'REPO_AVAILABLE' },
                    { label: '版本不匹配', value: 'VERSION_MISMATCH' },
                    { label: '目标缺失', value: 'MISSING' },
                    { label: '需人工确认', value: 'MANUAL_CONFIRM_REQUIRED' }
                  ],
                  placeholder: '目标匹配',
                  type: 'select'
                }
              ]
            }
          }}
        />
      </section>
      {canModify && autoFixOpen ? (
        <Suspense fallback={null}>
          <DependencyAutoFixModal
            analysisId={analysis.id}
            open
            onClose={() => setAutoFixOpen(false)}
          />
        </Suspense>
      ) : null}
    </div>
  )
}
