import { Tag } from 'antd'

export function reportRiskToken(value?: string | null) {
  return value?.split('/')[0]?.toUpperCase() ?? 'UNKNOWN'
}

export function reportRiskText(value?: string | null) {
  return (
    {
      COMMENT: '备注',
      CRITICAL: '严重',
      HIGH: '高',
      INFO: '提示',
      LOW: '低',
      MEDIUM: '中',
      UNKNOWN: '--'
    } as Record<string, string>
  )[reportRiskToken(value)]
}

export function reportRiskTag(value?: string | null) {
  const risk = reportRiskToken(value)
  const color =
    risk === 'CRITICAL' || risk === 'HIGH'
      ? 'error'
      : risk === 'MEDIUM'
        ? 'warning'
        : risk === 'LOW'
          ? 'success'
          : 'default'
  return <Tag color={color}>{reportRiskText(risk)}</Tag>
}

export function reportFindingTypeText(value?: string | null) {
  const token = normalizeReportToken(value)
  if (!token || token === 'UNCLASSIFIED') return '未分类问题'
  const labels: Record<string, string> = {
    BUILD_CONFIGURATION: '构建配置',
    COMMENT: '架构相关注释',
    HEADER: '专用头文件',
    INTRINSIC: '内建函数',
    TYPE: '类型兼容',
    VECTOR_TYPE: '向量类型',
    X86_COMMENT_HINT: 'x86 架构相关注释'
  }
  return labels[token] ?? value?.trim() ?? '未分类问题'
}

export function reportFindingTitleText(issueTitle?: string | null, findingType?: string | null) {
  const title = issueTitle?.trim()
  if (!title || normalizeReportToken(title) === normalizeReportToken(findingType)) {
    return reportFindingTypeText(findingType)
  }
  return title
}

export function reportModuleBasisText(value?: string | null) {
  const token = normalizeReportToken(value)
  return (
    (
      {
        BUILD_ARTIFACT: '构建产物识别',
        EXPLICIT_BUILD_TARGET: '显式构建目标',
        NEAREST_BUILD_DESCRIPTOR: '按构建文件归类',
        DIRECTORY: '目录识别',
        PROJECT_ROOT: '项目根模块',
        UNLOCATED: '未定位'
      } as Record<string, string>
    )[token] ??
    value?.trim() ??
    '识别依据未知'
  )
}

function normalizeReportToken(value?: string | null) {
  return (
    value
      ?.trim()
      .replace(/[\s-]+/g, '_')
      .toUpperCase() ?? ''
  )
}

export function reportConfidenceText(value?: string | null) {
  return (
    (
      {
        HIGH: '高可信度',
        LOW: '低可信度',
        MEDIUM: '中可信度'
      } as Record<string, string>
    )[value ?? ''] ??
    value ??
    '可信度未知'
  )
}

export function reportSourceTypeText(value?: string | null) {
  return (
    (
      {
        DEPENDENCY_RESULT: '依赖分析',
        KB_FINDING: '知识库扫描',
        FLOATING_POINT_FINDING: '浮点精度扫描',
        MEMORY_ORDER_FINDING: '强弱内存序分析'
      } as Record<string, string>
    )[value ?? ''] ??
    value ??
    '来源待补充'
  )
}
