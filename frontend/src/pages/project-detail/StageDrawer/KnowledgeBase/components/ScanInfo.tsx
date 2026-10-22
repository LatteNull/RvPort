import { DownloadOutlined, FileTextOutlined, ToolOutlined } from '@ant-design/icons'
import { Button, Tag, Tooltip } from 'antd'

import { getProjectKnowledgeBaseScanArtifactDownloadUrl } from '@/api/project/knowledge-base'
import ContentState from '@/components/ContentState'
import type { PageResponse } from '@/types'
import type {
  ProjectKnowledgeBaseScan,
  ProjectKnowledgeBaseScanArtifact
} from '@/types/project/knowledge-base'
import { formatDateTime, formatDisplayValue } from '@/utils/display'

import { asRecord } from '../../components/FindingDetail/presentation'
import StageStateNotice from '../../components/StageStateNotice'
import StageViewLoading from '../../components/StageViewLoading'
import { getExecutionStatusText } from '../../utils'
import {
  backendPendingText,
  formatFileSize,
  getKnowledgeBaseOverview,
  scanArtifactLabels
} from '../presentation'

import styles from '../index.module.scss'

export function ScanInfo({
  artifacts,
  error,
  loading,
  scan,
  onRetry
}: {
  artifacts?: PageResponse<ProjectKnowledgeBaseScanArtifact>
  error: boolean
  loading: boolean
  scan?: ProjectKnowledgeBaseScan
  onRetry: () => void
}) {
  if (loading) {
    return <StageViewLoading description="正在加载扫描信息" />
  }

  if (error || !scan) {
    return (
      <StageStateNotice
        description="无法读取本次扫描的执行信息与产物，请重新加载。"
        embedded
        primaryAction={{ label: '重新加载', onClick: onRetry }}
        title="扫描信息加载失败"
        variant="request-error"
      />
    )
  }

  const paths = scan.scope.paths.length ? scan.scope.paths.join(', ') : '全部路径'
  const scanner = asRecord(scan.summary.scan)
  const tool = asRecord(scanner.tool ?? scan.summary.tool)
  const scannerScope = asRecord(scanner.scope)
  const knowledgeSources = Array.isArray(scanner.knowledgeSources)
    ? scanner.knowledgeSources.map(asRecord)
    : []
  const diagnostics = Array.isArray(scan.summary.diagnostics)
    ? scan.summary.diagnostics.map(asRecord)
    : []
  const overview = getKnowledgeBaseOverview(scan.summary)

  return (
    <div className={styles.scanInfo}>
      <section className={styles.scanInfoHeader}>
        <div>
          <span>扫描 ID</span>
          <strong>{scan.id}</strong>
        </div>
        <Tag color={scan.status === 'SUCCEEDED' ? 'success' : 'processing'}>
          {getExecutionStatusText(scan.status)}
        </Tag>
      </section>
      <div className={styles.scanInfoSections}>
        <section className={styles.scanInfoPanel}>
          <h3>执行信息</h3>
          <div className={styles.scanInfoList}>
            <div>
              <span>任务 ID</span>
              <strong>{formatDisplayValue(scan.taskId)}</strong>
            </div>
            <div>
              <span>源码版本</span>
              <strong>{formatDisplayValue(scan.sourceRevisionId)}</strong>
            </div>
            <div>
              <span>知识库版本</span>
              <strong>{formatDisplayValue(scan.kbVersion)}</strong>
            </div>
            <div>
              <span>扫描模式</span>
              <strong>{formatDisplayValue(scan.scope.mode)}</strong>
            </div>
            <div>
              <span>开始时间</span>
              <strong>{formatDateTime(scan.startedAt)}</strong>
            </div>
            <div>
              <span>完成时间</span>
              <strong>{formatDateTime(scan.finishedAt)}</strong>
            </div>
          </div>
        </section>
        <section className={styles.scanInfoPanel}>
          <h3>
            <ToolOutlined />
            规则与扫描器
          </h3>
          <div className={styles.scanInfoList}>
            <div>
              <span>扫描器</span>
              <strong>{formatDisplayValue(tool.name)}</strong>
            </div>
            <div>
              <span>扫描器版本</span>
              <strong>{formatDisplayValue(tool.version)}</strong>
            </div>
            <div>
              <span>结果 Schema</span>
              <strong>{formatDisplayValue(scan.summary.schemaVersion)}</strong>
            </div>
            <div>
              <span>目标架构</span>
              <strong>{formatDisplayValue(scannerScope.targetArchitecture)}</strong>
            </div>
            <div>
              <span>分析方式</span>
              <strong>
                {scannerScope.staticAnalysisOnly === true ? '仅静态分析' : backendPendingText}
              </strong>
            </div>
          </div>
        </section>
      </div>
      <section className={`${styles.scanInfoPanel} ${styles.scanScopePanel}`}>
        <h3>扫描范围</h3>
        <p>{paths}</p>
        <p className={styles.staticAnalysisNotice}>
          当前结果尚未执行真实编译、链接或测试，不能单独作为迁移完成依据。
        </p>
      </section>
      <section className={styles.scanInfoPanel}>
        <h3>知识来源</h3>
        {knowledgeSources.length ? (
          <div className={styles.knowledgeSourceList}>
            {knowledgeSources.map((source, index) => (
              <div key={String(source.id ?? index)}>
                <strong>{formatDisplayValue(source.id)}</strong>
                <span>{formatDisplayValue(source.kind)}</span>
                <small>{formatDisplayValue(source.sha256)}</small>
              </div>
            ))}
          </div>
        ) : (
          <span className={styles.backendPending}>{backendPendingText}</span>
        )}
      </section>
      <section className={styles.scanInfoPanel}>
        <h3>扫描产出</h3>
        <div className={styles.scanOutputList}>
          {overview.outputCounts.map((item) => (
            <div key={item.key}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.scanInfoPanel}>
        <h3>扫描诊断</h3>
        {diagnostics.length ? (
          <div className={styles.diagnosticList}>
            {diagnostics.map((diagnostic, index) => (
              <div key={String(diagnostic.id ?? index)}>
                <Tag>{formatDisplayValue(diagnostic.severity)}</Tag>
                <div>
                  <strong>{formatDisplayValue(diagnostic.code)}</strong>
                  <span>{formatDisplayValue(diagnostic.stage)}</span>
                </div>
                <small>{formatDisplayValue(diagnostic.status)}</small>
              </div>
            ))}
          </div>
        ) : (
          <span>没有结构化诊断</span>
        )}
      </section>
      <section className={styles.scanArtifactsPanel}>
        <div className={styles.scanArtifactsHeading}>
          <h3>
            <FileTextOutlined />
            扫描产物
          </h3>
          <span>{artifacts?.total ?? 0}</span>
        </div>
        {artifacts?.items.length ? (
          <div className={styles.scanArtifactList}>
            {artifacts.items.map((artifact) => (
              <div key={artifact.id}>
                <div>
                  <strong>
                    {scanArtifactLabels[artifact.artifactType] ?? artifact.artifactType}
                  </strong>
                  <span>{formatDisplayValue(artifact.schemaVersion)}</span>
                </div>
                <span>{formatFileSize(artifact.sizeBytes)}</span>
                <span>{formatDisplayValue(artifact.sha256)}</span>
                <span>{formatDateTime(artifact.createdAt)}</span>
                <Tooltip title="下载产物">
                  <Button
                    aria-label={`下载 ${scanArtifactLabels[artifact.artifactType] ?? artifact.artifactType}`}
                    icon={<DownloadOutlined />}
                    type="text"
                    onClick={() =>
                      window.open(
                        getProjectKnowledgeBaseScanArtifactDownloadUrl(scan.id, artifact.id),
                        '_blank',
                        'noopener,noreferrer'
                      )
                    }
                  />
                </Tooltip>
              </div>
            ))}
          </div>
        ) : (
          <ContentState description="暂无扫描产物" compact />
        )}
      </section>
    </div>
  )
}
