import { ReloadOutlined } from '@ant-design/icons'
import { Button } from 'antd'

import RecordViewTitle from '../components/RecordViewTitle'
import StageOverview from '../components/StageOverview'
import StageSurface from '../components/StageSurface'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import AnalysisHistory from './components/AnalysisHistory'
import AnalysisResults from './components/AnalysisResults'
import { isCurrentAnalysisContext } from './components/presentation'
import { dependencyReadinessPresentation } from './components/readinessPresentation'
import { DependencyResultFooter, ResultDetail } from './components/ResultDetail'
import { useDependencyAnalysisDrawer } from './useDependencyAnalysisDrawer'

export default function RvDependencyAnalysis({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange
}: StageDrawerProps) {
  const state = useDependencyAnalysisDrawer(projectId, visible)
  const {
    view,
    setView,
    latestAnalysisQuery,
    latestAnalysis,
    readinessQuery,
    createMutation,
    selectedResultQuery
  } = state
  const { ready, prerequisiteItems } = dependencyReadinessPresentation(
    readinessQuery.data,
    onStageChange
  )
  const title =
    view.type === 'history' ? (
      <RecordViewTitle
        backLabel="返回当前概览"
        title="分析记录"
        onBack={() => setView({ type: 'latest' })}
      />
    ) : view.type === 'history-analysis' ? (
      <RecordViewTitle
        backLabel="返回历史记录"
        title="历史分析详情"
        onBack={() => setView({ type: 'history' })}
      />
    ) : view.type === 'latest-result' ? (
      <RecordViewTitle
        backLabel="返回最新分析"
        title="依赖结果详情"
        onBack={() => setView({ type: 'latest' })}
      />
    ) : view.type === 'history-result' ? (
      <RecordViewTitle
        backLabel="返回历史分析详情"
        title="历史依赖结果详情"
        onBack={() => setView({ analysis: view.analysis, type: 'history-analysis' })}
      />
    ) : (
      (stage?.title ?? '依赖分析')
    )
  return (
    <StageSurface
      visible={visible}
      onClose={onClose}
      title={title}
      size={getStageDrawerWidth('rv-dependency-analysis')}
      panelTitleVisible={view.type !== 'latest'}
      panelScrollKey={`${view.type}:${'analysis' in view ? view.analysis.id : ''}:${'resultId' in view ? view.resultId : ''}`}
      afterOpenChange={(open) => {
        if (!open) setView({ type: 'latest' })
      }}
      onHistory={view.type === 'latest' ? () => setView({ type: 'history' }) : undefined}
      loading={selectedResultQuery.isLoading}
      extra={
        view.type === 'latest' || view.type === 'history' ? (
          <Button
            type="text"
            aria-label={view.type === 'history' ? '刷新分析记录' : '刷新依赖分析信息'}
            icon={<ReloadOutlined />}
            onClick={() =>
              void (view.type === 'latest'
                ? state.refetch()
                : state.queryClient.invalidateQueries({ queryKey: state.analysisKey }))
            }
          />
        ) : undefined
      }
      footer={
        view.type === 'latest-result' && isCurrentAnalysisContext(view.analysis) ? (
          <DependencyResultFooter
            analysis={view.analysis}
            projectId={projectId ?? ''}
            result={selectedResultQuery.data}
          />
        ) : undefined
      }
    >
      {view.type === 'latest-result' || view.type === 'history-result' ? (
        <ResultDetail
          isError={selectedResultQuery.isError}
          result={selectedResultQuery.data}
          readOnly={view.type === 'history-result' || !isCurrentAnalysisContext(view.analysis)}
          onRefetch={() => void selectedResultQuery.refetch()}
        />
      ) : null}
      {view.type === 'history-analysis' ? (
        <AnalysisResults
          analysis={view.analysis}
          projectId={projectId ?? ''}
          readOnly
          onOpenResult={(resultId) =>
            setView({ analysis: view.analysis, resultId, type: 'history-result' })
          }
        />
      ) : null}
      {view.type === 'history' ? (
        <AnalysisHistory
          projectId={projectId}
          onOpenAnalysis={(analysis) => setView({ analysis, type: 'history-analysis' })}
        />
      ) : null}
      {view.type === 'latest' ? (
        <StageOverview
          label="依赖分析"
          request={{
            loading: state.isLoading,
            error: state.isError,
            hasData: Boolean(readinessQuery.data && latestAnalysisQuery.data),
            reload: () => void state.refetch()
          }}

          gate={{ ready: ready, prerequisites: prerequisiteItems }}
          result={{
            record: latestAnalysisQuery.data?.result ?? undefined,
            execution: latestAnalysisQuery.data?.execution,
            status:
              latestAnalysisQuery.data?.execution?.status ??
              latestAnalysisQuery.data?.result?.status,
            freshness: latestAnalysisQuery.data?.freshness,
            hasResult: Boolean(latestAnalysis)
          }}
          operation={{
            submitting: createMutation.isPending || state.submitted,
            start: {
              label: '执行依赖分析',
              onClick: () => createMutation.mutate(),
              loading: createMutation.isPending
            }
          }}
        >
          {latestAnalysis ? (
            <AnalysisResults
              analysis={latestAnalysis}
              projectId={projectId ?? ''}
              isCreating={createMutation.isPending}
              onOpenResult={(resultId) =>
                setView({ analysis: latestAnalysis, resultId, type: 'latest-result' })
              }
              onRerun={state.isError ? undefined : () => createMutation.mutate()}
            />
          ) : null}
        </StageOverview>
      ) : null}
    </StageSurface>
  )
}
