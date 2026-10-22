import { lazy, Suspense, useCallback, useState } from 'react'
import { ReloadOutlined } from '@ant-design/icons'
import { Button, Form, Tooltip } from 'antd'

import { projectQueryKeys } from '../../queryKeys'
import StageOverview from '../components/StageOverview'
import StageStateNotice from '../components/StageStateNotice'
import StageSurface from '../components/StageSurface'
import StageViewLoading from '../components/StageViewLoading'
import { getStageDrawerWidth } from '../drawerWidth'
import { presentPrerequisites } from '../stagePresentation'
import type { StageDrawerProps } from '../types'
import { KnowledgeBaseFooter, KnowledgeBaseTitle } from './components/drawer-chrome'
import { ScanResults } from './components/ScanResults'
import { initialScanConfig } from './types'
import { useKnowledgeBaseDrawer } from './useKnowledgeBaseDrawer'

const FindingDetail = lazy(() =>
  import('../components/FindingDetail/index').then((module) => ({ default: module.FindingDetail }))
)
const ScanHistory = lazy(() =>
  import('./components/ScanHistory').then((module) => ({ default: module.ScanHistory }))
)
const ScanInfo = lazy(() =>
  import('./components/ScanInfo').then((module) => ({ default: module.ScanInfo }))
)
const ScanConfig = lazy(() =>
  import('./components/ScanConfig').then((module) => ({ default: module.ScanConfig }))
)
const MigrationInputDetailFooter = lazy(() =>
  import('../components/MigrationInputActions').then((module) => ({
    default: module.MigrationInputDetailFooter
  }))
)

export default function Kb({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange,
  onDirtyChange
}: StageDrawerProps) {
  const [configReady, setConfigReady] = useState(false)
  const {
    latestScan,
    readinessQuery,
    submitted,
    isRecordLoading,
    isRecordError,
    refetchRecord,
    aiSuggestionReadiness,
    aiSuggestionRun,
    clearScanCache,
    findingDetail,
    form,
    handleCreateScan,
    handleCreateAiSuggestion,
    isCreating,
    isCreatingAiSuggestion,
    isCodeContextError,
    isCodeContextLoading,
    isFindingError,
    isFindingLoading,
    isHistoryFetching,
    isAiSuggestionError,
    isAiSuggestionLoading,
    isScanArtifactsError,
    isScanArtifactsLoading,
    isStageError,
    isStageLoading,
    refetchFinding,
    refetchAiSuggestion,
    refetchScanInfo,
    refetchStage,
    refreshHistory,
    setView,
    showConfig,
    showHistory,
    showRecord,
    showScanInfo,
    showResults,
    scan,
    scanArtifacts,
    sourceReady,
    x86BuildReady,
    isReadinessLoading,
    view
  } = useKnowledgeBaseDrawer(projectId, visible, onDirtyChange)
  const markConfigReady = useCallback(() => {
    form.resetFields()
    form.setFieldsValue(initialScanConfig)
    setConfigReady(true)
  }, [form])
  const openConfig = () => {
    setConfigReady(false)
    showConfig()
  }
  const scanReady = sourceReady && x86BuildReady
  const scanPrerequisites = presentPrerequisites(
    readinessQuery.data?.prerequisites ?? [],
    onStageChange
  )
  const showParentView = () => {
    if (view.type === 'record') return showHistory()
    if (view.type === 'detail')
      return view.returnTo === 'record' ? showRecord(view.scanId) : showResults()
    if (view.type === 'scan-info') {
      if (view.returnTo === 'history') return showHistory()
      if (view.returnTo === 'record') return showRecord(view.scanId)
    }
    return showResults()
  }

  return (
    <StageSurface
      onHistory={view.type === 'results' ? showHistory : undefined}
      afterOpenChange={(open) => {
        if (open) return
        clearScanCache()
        setConfigReady(false)
        setView({ type: 'results' })
      }}
      extra={
        view.type === 'history' ? (
          <Tooltip title="刷新扫描记录">
            <Button
              aria-label="刷新扫描记录"
              icon={<ReloadOutlined />}
              loading={isHistoryFetching}
              type="text"
              onClick={() => void refreshHistory()}
            />
          </Tooltip>
        ) : view.type === 'results' ? (
          <Tooltip title="刷新知识库扫描">
            <Button
              aria-label="刷新知识库扫描"
              icon={<ReloadOutlined />}
              loading={isStageLoading}
              type="text"
              onClick={() => void refetchStage()}
            />
          </Tooltip>
        ) : undefined
      }
      footer={
        view.type === 'config' && configReady ? (
          <KnowledgeBaseFooter
            isCreating={isCreating}
            sourceReady={scanReady && !isReadinessLoading}
            view={view}
            onCreateScan={() => void handleCreateScan()}
            onShowResults={showResults}
          />
        ) : undefined
      }
      loading={false}
      panelTitleVisible={view.type !== 'results'}
      panelScrollKey={`${view.type}:${'scanId' in view ? view.scanId : ''}:${'findingId' in view ? view.findingId : ''}`}
      size={getStageDrawerWidth('kb')}
      title={
        <KnowledgeBaseTitle
          disabled={isCreating && view.type === 'config'}
          stage={stage}
          view={view}
          onBack={showParentView}
        />
      }
      visible={visible}
      onClose={onClose}
    >
      <Suspense
        fallback={
          <StageViewLoading
            description="正在加载扫描视图"
            variant={view.type === 'config' ? 'form' : view.type === 'history' ? 'table' : 'detail'}
          />
        }
      >
        {view.type === 'config' ? (
          <Form
            disabled={isCreating}
            form={form}
            initialValues={initialScanConfig}
            layout="vertical"
          >
            <ScanConfig
              sourceReady={sourceReady || isReadinessLoading}
              x86BuildReady={x86BuildReady || isReadinessLoading}
              onManageSource={() => onStageChange?.('assets')}
              onManageX86Build={() => onStageChange?.('x86-build')}
              onReady={markConfigReady}
            />
          </Form>
        ) : null}
        {view.type === 'detail' ? (
          isFindingError ? (
            <StageStateNotice
              description="无法读取该扫描结果，请重新加载。"
              embedded
              primaryAction={{ label: '重新加载', onClick: () => void refetchFinding() }}
              secondaryActions={[{ label: '返回', onClick: showParentView }]}
              title="扫描结果详情加载失败"
              variant="request-error"
            />
          ) : (
            <FindingDetail
              codeContextError={isCodeContextError}
              codeContextLoading={isCodeContextLoading}
              detail={findingDetail}
              loading={isFindingLoading}
              reportActions={
                view.returnTo === 'results' &&
                findingDetail &&
                scan &&
                scan.currentSourceRevision !== false ? (
                  <Suspense fallback={null}>
                    <MigrationInputDetailFooter
                      invalidateQueryKeys={[
                        projectQueryKeys.knowledgeBaseFinding(findingDetail.id),
                        projectQueryKeys.knowledgeBaseFindings(scan.id)
                      ]}
                      migrationInputRefId={findingDetail.migrationInputRefId}
                      projectId={projectId ?? ''}
                      sourceRefId={findingDetail.id}
                      sourceRevisionId={scan.sourceRevisionId}
                      sourceType="KB_FINDING"
                      status={findingDetail.migrationInputStatus}
                    />
                  </Suspense>
                ) : undefined
              }
              showMigrationInputStatus={view.returnTo !== 'results'}
            />
          )
        ) : null}
        {view.type === 'scan-info' ? (
          <ScanInfo
            artifacts={scanArtifacts}
            error={isScanArtifactsError}
            loading={isScanArtifactsLoading}
            scan={scan}
            onRetry={() => void refetchScanInfo()}
          />
        ) : null}
        {view.type === 'history' ? (
          <ScanHistory projectId={projectId ?? ''} onOpenScan={showRecord} />
        ) : null}
      </Suspense>
      {view.type === 'record' && isRecordLoading ? (
        <StageViewLoading description="正在读取扫描记录" variant="detail" />
      ) : null}
      {view.type === 'record' && isRecordError ? (
        <StageStateNotice
          title="扫描记录加载失败"
          description="请重新读取此记录。"
          variant="request-error"
          primaryAction={{ label: '重新加载', onClick: () => void refetchRecord() }}
        />
      ) : null}
      {view.type === 'record' && scan ? (
        <ScanResults
          projectId={projectId ?? ''}
          readOnly
          scan={scan}
          onOpenFinding={(findingId) =>
            setView({ findingId, returnTo: 'record', scanId: scan.id, type: 'detail' })
          }
          onShowScanInfo={() => showScanInfo(scan.id, 'record')}
        />
      ) : null}
      {view.type === 'results' ? (
        <StageOverview
          label="知识库扫描"
          request={{
            loading: isStageLoading || isReadinessLoading,
            error: isStageError,
            hasData: Boolean(readinessQuery.data && latestScan),
            reload: () => void refetchStage()
          }}

          gate={{ ready: scanReady, prerequisites: scanPrerequisites }}
          result={{
            record: latestScan?.result ?? undefined,
            execution: latestScan?.execution,
            status: latestScan?.execution?.status ?? latestScan?.result?.status,
            freshness: latestScan?.freshness,
            hasResult: Boolean(scan)
          }}
          operation={{
            submitting: isCreating || submitted,
            start: { label: '新建扫描', onClick: openConfig }
          }}
        >
          {scan ? (
            <ScanResults
              aiSuggestion={{
                creating: isCreatingAiSuggestion,
                error: isAiSuggestionError,
                loading: isAiSuggestionLoading,
                readiness: aiSuggestionReadiness,
                run: aiSuggestionRun,
                onGenerate: () => void handleCreateAiSuggestion(),
                onRetry: () => void refetchAiSuggestion()
              }}
              projectId={projectId ?? ''}
              scan={scan}
              onOpenFinding={(findingId) =>
                setView({ findingId, returnTo: 'results', scanId: scan.id, type: 'detail' })
              }
              onRescan={isStageError ? undefined : openConfig}
              onShowScanInfo={() => showScanInfo(scan.id)}
            />
          ) : null}
        </StageOverview>
      ) : null}
    </StageSurface>
  )
}
