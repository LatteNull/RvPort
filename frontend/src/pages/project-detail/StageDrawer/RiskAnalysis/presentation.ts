import type {
  SpecializedAnalysisStatus,
  SpecializedFinding
} from '@/types/project/specialized-analysis'

import type { RiskFinding, RiskSeverity } from './types'

export const severityLabels: Record<RiskSeverity, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  info: '提示',
  unknown: '未定级'
}
export const severityColors: Record<RiskSeverity, string> = {
  high: 'error',
  medium: 'warning',
  low: 'success',
  info: 'processing',
  unknown: 'default'
}
export const statusLabels: Record<SpecializedAnalysisStatus, string> = {
  PENDING: '等待调度',
  QUEUED: '排队中',
  RUNNING: '分析中',
  COMPLETE: '分析完成',
  COMPLETE_WITH_RISK: '分析完成，发现风险',
  PARTIAL: '部分分析完成',
  FAILED: '分析失败',
  CANCELLED: '已取消',
  TIMEOUT: '分析超时'
}
export function isAnalysisActive(status?: string) {
  return ['PENDING', 'QUEUED', 'RUNNING'].includes(status ?? '')
}
export function analysisTaskStatus(status: SpecializedAnalysisStatus) {
  return ['COMPLETE', 'COMPLETE_WITH_RISK', 'PARTIAL'].includes(status) ? 'SUCCEEDED' : status
}
function object(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}
function string(value: unknown) {
  return typeof value === 'string' ? value : ''
}
function translated(value: unknown, labels: Record<string, string>) {
  const raw = string(value)
  return Object.hasOwn(labels, raw.toLowerCase()) ? labels[raw.toLowerCase()] : raw
}
function translatedList(value: unknown, labels: Record<string, string>) {
  return Array.isArray(value)
    ? value
        .filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
        .map((item) => translated(item, labels))
        .join('、')
    : ''
}
export function presentFinding(finding: SpecializedFinding): RiskFinding {
  const conclusion = object(finding.detail.conclusion)
  const plan = object(conclusion.validationPlan)
  // 仅展示接口提供的验证项；未知枚举保留原文，不能由规则名称推断方案。
  const validationPlan = [
    {
      label: '验证输入',
      value: translatedList(plan.inputClasses, {
        cancellation: '正负抵消',
        'ill-conditioned-order': '对顺序敏感的输入',
        'long-sequence': '长序列'
      })
    },
    {
      label: '误差指标',
      value: translatedList(plan.errorMetrics, {
        absolute: '绝对误差',
        relative: '相对误差',
        ulp: 'ULP（末位单位误差）',
        classification: '浮点分类',
        errno: '错误码（errno）',
        exceptions: '浮点异常'
      })
    },
    {
      label: '重复方式',
      value: translated(plan.repeatStrategy, {
        'repeat across order, vector width, and thread count':
          '改变计算顺序、向量宽度和线程数，重复测试'
      })
    },
    {
      label: '阈值来源',
      value: translated(plan.thresholdSource, {
        standard: '标准规范',
        profile: '分析配置',
        'project-policy': '项目策略',
        'user-provided': '用户提供',
        unknown: '未知'
      })
    }
  ].filter((item) => item.value)
  const level = finding.severity?.toLowerCase() ?? 'unknown'
  const severity = level in severityLabels ? (level as RiskSeverity) : 'unknown'
  return {
    id: finding.id,
    code: finding.findingCode ?? '--',
    title: finding.title || finding.titleEn || finding.findingCode || '未命名分析结果',
    severity,
    confidence:
      translated(finding.confidence, { high: '高', medium: '中', low: '低', unknown: '未知' }) ||
      '未提供',
    location: finding.filePath ?? '未提供位置',
    line: finding.startLine,
    detail: finding.message || finding.messageEn || '未提供说明',
    impact: string(conclusion.impact) || string(conclusion.impactEn) || '',
    suggestion: finding.suggestion || finding.suggestionEn || '未提供修复建议',
    validation: finding.testSuggestion || finding.testSuggestionEn || '',
    validationPlan,
    evidenceOrigin: translated(conclusion.evidenceOrigin, {
      heuristic: '启发式规则',
      deterministic: '确定性规则'
    }),
    assumptions: Array.isArray(conclusion.assumptions)
      ? conclusion.assumptions.filter((item): item is string => typeof item === 'string')
      : [],
    resultStatus:
      translated(finding.resultStatus, {
        complete: '分析完成',
        complete_with_risk: '分析完成，发现风险',
        partial: '部分分析完成',
        failed: '分析失败',
        unknown: '状态未知'
      }) || '状态未知',
    findingKind: finding.findingKind,
    requiresHumanConfirmation: finding.requiresHumanConfirmation,
    rawDetail: finding.detail
  }
}
