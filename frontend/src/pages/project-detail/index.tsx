import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useBeforeUnload, useBlocker, useNavigate, useParams } from 'react-router'
import { Button, Modal, Segmented } from 'antd'

import ContentState from '@/components/ContentState'

import ProjectSummary from './components/ProjectSummary'
import { ProjectOverviewContext } from './ProjectOverviewContext'
import {
  isProjectStageId,
  type ProjectView,
  projectViewPath,
  resolveProjectView
} from './projectView'
import StageDrawer from './StageDrawer'
import { preloadEnvironmentStage } from './StageDrawer/stageLoaders'
import { useProjectPipelineData } from './useProjectPipelineData'
import { useProjectTaskEvents } from './useProjectTaskEvents'
import { useProjectViewTransition } from './useProjectViewTransition'
import { getWorkflowStageData } from './Workflow/stageData'
import StepNavigation from './Workflow/StepNavigation'

import styles from './index.module.scss'

const Workflow = lazy(() => import('./Workflow'))

function WorkflowLoading() {
  return (
    <div aria-busy="true" aria-label="正在加载项目流水线" className={styles.workflowLoading}>
      <div aria-hidden="true" className={styles.workflowLoadingTrack}>
        <span />
        <span />
        <span />
      </div>
      <span className={styles.workflowLoadingText}>正在载入流水线</span>
    </div>
  )
}

function ProjectTaskEventSubscription({
  eventCursor,
  projectId
}: {
  eventCursor: number
  projectId: string
}) {
  const [connectionBaseline] = useState(() => ({ eventCursor, projectId }))
  useProjectTaskEvents(connectionBaseline.projectId, connectionBaseline.eventCursor)
  return null
}

export default function ProjectPipelineWorkbenchPage() {
  const { projectId, '*': viewPath } = useParams()
  const navigate = useNavigate()
  const viewLocation = useMemo(() => resolveProjectView(viewPath), [viewPath])
  const { overview, workflowStatus, isError, isLoading, isFetching, refetch } =
    useProjectPipelineData(projectId)
  const selectedStage = useMemo(
    () => getWorkflowStageData(viewLocation.stageId, workflowStatus),
    [viewLocation.stageId, workflowStatus]
  )

  const isStepView = viewLocation.view === 'steps'
  const [workflowFocus, setWorkflowFocus] = useState<{
    projectId: string
    stageId: string
    request: number
  }>()
  const focusTarget = workflowFocus?.projectId === projectId ? workflowFocus : undefined
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const blocker = useBlocker(hasUnsavedChanges)
  const transitionProjectView = useProjectViewTransition()

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!hasUnsavedChanges) return
        event.preventDefault()
        event.returnValue = ''
      },
      [hasUnsavedChanges]
    )
  )

  useEffect(() => {
    if (viewLocation.valid || !projectId) return
    navigate(projectViewPath(projectId, 'workflow'), { replace: true })
  }, [navigate, projectId, viewLocation.valid])

  useEffect(() => {
    if (overview && !isStepView) void preloadEnvironmentStage().catch(() => undefined)
  }, [isStepView, overview])

  const handleStageClick = useCallback(
    (stageId: string) => {
      if (!projectId || !isProjectStageId(stageId)) return
      const targetView: ProjectView = isStepView ? 'steps' : 'workflow'
      if (stageId === selectedStage?.id && targetView === viewLocation.view) return
      const navigateToStage = () => navigate(projectViewPath(projectId, targetView, stageId))

      if (stageId === 'env') void preloadEnvironmentStage().catch(() => undefined)
      navigateToStage()
    },
    [isStepView, navigate, projectId, selectedStage?.id, viewLocation.view]
  )
  const handleReturnToOverview = useCallback(() => {
    if (projectId) navigate(projectViewPath(projectId, 'workflow'), { replace: true })
  }, [navigate, projectId])
  const handleStageChange = useCallback(
    (stageId: string) => {
      if (!projectId || !isProjectStageId(stageId)) return
      const targetView: ProjectView = isStepView ? 'steps' : 'workflow'
      navigate(projectViewPath(projectId, targetView, stageId))
    },
    [isStepView, navigate, projectId]
  )
  const handleViewChange = useCallback(
    (view: ProjectView) => {
      if (!projectId || view === viewLocation.view) return
      if (view === 'workflow') {
        if (selectedStage) {
          setWorkflowFocus((previous) => ({
            projectId,
            stageId: selectedStage.id,
            request: (previous?.request ?? 0) + 1
          }))
        }
        transitionProjectView(
          view,
          (options) => navigate(projectViewPath(projectId, 'workflow'), options),
          !hasUnsavedChanges
        )
        return
      }
      const requestedStageId = selectedStage?.id ?? workflowStatus?.currentStageId
      const targetStageId =
        requestedStageId && isProjectStageId(requestedStageId) ? requestedStageId : 'project'
      transitionProjectView(
        view,
        (options) => navigate(projectViewPath(projectId, 'steps', targetStageId), options),
        !hasUnsavedChanges
      )
    },
    [
      hasUnsavedChanges,
      navigate,
      projectId,
      selectedStage,
      transitionProjectView,
      viewLocation.view,
      workflowStatus?.currentStageId
    ]
  )
  const viewSwitcher = overview ? (
    <div aria-label="视图切换" className={styles.viewModeSwitcher} role="group">
      <Segmented
        aria-label="项目视图"
        options={[
          { label: 'Workflow', value: 'workflow' },
          { label: 'Step', value: 'steps' }
        ]}
        size="small"
        value={viewLocation.view}
        onChange={(value) => handleViewChange(value as ProjectView)}
      />
    </div>
  ) : null

  return (
    <ProjectOverviewContext.Provider
      value={{
        projectId,
        data: overview,
        isError,
        isLoading,
        isFetching: Boolean(isFetching),
        refetch
      }}
    >
      <div className={styles.page}>
        <Modal
          cancelText="继续编辑"
          okButtonProps={{ danger: true }}
          okText="放弃更改"
          open={blocker.state === 'blocked'}
          title="放弃未保存的更改？"
          onCancel={() => blocker.reset?.()}
          onOk={() => blocker.proceed?.()}
        >
          当前填写的内容尚未保存，离开后将无法恢复。
        </Modal>
        {projectId && overview && (
          <ProjectTaskEventSubscription
            key={projectId}
            eventCursor={overview.latestTaskEventId}
            projectId={projectId}
          />
        )}
        <h1 className={styles.screenReaderOnly}>{overview?.project.name ?? '项目流水线工作台'}</h1>
        {isStepView && overview ? (
          <header aria-label="项目页头" className={styles.pageHeader}>
            <ProjectSummary compact overview={overview} />
          </header>
        ) : null}

        {isLoading && (
          <div className={styles.statePanel}>
            <ContentState kind="loading" description="正在加载项目工作台" compact />
          </div>
        )}

        {isError && (
          <div className={styles.statePanel}>
            <ContentState kind="error" description="项目流水线工作台加载失败，请稍后重试">
              <Button type="primary" onClick={() => void refetch()}>
                重试
              </Button>
            </ContentState>
          </div>
        )}

        {!isLoading && !isError && !overview && (
          <div className={styles.statePanel}>
            <ContentState description="暂无项目流水线数据" />
          </div>
        )}

        {overview && (
          <div className={styles.viewFrame}>
            <section
              aria-label="项目总览"
              className={styles.overview}
              data-hidden={isStepView || undefined}
              inert={isStepView}
              aria-hidden={isStepView || undefined}
            >
              <ProjectSummary overview={overview} />
              <div className={styles.workflowSurface}>
                {!isStepView && viewSwitcher}
                <Suspense fallback={<WorkflowLoading />}>
                  <Workflow
                    focusedStageId={focusTarget?.stageId}
                    focusRequest={focusTarget?.request}
                    focusEnabled={!isStepView}
                    selectedStageId={isStepView ? undefined : selectedStage?.id}
                    workflowStatus={workflowStatus}
                    onStageClick={handleStageClick}
                  />
                </Suspense>
              </div>
            </section>
            {isStepView && selectedStage && (
              <div className={styles.workspace}>
                <StepNavigation
                  viewSwitcher={viewSwitcher}
                  workflowStatus={workflowStatus}
                  selectedStageId={selectedStage.id}
                  onStageClick={handleStageClick}
                />
                <section aria-label="阶段工作区" className={styles.stageContent}>
                  <StageDrawer
                    key={`${projectId}:${selectedStage.id}`}
                    projectId={projectId}
                    presentation="panel"
                    visible
                    stage={selectedStage}
                    onClose={handleReturnToOverview}
                    onStageChange={handleStageChange}
                    onDirtyChange={setHasUnsavedChanges}
                  />
                </section>
              </div>
            )}
            {!isStepView && (
              <StageDrawer
                key={projectId}
                projectId={projectId}
                visible={Boolean(selectedStage)}
                stage={selectedStage}
                onClose={handleReturnToOverview}
                onStageChange={handleStageChange}
                onDirtyChange={setHasUnsavedChanges}
              />
            )}
          </div>
        )}
      </div>
    </ProjectOverviewContext.Provider>
  )
}
