import { Descriptions, Tooltip } from 'antd'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'
import type { ProjectDependencyAnalysisResult } from '@/types/project/dependency-analysis'

import {
  dependencyRiskTag,
  dependencyTargetMatchStatusTag,
  dependencyTypeLabel,
  displayValue,
  packageLabel
} from './presentation'

import styles from './index.module.scss'

function tooltipTextCell(value: string | null | undefined) {
  const content = displayValue(value)
  return (
    <Tooltip title={content}>
      <span className={styles.ellipsisText}>{content}</span>
    </Tooltip>
  )
}

export function DependencyResultDetailContent({
  result
}: {
  result: ProjectDependencyAnalysisResult
}) {
  return (
    <div className={styles.content}>
      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="依赖">{result.dependencyName}</Descriptions.Item>
        <Descriptions.Item label="风险">{dependencyRiskTag(result.riskLevel)}</Descriptions.Item>
        <Descriptions.Item label="类型">
          {dependencyTypeLabel(result.dependencyType)}
        </Descriptions.Item>
        <Descriptions.Item label="目标匹配">
          {dependencyTargetMatchStatusTag(result.targetMatchStatus)}
        </Descriptions.Item>
        <Descriptions.Item label="源提供包">
          {packageLabel(result.sourceProviderPackage, result.sourceProviderVersion)}
        </Descriptions.Item>
        <Descriptions.Item label="目标提供包">
          {packageLabel(result.targetProviderPackage, result.targetProviderVersion)}
        </Descriptions.Item>
        <Descriptions.Item label="源端检测版本">
          {displayValue(result.sourceDetectedVersion)}
        </Descriptions.Item>
        <Descriptions.Item label="目标端检测版本">
          {displayValue(result.targetDetectedVersion)}
        </Descriptions.Item>
        <Descriptions.Item label="提供包版本状态">
          {displayValue(result.providerVersionStatus)}
        </Descriptions.Item>
        <Descriptions.Item label="证据置信度">
          {displayValue(result.versionEvidenceConfidence)}
        </Descriptions.Item>
        <Descriptions.Item label="结论置信度">{displayValue(result.confidence)}</Descriptions.Item>
        <Descriptions.Item label="来源位置" span={2}>
          {displayValue(result.locationLabel)}
        </Descriptions.Item>
        <Descriptions.Item label="建议" span={2}>
          {tooltipTextCell(result.recommendation)}
        </Descriptions.Item>
      </Descriptions>
      <section className={styles.evidence}>
        <h3>分析证据</h3>
        <div className={styles.evidenceViewport}>
          <CodeMirrorEditor
            ariaLabel="依赖分析证据"
            height="100%"
            language="json"
            readOnly
            value={JSON.stringify(result.evidence, null, 2)}
          />
        </div>
      </section>
    </div>
  )
}
