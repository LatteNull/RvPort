import { lazy, Suspense, useContext, useEffect, useState } from 'react'
import { Form, Modal } from 'antd'

import BaseModal from '@/components/BaseModal'
import TableViewStateProvider from '@/components/BaseTable/TableViewStateProvider'

import RuntimeEnvironmentCards from '../components/RuntimeEnvironmentCards'
import { StagePresentationContext } from '../components/StagePresentationContext'
import StageSurface from '../components/StageSurface'
import StageViewLoading from '../components/StageViewLoading'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import { EnvironmentDrawerFooter, EnvironmentDrawerTitle } from './components/drawer-chrome'
import List from './components/List'
import { useEnvironmentDrawer } from './useEnvironmentDrawer'

import styles from './index.module.scss'

const loadFormView = () => import('./components/Form')
const loadScriptForm = () => import('./components/ScriptForm')

const Executions = lazy(() => import('./components/Executions'))
const FormView = lazy(loadFormView)
const ScriptForm = lazy(loadScriptForm)
const LogView = lazy(() =>
  import('./components/views').then((module) => ({ default: module.LogView }))
)

export default function Env({
  projectId,
  visible,
  stage,
  onClose,
  onDirtyChange
}: StageDrawerProps) {
  const isPanel = useContext(StagePresentationContext) === 'panel'
  const drawer = useEnvironmentDrawer(projectId, visible, onClose)
  const [modal, modalContextHolder] = Modal.useModal()
  const isFormView = drawer.view.type === 'create' || drawer.view.type === 'edit'
  const interactiveView = isFormView ? 'form' : drawer.view.type === 'script' ? 'script' : null
  const isExecutionView = drawer.view.type === 'history' || drawer.view.type === 'log'
  const [loadedInteractiveView, setLoadedInteractiveView] = useState<'form' | 'script' | null>(null)

  useEffect(() => {
    onDirtyChange?.(drawer.hasUnsavedChanges)
    return () => onDirtyChange?.(false)
  }, [drawer.hasUnsavedChanges, onDirtyChange])

  useEffect(() => {
    if (!interactiveView) return
    let active = true
    const loadView = interactiveView === 'form' ? loadFormView : loadScriptForm
    void loadView().then(
      () => {
        if (active) setLoadedInteractiveView(interactiveView)
      },
      () => undefined // The lazy component reports load failures to the route boundary.
    )
    return () => {
      active = false
    }
  }, [interactiveView])

  const hasFooter = interactiveView !== null && loadedInteractiveView === interactiveView
  const requestInteractiveClose = () => {
    if (drawer.isBusy()) return
    if (!drawer.hasUnsavedChanges) {
      drawer.showList()
      return
    }

    modal.confirm({
      cancelText: '继续编辑',
      content: '当前填写的内容尚未保存，关闭后将无法恢复。',
      okButtonProps: { danger: true },
      okText: '放弃更改',
      title: '放弃未保存的更改？',
      onOk: drawer.showList
    })
  }

  const listContent = drawer.isListReady ? (
    <div className={styles.listView}>
      <section className={styles.runtimeEnvironmentOverview}>
        <h3>当前运行环境</h3>
        <p>后续构建、验证和测试将使用这组项目级环境。</p>
        <RuntimeEnvironmentCards
          environments={drawer.runtimeEnvironments}
          showConnectionStatus={false}
        />
      </section>
      <List
        actions={{
          checkingEnvironmentId: drawer.checkingEnvironmentId,
          onCheck: drawer.handleCheck,
          onCreate: drawer.showCreate,
          onEdit: drawer.showEdit,
          onHistory: drawer.showHistory,
          onRefresh: drawer.handleRefresh,
          onRunScript: drawer.showRunScript,
          onSetCurrent: drawer.handleSetRuntimeEnvironment,
          settingRuntimeEnvironmentId: drawer.settingRuntimeEnvironmentId
        }}
        projectId={projectId ?? ''}
        runtimeEnvironments={drawer.runtimeEnvironments}
      />
    </div>
  ) : null

  const footer = hasFooter ? (
    <EnvironmentDrawerFooter
      isRunningScript={drawer.isRunningScript}
      isSaving={drawer.isSaving}
      isTestingConnection={drawer.isTestingConnection}
      onRunScript={drawer.handleRunScript}
      onSave={drawer.handleSave}
      onShowList={requestInteractiveClose}
      view={drawer.view}
    />
  ) : null
  const title = (
    <EnvironmentDrawerTitle
      stage={stage}
      view={drawer.view}
      showBack={!isPanel && drawer.view.type !== 'list'}
      busy={drawer.busy}
      onRefresh={drawer.handleRefresh}
      onBack={() => {
        if (drawer.view.type === 'log') drawer.showHistory(drawer.view.environment)
        else requestInteractiveClose()
      }}
    />
  )
  const detailContent = isExecutionView ? (
    <Suspense fallback={<StageViewLoading description="正在加载执行记录" variant="table" />}>
      {drawer.view.type === 'history' ? (
        <Executions
          environment={drawer.view.environment}
          projectId={projectId ?? ''}
          onViewLog={drawer.showLog}
        />
      ) : null}
      {drawer.view.type === 'log' ? (
        <LogView
          loading={drawer.isExecutionDetailLoading}
          error={drawer.isExecutionDetailError}
          onRetry={() => void drawer.refetchExecutionDetail()}
          execution={drawer.executionDetail}
          onTaskCompleted={() => void drawer.refetchExecutionDetail()}
        />
      ) : null}
    </Suspense>
  ) : (
    <Suspense
      fallback={
        <StageViewLoading
          description={isFormView ? '正在加载环境表单' : '正在加载脚本表单'}
          variant="form"
        />
      }
    >
      {isFormView ? (
        <Form
          className={styles.environmentForm}
          disabled={drawer.busy}
          form={drawer.form}
          layout="vertical"
          onValuesChange={drawer.handleEnvironmentFormValuesChange}
        >
          <FormView
            key={drawer.view.type === 'edit' ? drawer.view.environment.id : 'create'}
            busy={drawer.busy}
            isBusy={drawer.isBusy}
            environment={drawer.view.type === 'edit' ? drawer.view.environment : undefined}
            isTestingConnection={drawer.isTestingConnection}
            jumpHostOptions={drawer.jumpHostOptions}
            mode={drawer.view.type === 'create' ? 'create' : 'edit'}
            onTestConnection={() => void drawer.handleTestConnection()}
            onValuesChange={drawer.handleEnvironmentFormValuesChange}
          />
        </Form>
      ) : null}
      {drawer.view.type === 'script' ? (
        <Form
          className={styles.scriptForm}
          disabled={drawer.busy}
          form={drawer.scriptForm}
          layout="vertical"
          onValuesChange={drawer.handleScriptFormValuesChange}
        >
          <ScriptForm busy={drawer.busy} environment={drawer.view.environment} />
        </Form>
      ) : null}
    </Suspense>
  )

  return (
    <TableViewStateProvider key={projectId} active={visible}>
      {modalContextHolder}
      <StageSurface
        listStateScope="external"
        afterOpenChange={drawer.handleAfterOpenChange}
        keyboard={!drawer.busy}
        closable={!drawer.busy}
        maskClosable={!drawer.busy}
        loading={!drawer.isListReady}
        size={getStageDrawerWidth('env')}
        title={isPanel ? (stage?.title ?? '环境管理') : title}
        footer={isPanel ? null : footer}
        visible={visible}
        onClose={drawer.handleClose}
      >
        {isPanel || drawer.view.type === 'list' ? listContent : detailContent}
      </StageSurface>
      {isPanel ? (
        <BaseModal
          busy={drawer.busy}
          destroyOnHidden
          footer={footer}
          maskClosable={false}
          title={title}
          visible={visible && drawer.view.type !== 'list'}
          width={isExecutionView ? 960 : 760}
          onCancel={requestInteractiveClose}
        >
          {detailContent}
        </BaseModal>
      ) : null}
    </TableViewStateProvider>
  )
}
