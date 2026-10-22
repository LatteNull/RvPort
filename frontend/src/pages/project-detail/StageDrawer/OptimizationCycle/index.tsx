import { lazy, Suspense, useState } from 'react'
import { ReloadOutlined } from '@ant-design/icons'
import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Tag, Tooltip } from 'antd'

import ContentState from '@/components/ContentState'
import type { ProjectOptimizationCycle } from '@/types/project'

import { projectQueryKeys } from '../../queryKeys'
import RecordViewTitle from '../components/RecordViewTitle'
import StageStateNotice, { type StageStatePrerequisite } from '../components/StageStateNotice'
import StageSurface from '../components/StageSurface'
import StageViewLoading from '../components/StageViewLoading'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import { CycleSummary } from './components/CycleSummary'
import { getOptimizationNextAction } from './presentation'
import { useOptimizationCycleDrawer } from './useOptimizationCycleDrawer'

import styles from './index.module.scss'

const CycleHistory = lazy(() =>
  import('./components/CycleHistory').then((module) => ({ default: module.CycleHistory }))
)

export default function Optimize({
  projectId,
  visible,
  presentation,
  stage,
  onClose,
  onStageChange
}: StageDrawerProps) {
  const [view, setView] = useState<
    { type: 'latest' } | { type: 'history' } | { cycle: ProjectOptimizationCycle; type: 'record' }
  >({ type: 'latest' })
  const [isClosing, setIsClosing] = useState(false)
  const currentEnabled = visible && view.type === 'latest' && !isClosing
  const drawer = useOptimizationCycleDrawer(projectId, currentEnabled)
  const queryClient = useQueryClient()
  const historyKey = projectQueryKeys.optimizationCycles(projectId)
  const isHistoryFetching = useIsFetching({ queryKey: historyKey }) > 0
  const displayedCycle = view.type === 'record' ? view.cycle : drawer.currentCycle
  const nextAction = displayedCycle ? getOptimizationNextAction(displayedCycle) : undefined
  const sourcePrerequisites: StageStatePrerequisite[] = [
    {
      action: drawer.ready
        ? undefined
        : {
            label: '前往源码管理',
            onClick: () => onStageChange?.('assets')
          },
      key: 'active-source',
      label: '当前源码',
      ready: drawer.ready,
      value: drawer.ready ? '已准备' : '未导入或未激活'
    }
  ]
  const title =
    view.type === 'history' ? (
      <RecordViewTitle
        backLabel="返回当前结果"
        title="优化轮次记录"
        onBack={() => setView({ type: 'latest' })}
      />
    ) : view.type === 'record' ? (
      <RecordViewTitle
        backLabel="返回优化轮次记录"
        title="优化轮次概览"
        onBack={() => setView({ type: 'history' })}
      />
    ) : (
      (stage?.title ?? '优化闭环')
    )

  return (
    <StageSurface
      onHistory={view.type === 'latest' ? () => setView({ type: 'history' }) : undefined}
      afterOpenChange={(open) => {
        if (open) return
        setIsClosing(false)
        setView({ type: 'latest' })
      }}
      extra={
        view.type !== 'record' ? (
          <Tooltip title={view.type === 'history' ? '刷新优化轮次记录' : '刷新'}>
            <Button
              aria-label={view.type === 'history' ? '刷新优化轮次记录' : '刷新'}
              icon={<ReloadOutlined />}
              loading={view.type === 'history' ? isHistoryFetching : drawer.isFetching}
              type="text"
              onClick={() =>
                void (view.type === 'history'
                  ? queryClient.invalidateQueries({ queryKey: historyKey })
                  : drawer.refetch())
              }
            />
          </Tooltip>
        ) : undefined
      }
      footer={
        presentation !== 'panel' && view.type === 'latest' && nextAction ? (
          <Button type="primary" onClick={() => onStageChange?.(nextAction.stageId)}>
            {nextAction.label}
          </Button>
        ) : undefined
      }
      loading={view.type === 'latest' && drawer.isLoading}
      panelTitleVisible={view.type !== 'latest'}
      panelScrollKey={`${view.type}:${view.type === 'record' ? view.cycle.id : ''}`}
      size={getStageDrawerWidth('optimize')}
      title={title}
      visible={visible}
      onClose={() => {
        setIsClosing(true)
        onClose()
      }}
    >
      {view.type === 'latest' && drawer.isError && drawer.hasData ? (
        <Alert showIcon type="warning" title="刷新失败，正在显示上次读取的内容。" />
      ) : null}
      {view.type === 'history' ? (
        projectId ? (
          <Suspense fallback={<StageViewLoading description="正在加载优化记录" variant="table" />}>
            <CycleHistory
              projectId={projectId}
              onOpen={(cycle) => setView({ cycle, type: 'record' })}
            />
          </Suspense>
        ) : null
      ) : view.type === 'latest' && drawer.isError && !drawer.hasData ? (
        <div className={styles.statePanel}>
          <ContentState kind="error" description="优化轮次加载失败">
            <Button type="primary" onClick={() => void drawer.refetch()}>
              重试
            </Button>
          </ContentState>
        </div>
      ) : view.type === 'latest' && !drawer.ready ? (
        <StageStateNotice
          description="当前没有可用源码版本，请先完成源码导入并设为当前源码。"
          prerequisites={sourcePrerequisites}
          title="暂不能查看优化闭环"
          variant="prerequisite"
        />
      ) : !displayedCycle ? (
        <div className={styles.statePanel}>
          <ContentState
            description={
              drawer.freshness === 'STALE'
                ? '当前源码尚无优化轮次，历史记录中保留了旧源码的轮次。'
                : '当前源码尚无优化轮次，请刷新或检查源码状态。'
            }
          >
            <Button onClick={() => onStageChange?.('assets')}>前往源码管理</Button>
          </ContentState>
        </div>
      ) : (
        <div className={styles.content}>
          <section className={styles.overviewSection}>
            <CycleSummary
              actions={
                view.type === 'record' ? (
                  <Tag>只读记录</Tag>
                ) : presentation === 'panel' && nextAction ? (
                  <Button type="primary" onClick={() => onStageChange?.(nextAction.stageId)}>
                    {nextAction.label}
                  </Button>
                ) : undefined
              }
              cycle={displayedCycle}
            />
          </section>
        </div>
      )}
    </StageSurface>
  )
}
