import type { ProjectArchiveItem, ProjectArchiveStatus } from '@/types/project'

const statusText: Record<string, string> = {
  PENDING: '等待中',
  QUEUED: '排队中',
  RUNNING: '归档中',
  SUCCEEDED: '归档完成',
  FAILED: '归档失败',
  CANCELLED: '已取消',
  TIMEOUT: '已超时'
}

export function getArchiveStatusText(status?: string | null) {
  return status ? (statusText[status] ?? status) : '缺失状态数据'
}

export function getArchiveStatusColor(status?: string | null) {
  if (status === 'SUCCEEDED') return 'success'
  if (status === 'FAILED' || status === 'CANCELLED' || status === 'TIMEOUT') return 'error'
  if (status === 'RUNNING' || status === 'QUEUED' || status === 'PENDING') return 'processing'
  return 'default'
}

export const archiveStatusOptions: Array<{ label: string; value: ProjectArchiveStatus }> = [
  { label: '等待中', value: 'PENDING' },
  { label: '排队中', value: 'QUEUED' },
  { label: '归档中', value: 'RUNNING' },
  { label: '归档完成', value: 'SUCCEEDED' },
  { label: '归档失败', value: 'FAILED' },
  { label: '已取消', value: 'CANCELLED' },
  { label: '已超时', value: 'TIMEOUT' }
]

export function getSourceRevisionLabel(
  revision?: {
    versionLabel: string | null
    gitCommit: string | null
    gitBranch: string | null
  } | null
) {
  return revision?.versionLabel ?? revision?.gitCommit ?? revision?.gitBranch ?? '未标记版本'
}

export function formatBytes(value?: number | null) {
  if (value === null || value === undefined) return '缺失归档包大小数据'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

const archiveNodeTypeLabels: Record<string, string> = {
  FLOATING_POINT_ANALYSIS: '浮点精度扫描',
  MEMORY_ORDER_ANALYSIS: '强弱内存序分析',
  AUTOMATED_TEST: '自动化测试',
  BUILD_VALIDATION: '构建验证',
  DEPENDENCY_ANALYSIS: '依赖分析',
  KB_AI_EXTENSION: '知识库 AI 建议',
  KB_SCAN: '知识库扫描',
  MIGRATION_REPORT: '迁移评估报告',
  RECHECK: '复检结果',
  REPORT_COMPARISON: '评估报告对比',
  TEST_COMPARISON: '测试结果对比'
}

const archiveCandidateTypeLabels: Record<string, string> = {
  BUILD_SUMMARY: '构建摘要',
  COMPARISON_REPORT: '对比报告',
  DIFF_REPORT: '差异报告',
  LOG: '日志',
  RAW_RESULT: '原始结果',
  REPORT: '分析报告',
  SUMMARY: '结果摘要',
  TEST_SUMMARY: '测试摘要'
}

const metadataLabels: Record<string, string> = {
  artifactCount: '产物数量',
  artifactFormats: '产物格式',
  baseReportId: '基准报告 ID',
  baseSourceRevisionId: '基准源码记录 ID',
  buildScope: '构建范围',
  buildRunId: '构建记录 ID',
  comparisonRunId: '对比记录 ID',
  confidence: '置信度',
  dependencyAnalysisRunId: '依赖分析记录 ID',
  durationMs: '执行耗时',
  environmentId: '环境 ID',
  exitCode: '退出码',
  failureCategory: '失败分类',
  failedTests: '失败测试',
  generatedAt: '生成时间',
  kbAiExtensionRunId: 'AI 建议记录 ID',
  kbScanRunId: '知识库扫描记录 ID',
  kbVersion: '知识库版本',
  passedTests: '通过测试',
  recheckRunId: '复检记录 ID',
  reportArtifactCount: '测试报告数量',
  riskLevel: '风险等级',
  schemaVersion: '数据版本',
  scriptLength: '脚本长度',
  scriptSha256: '脚本 SHA-256',
  skippedTests: '跳过测试',
  sourceRevisionId: '源码记录 ID',
  sourceDeploymentId: '源码部署记录 ID',
  status: '执行状态',
  targetReportId: '目标报告 ID',
  targetSourceRevisionId: '目标源码记录 ID',
  testBatchId: '测试批次 ID',
  testBatchRole: '测试端',
  testRunId: '测试记录 ID',
  totalTests: '测试总数'
}

const metadataValueLabels: Record<string, string> = {
  COMPLETE: '分析完成',
  COMPLETE_WITH_RISK: '分析完成，发现风险',
  PARTIAL: '部分分析完成',
  FLOATING_POINT: '浮点精度扫描',
  MEMORY_ORDER: '强弱内存序分析',
  BOTH: '双端',
  CANCELLED: '已取消',
  CRITICAL: '严重',
  FAILED: '失败',
  HIGH: '高',
  INFO: '提示',
  LOW: '低',
  MEDIUM: '中',
  QUEUED: '排队中',
  RUNNING: '进行中',
  SOURCE: '源端',
  SUCCEEDED: '成功',
  TARGET: '目标端',
  TIMEOUT: '已超时'
}

export function getArchiveNodeTypeLabel(value: string) {
  return archiveNodeTypeLabels[value] ?? value
}

export function getArchiveCandidateTypeLabel(value: string) {
  return archiveCandidateTypeLabels[value] ?? value
}

export function getArchiveItemTitle(item: ProjectArchiveItem) {
  if (item.nodeType === 'AUTOMATED_TEST') {
    if (item.metadata.testBatchRole === 'SOURCE') return '源端自动化测试'
    if (item.metadata.testBatchRole === 'TARGET') return '目标端自动化测试'
  }
  return archiveNodeTypeLabels[item.nodeType] ?? item.title ?? item.nodeType
}

export function formatArchiveMetadataLabel(value: string) {
  return metadataLabels[value] ?? value
}

export function formatArchiveMetadataValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '--'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    if (key === 'durationMs') {
      if (value < 1000) return `${value} ms`
      return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)} 秒`
    }
    if (key === 'confidence') return `${Math.round(value * 100)}%`
    return String(value)
  }
  if (typeof value === 'string') return metadataValueLabels[value] ?? value
  return JSON.stringify(value)
}
