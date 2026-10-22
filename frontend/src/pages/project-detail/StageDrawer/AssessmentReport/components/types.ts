import type {
  ProjectEvaluationReport,
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeModule
} from '@/types/project'

export interface OrganizedReportProps {
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
}
