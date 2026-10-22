import type {
  ProjectEvaluationReport,
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeFinding,
  ProjectEvaluationReportCodeModule,
  ProjectEvaluationReportInput
} from '@/types/project'

export const moduleFixture: ProjectEvaluationReportCodeModule = {
  moduleKey: 'simd',
  moduleName: 'SIMD core',
  highestRisk: 'HIGH',
  basis: 'BUILD_TARGET',
  confidence: 'HIGH',
  fileCount: 2,
  findingCount: 2,
  findingTypeCount: 1,
  relatedModuleKeys: [],
  typeCounts: { INTRINSIC: 2 },
  riskCounts: { HIGH: 2 }
}
export const fileFixture: ProjectEvaluationReportCodeFile = {
  fileKey: 'simd-file',
  relativePath: 'src/simd.c',
  contextAvailable: false,
  findingCount: 2,
  findingTypeCount: 1,
  highestRisk: 'HIGH',
  riskCounts: { HIGH: 2 },
  sourceContentHash: null,
  typeCounts: { INTRINSIC: 2 }
}
export const findingFixture: ProjectEvaluationReportCodeFinding = {
  id: 'finding-1',
  issueTitle: 'Intrinsic call',
  findingType: 'INTRINSIC',
  relativePath: 'src/simd.c',
  columnStart: null,
  columnEnd: null,
  lineStart: 12,
  lineEnd: 12,
  locationAvailable: true,
  recommendation: 'Replace intrinsic',
  riskLevel: 'HIGH',
  sourceDetail: {},
  sourceRefId: 'source-finding-1',
  symbol: '_mm_add'
}
export const reportFixture: ProjectEvaluationReport = {
  id: 'report-1',
  title: 'Report',
  artifacts: [],
  createdAt: '2026-09-29T00:00:00Z',
  generatedAt: '2026-09-29T00:00:00Z',
  projectId: 'project-1',
  reportType: 'EVALUATION',
  riskLevel: 'HIGH',
  sourceRevisionId: 'source-1',
  status: 'SUCCEEDED',
  taskId: 'task-1',
  summary: { codeModuleCount: 35, codeFindingCount: 35, dependencyAnalysisInputCount: 35 }
}
export function dependencyFixtures(total: number): ProjectEvaluationReportInput[] {
  return Array.from({ length: total }, (_, index) => ({
    id: `input-${index + 1}`,
    inputId: `dependency-${index + 1}`,
    createdAt: '2026-09-29T00:00:00Z',
    inputType: 'MIGRATION_INPUT_REF',
    reportId: 'report-1',
    inputSnapshot: {
      sourceType: 'DEPENDENCY_RESULT',
      issueTitle: `Dependency issue ${index + 1}`,
      detectedLevel: 'HIGH'
    }
  }))
}
