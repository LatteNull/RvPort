import { type ReactNode, useState } from 'react'
import { RobotOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Select, Tag } from 'antd'

import type {
  KnowledgeBaseOccurrence,
  ProjectKnowledgeBaseCodeContext,
  ProjectKnowledgeBaseFindingDetail
} from '@/types/project/knowledge-base'
import { formatDateTime } from '@/utils/display'

import { MigrationInputStatusTag } from '../MigrationInputActions'
import StageViewLoading from '../StageViewLoading'
import {
  formatFindingLocation,
  getCompletionLabel,
  getEvidenceKindLabel,
  getFindingDetailModel,
  getFindingSourceLocation,
  getReachabilityLabel,
  getReasonCodeLabel,
  missingFindingValue
} from './findingDetailPresentation'
import { FindingFacts, FindingRawData } from './FindingDisclosures'
import { EvidencePath, SourceEvidence } from './FindingEvidence'
import FindingNextSteps from './FindingNextSteps'
import { findingTitle } from './presentation'
import { normalizeKnowledgeBaseSeverity, renderSeverityTag } from './tags'

import styles from './index.module.scss'

type FindingDetailData = ProjectKnowledgeBaseFindingDetail & {
  codeContext?: ProjectKnowledgeBaseCodeContext
}

function OccurrenceSelector({
  occurrences,
  location,
  selectedIndex,
  onSelect
}: {
  occurrences: KnowledgeBaseOccurrence[]
  location?: KnowledgeBaseOccurrence['location'] | null
  selectedIndex: number
  onSelect: (index: number) => void
}) {
  const selectedOccurrence = occurrences[selectedIndex]

  return (
    <div className={styles.evidenceWorkspaceHeader}>
      <div className={styles.evidenceWorkspaceIdentity}>
        <h3 id="finding-evidence-workspace-title">证据工作区</h3>
        <strong>{formatFindingLocation(location)}</strong>
      </div>
      <div className={styles.evidenceWorkspaceMeta} aria-label="位置摘要">
        {selectedOccurrence ? (
          <small>
            {getEvidenceKindLabel(selectedOccurrence.kind)} ·{' '}
            {getReachabilityLabel(selectedOccurrence.selectionStatus)}
          </small>
        ) : null}
        {occurrences.length > 1 ? (
          <label className={styles.occurrenceSummary}>
            <span>命中位置</span>
            <Select
              aria-label="选择 Finding 命中位置"
              options={occurrences.map((occurrence, index) => ({
                label: `位置 ${index + 1} · ${formatFindingLocation(occurrence.location)}`,
                value: index
              }))}
              value={selectedIndex}
              onChange={onSelect}
            />
          </label>
        ) : (
          <div className={styles.occurrenceSummary}>
            <span>命中位置</span>
            <strong>{occurrences.length ? '1 处' : '未提供'}</strong>
          </div>
        )}
      </div>
    </div>
  )
}

function FindingWorkspace({
  detail,
  codeContextLoading,
  codeContextError,
  reportActions,
  showMigrationInputStatus
}: {
  detail: FindingDetailData
  codeContextLoading?: boolean
  codeContextError?: boolean
  reportActions?: ReactNode
  showMigrationInputStatus: boolean
}) {
  const model = getFindingDetailModel(detail)
  const { conclusion, fact, occurrences } = model
  const [selectedOccurrenceIndex, setSelectedOccurrenceIndex] = useState(
    model.defaultOccurrenceIndex
  )
  const [selectedEvidenceIndex, setSelectedEvidenceIndex] = useState<number | null>(null)
  const [sourceEvidenceIndex, setSourceEvidenceIndex] = useState<number | null>(null)
  const selectedOccurrence = occurrences[selectedOccurrenceIndex]
  const primaryLocation = getFindingSourceLocation(detail, model, selectedOccurrence)
  const allowFindingContext =
    !selectedOccurrence || selectedOccurrenceIndex === model.defaultOccurrenceIndex
  const selectedEvidenceStep =
    selectedEvidenceIndex === null ? undefined : model.evidencePath.steps[selectedEvidenceIndex]
  const sourceEvidenceStep =
    sourceEvidenceIndex === null ? undefined : model.evidencePath.steps[sourceEvidenceIndex]
  const location = sourceEvidenceStep?.source ?? primaryLocation
  const selectedReasonCodes = selectedOccurrence?.reasonCodes ?? []
  const selectOccurrence = (index: number) => {
    setSelectedOccurrenceIndex(index)
    setSelectedEvidenceIndex(null)
    setSourceEvidenceIndex(null)
  }
  const selectEvidenceStep = (index: number) => {
    const step = model.evidencePath.steps[index]
    setSelectedEvidenceIndex(index)
    // 分类与结论没有直接源码时保留最近一次有效代码，避免点击后代码区突然清空。
    if (step?.source?.context?.lines?.length) setSourceEvidenceIndex(index)
  }
  const showPrimaryContext = () => {
    setSelectedEvidenceIndex(null)
    setSourceEvidenceIndex(null)
  }

  return (
    <article className={styles.findingWorkspace}>
      <section
        className={styles.findingConclusionV2}
        data-severity={normalizeKnowledgeBaseSeverity(conclusion.severity ?? detail.severity)}
        aria-labelledby="finding-title"
      >
        <div className={styles.findingConclusionIcon} aria-hidden="true">
          <SafetyCertificateOutlined />
        </div>
        <div className={styles.findingConclusionCopy}>
          <span className={styles.findingEyebrow}>迁移判断</span>
          <h2 id="finding-title">{findingTitle(detail)}</h2>
          <p>{conclusion.reason ?? detail.description ?? '未提供判断原因。'}</p>
        </div>
        <div className={styles.findingConclusionMeta} aria-label="判断摘要">
          <div className={styles.findingConclusionTags}>
            {renderSeverityTag(conclusion.severity ?? detail.severity)}
            <Tag color={conclusion.blocking ? 'error' : undefined}>
              {conclusion.blocking ? '阻塞迁移' : '非阻塞'}
            </Tag>
          </div>
          <div className={styles.findingConfidence}>
            <span>判断置信度</span>
            <strong>
              {typeof conclusion.confidence === 'number'
                ? `${Math.round(conclusion.confidence * 100)}%`
                : '未提供'}
            </strong>
          </div>
        </div>
        {showMigrationInputStatus ? (
          <div className={styles.findingReadOnlyStatus}>
            <span>历史记录 · 只读</span>
            <MigrationInputStatusTag status={detail.migrationInputStatus} />
          </div>
        ) : null}
      </section>

      <section
        className={styles.evidenceWorkspace}
        aria-labelledby="finding-evidence-workspace-title"
      >
        <OccurrenceSelector
          location={location}
          occurrences={occurrences}
          selectedIndex={selectedOccurrenceIndex}
          onSelect={selectOccurrence}
        />
        <div className={styles.evidenceWorkbench}>
          <SourceEvidence
            codeContext={detail.codeContext}
            codeContextError={codeContextError}
            codeContextLoading={codeContextLoading}
            highlightText={fact.matchedText ?? fact.symbol ?? detail.symbol ?? undefined}
            location={location}
            preferCodeContext={allowFindingContext && sourceEvidenceIndex === null}
            selectedStep={selectedEvidenceStep}
            sourceStep={sourceEvidenceStep}
            showingEvidenceSource={sourceEvidenceIndex !== null}
            onShowPrimaryContext={showPrimaryContext}
          />
          <EvidencePath
            model={model}
            selectedIndex={selectedEvidenceIndex}
            onSelect={selectEvidenceStep}
          />
        </div>
      </section>

      <FindingNextSteps
        suggestion={conclusion.suggestion ?? detail.suggestion ?? '当前没有可用的处理建议。'}
        reportActions={reportActions}
      >
        {detail.aiExtension ? (
          <div className={styles.findingAiSupplement}>
            <RobotOutlined aria-hidden="true" />
            <div>
              <strong>AI 补充建议</strong>
              <p>{detail.aiExtension.aiSummary ?? '没有补充说明。'}</p>
              <p>{detail.aiExtension.aiSuggestion ?? '没有补充建议。'}</p>
              <small>
                AI 补充不替代静态证据
                {typeof detail.aiExtension.confidence === 'number'
                  ? ` · 置信度 ${Math.round(detail.aiExtension.confidence * 100)}%`
                  : ''}
                {' · '}
                {formatDateTime(detail.aiExtension.createdAt)}
              </small>
            </div>
          </div>
        ) : null}
      </FindingNextSteps>

      <FindingFacts>
        <dl className={styles.findingFactsContent}>
          <div>
            <dt>规则 ID</dt>
            <dd>{detail.ruleId || missingFindingValue}</dd>
          </div>
          <div>
            <dt>事实类型</dt>
            <dd>{getEvidenceKindLabel(fact.kind)}</dd>
          </div>
          <div>
            <dt>符号</dt>
            <dd>{fact.symbol ?? detail.symbol ?? '无'}</dd>
          </div>
          <div>
            <dt>命中文本</dt>
            <dd>{fact.matchedText ?? missingFindingValue}</dd>
          </div>
          <div>
            <dt>问题类型</dt>
            <dd>{conclusion.findingType ?? detail.category ?? missingFindingValue}</dd>
          </div>
          <div>
            <dt>架构可达性</dt>
            <dd>{getReachabilityLabel(conclusion.archReachability)}</dd>
          </div>
          <div>
            <dt>当前配置</dt>
            <dd>{selectedOccurrence?.configuration ?? '未指定'}</dd>
          </div>
          <div>
            <dt>位置分析状态</dt>
            <dd>{getCompletionLabel(selectedOccurrence?.status)}</dd>
          </div>
          <div>
            <dt>位置选择状态</dt>
            <dd>{getReachabilityLabel(selectedOccurrence?.selectionStatus)}</dd>
          </div>
          <div>
            <dt>发现时间</dt>
            <dd>{formatDateTime(detail.createdAt)}</dd>
          </div>
        </dl>
        {selectedReasonCodes.length ? (
          <div className={styles.findingReasonCodes}>
            <strong>位置说明</strong>
            <ul>
              {selectedReasonCodes.map((reasonCode) => (
                <li key={reasonCode}>{getReasonCodeLabel(reasonCode)}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </FindingFacts>
      <FindingRawData value={detail.evidence} />
    </article>
  )
}

export function FindingDetail({
  detail,
  loading,
  codeContextLoading,
  codeContextError,
  reportActions,
  showMigrationInputStatus = true
}: {
  detail?: FindingDetailData
  loading: boolean
  codeContextLoading?: boolean
  codeContextError?: boolean
  reportActions?: ReactNode
  showMigrationInputStatus?: boolean
}) {
  if (loading || !detail) {
    return <StageViewLoading description="正在加载 Finding 详情" />
  }

  return (
    <FindingWorkspace
      codeContextError={codeContextError}
      codeContextLoading={codeContextLoading}
      detail={detail}
      key={detail.id}
      reportActions={reportActions}
      showMigrationInputStatus={showMigrationInputStatus}
    />
  )
}
