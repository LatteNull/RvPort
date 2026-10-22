import type {
  ProjectEvaluationReport,
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeModule
} from '@/types/project'

import OrganizedReport from './OrganizedReport'

export function AssessmentReportResult({
  canGenerate,
  isCreating,
  report,
  selectedFile,
  selectedModule,
  onCreate,
  onDownload,
  onOpenIssue,
  onSelectFile,
  onSelectModule
}: {
  canGenerate: boolean
  isCreating: boolean
  report: ProjectEvaluationReport
  selectedFile?: ProjectEvaluationReportCodeFile
  selectedModule?: ProjectEvaluationReportCodeModule
  onCreate: () => void
  onDownload: (format: 'HTML' | 'JSON') => void
  onOpenIssue: (migrationInputId: string) => void
  onSelectFile: (file: ProjectEvaluationReportCodeFile) => void
  onSelectModule: (module: ProjectEvaluationReportCodeModule) => void
}) {
  return (
    <OrganizedReport
      canGenerate={canGenerate}
      isCreating={isCreating}
      report={report}
      selectedFile={selectedFile}
      selectedModule={selectedModule}
      onCreate={onCreate}
      onDownload={onDownload}
      onOpenIssue={onOpenIssue}
      onSelectFile={onSelectFile}
      onSelectModule={onSelectModule}
    />
  )
}
