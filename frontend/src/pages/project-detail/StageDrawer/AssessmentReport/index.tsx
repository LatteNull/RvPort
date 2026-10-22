import { lazy, Suspense, useState } from 'react'
import { ReloadOutlined } from '@ant-design/icons'
import { Button } from 'antd'

import ContentState from '@/components/ContentState'
import type {
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeModule
} from '@/types/project'

import RecordViewTitle from '../components/RecordViewTitle'
import StageOverview from '../components/StageOverview'
import StageSurface from '../components/StageSurface'
import { TaskLogPanel } from '../components/TaskLogPanel'
import { getStageDrawerWidth } from '../drawerWidth'
import { presentPrerequisites } from '../stagePresentation'
import type { StageDrawerProps } from '../types'
import { AssessmentReportResult } from './components/content'
import { AssessmentReportFooter, AssessmentReportTitle } from './components/drawer-chrome'
import ReportHistory from './components/ReportHistory'
import { useAssessmentReportDrawer } from './useAssessmentReportDrawer'

const ReportIssueDetail = lazy(() => import('./components/ReportIssueDetail'))

export default function Report({
  projectId,
  visible,
  presentation,
  onClose,
  onStageChange
}: StageDrawerProps) {
  const [view, setView] = useState<'current' | 'history' | 'record'>('current')
  const [recordId, setRecordId] = useState<string>()
  const [issueId, setIssueId] = useState<string>()
  const [selectedModule, setSelectedModule] = useState<ProjectEvaluationReportCodeModule>()
  const [selectedFile, setSelectedFile] = useState<ProjectEvaluationReportCodeFile>()
  const [isClosing, setIsClosing] = useState(false)
  const current = view === 'current' && !issueId && !selectedModule
  const drawer = useAssessmentReportDrawer(
    projectId,
    visible && current && !isClosing,
    view === 'record' && visible && !isClosing ? recordId : undefined
  )
  const report = drawer.report
  const openHistory = () => {
    setIssueId(undefined)
    setSelectedModule(undefined)
    setSelectedFile(undefined)
    setView('history')
  }
  const result =
    report?.status === 'SUCCEEDED' ? (
      <AssessmentReportResult
        canGenerate={view === 'current' && drawer.canGenerate && !drawer.submitted}
        isCreating={drawer.isCreating}
        report={report}
        selectedFile={selectedFile}
        selectedModule={selectedModule}
        onCreate={() => void drawer.handleCreate()}
        onDownload={drawer.handleDownload}
        onOpenIssue={setIssueId}
        onSelectFile={setSelectedFile}
        onSelectModule={setSelectedModule}
      />
    ) : null
  const title = issueId ? (
    <RecordViewTitle
      backLabel="返回评估报告"
      title="报告问题详情"
      onBack={() => setIssueId(undefined)}
    />
  ) : selectedFile && selectedModule ? (
    <RecordViewTitle
      backLabel={`返回 ${selectedModule.moduleName || '模块详情'}`}
      title={selectedFile.relativePath || '文件详情'}
      onBack={() => setSelectedFile(undefined)}
    />
  ) : selectedModule ? (
    <RecordViewTitle
      backLabel="返回报告总览"
      title={selectedModule.moduleName || '模块详情'}
      onBack={() => setSelectedModule(undefined)}
    />
  ) : view === 'history' ? (
    <RecordViewTitle
      backLabel="返回当前概览"
      title="评估报告记录"
      onBack={() => setView('current')}
    />
  ) : view === 'record' ? (
    <RecordViewTitle backLabel="返回历史记录" title="历史评估报告" onBack={openHistory} />
  ) : (
    <AssessmentReportTitle />
  )
  return (
    <StageSurface
      visible={visible}
      title={title}
      size={getStageDrawerWidth('report')}
      onHistory={current ? openHistory : undefined}
      panelTitleVisible={!current}
      panelScrollKey={`${view}:${recordId ?? ''}:${issueId ?? ''}:${selectedModule?.moduleKey ?? ''}:${selectedFile?.fileKey ?? ''}`}
      afterOpenChange={(open) => {
        if (!open) {
          setIsClosing(false)
          setIssueId(undefined)
          setSelectedModule(undefined)
          setSelectedFile(undefined)
          setView('current')
          setRecordId(undefined)
        }
      }}
      onClose={() => {
        setIsClosing(true)
        onClose()
      }}
      extra={
        current ? (
          <Button
            type="text"
            aria-label="刷新"
            icon={<ReloadOutlined />}
            onClick={() => void drawer.refetch()}
          />
        ) : undefined
      }
      footer={
        presentation !== 'panel' &&
        current &&
        drawer.canGenerate &&
        report?.status === 'SUCCEEDED' ? (
          <AssessmentReportFooter
            report={report}
            onManualRepair={() => onStageChange?.('manual')}
          />
        ) : undefined
      }
    >
      {issueId ? (
        <Suspense fallback={<ContentState kind="loading" description="正在加载报告详情" />}>
          <ReportIssueDetail migrationInputId={issueId} />
        </Suspense>
      ) : view === 'history' ? (
        <ReportHistory
          projectId={projectId ?? ''}
          onOpen={(id) => {
            setRecordId(id)
            setView('record')
          }}
        />
      ) : view === 'record' ? (
        drawer.selected.isLoading ? (
          <ContentState kind="loading" description="正在读取报告记录" />
        ) : drawer.selected.isError ? (
          <ContentState kind="error" description="报告记录加载失败">
            <Button onClick={() => void drawer.selected.refetch()}>重新加载</Button>
          </ContentState>
        ) : (
          (result ??
          (report ? (
            <TaskLogPanel
              className=""
              editorClassName=""
              taskId={report.taskId}
              status={report.status}
              title="报告任务日志"
              ariaLabel="报告任务日志"
            />
          ) : null))
        )
      ) : selectedModule ? (
        result
      ) : (
        <StageOverview
          label="评估报告"

          request={{
            loading: drawer.isLoading,
            error: drawer.isError,
            hasData: Boolean(drawer.readinessQuery.data && drawer.latestQuery.data),
            reload: () => void drawer.refetch()
          }}

          gate={{
            ready: drawer.generationPrerequisites.every((item) => item?.status === 'SATISFIED'),
            prerequisites: presentPrerequisites(drawer.generationPrerequisites, onStageChange)
          }}
          result={{
            record: drawer.latestQuery.data?.result ?? undefined,
            execution: drawer.latestQuery.data?.execution,
            status: drawer.latestQuery.data?.execution?.status ?? report?.status,
            freshness: drawer.latestFreshness,
            hasResult: Boolean(report)
          }}
          operation={{
            submitting: drawer.isCreating || drawer.submitted,
            start: {
              label: '生成评估报告',
              loading: drawer.isCreating,
              onClick: () => void drawer.handleCreate()
            }
          }}
        >
          {result}
        </StageOverview>
      )}
    </StageSurface>
  )
}
