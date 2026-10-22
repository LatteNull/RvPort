import { useCallback, useState } from 'react'
import { CodeOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Pagination, Spin } from 'antd'

import {
  getProjectEvaluationReportCodeFindings,
  getProjectEvaluationReportFileContext,
  getProjectEvaluationReportFindingTypes
} from '@/api/project/assessment-report'
import { readAllPages } from '@/api/readAllPages'
import { usePageBounds } from '@/components/BaseTable/hooks/usePageBounds'
import { useTableViewState } from '@/components/BaseTable/TableViewStateContext'
import ContentState from '@/components/ContentState'
import type {
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeModule
} from '@/types/project'

import { projectQueryKeys } from '../../../queryKeys'
import { reportFindingTitleText, reportRiskTag } from '../reportPresentation'
import { FindingTooltip, FindingTypeFilter } from './report-list-presentation'
import ReportSourceContextEditor from './ReportSourceContextEditor'

import styles from '../index.module.scss'

export default function ReportFileDetail({
  file,
  module,
  reportId
}: {
  file: ProjectEvaluationReportCodeFile
  module: ProjectEvaluationReportCodeModule
  reportId: string
}) {
  const [{ findingType, findingPage }, updateQuery] = useTableViewState<{
    findingType?: string
    findingPage: number
  }>(projectQueryKeys.evaluationReportCodeFindings(reportId, module.moduleKey, file.fileKey), {
    findingPage: 1
  })
  const setFindingType = (findingType?: string) =>
    updateQuery((current) => ({ ...current, findingType }))
  const setFindingPage = (findingPage: number) =>
    updateQuery((current) => ({ ...current, findingPage }))
  const [selectedFindingId, setSelectedFindingId] = useState<string>()
  const [activeFindingTooltip, setActiveFindingTooltip] = useState<string>()
  const [revealFindingKey, setRevealFindingKey] = useState(0)
  const handleFindingTooltipOpenChange = useCallback((tooltipId: string, open: boolean) => {
    setActiveFindingTooltip((current) => {
      if (open) return tooltipId
      return current === tooltipId ? undefined : current
    })
  }, [])
  const findingParams = {
    page: findingPage,
    pageSize: 20,
    sortBy: 'lineStart',
    sortDirection: 'asc' as const
  }
  const typesQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportFindingTypes(
      reportId,
      module.moduleKey,
      file.fileKey
    ),
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) =>
          getProjectEvaluationReportFindingTypes(reportId, module.moduleKey, file.fileKey, {
            page,
            pageSize,
            sortBy: 'findingCount',
            sortDirection: 'desc'
          }),
        { signal }
      )
  })
  const findingsQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportCodeFindings(
      reportId,
      module.moduleKey,
      file.fileKey,
      findingType,
      findingParams
    ),
    queryFn: () =>
      getProjectEvaluationReportCodeFindings(
        reportId,
        module.moduleKey,
        file.fileKey,
        findingType,
        findingParams
      )
  })
  const contextQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportFileContext(reportId, file.fileKey),
    queryFn: () => getProjectEvaluationReportFileContext(reportId, file.fileKey),
    retry: false
  })
  usePageBounds({
    page: findingPage,
    pageSize: 20,
    total: findingsQuery.data?.total,
    ready: findingsQuery.isSuccess && !findingsQuery.isFetching && !findingsQuery.isPlaceholderData,
    onCorrectPage: setFindingPage
  })
  const selectedFinding = findingsQuery.data?.items.find(
    (finding) => finding.id === selectedFindingId
  )
  const fileTypeOptions =
    typesQuery.data?.items.map((type) => ({
      count: type.findingCount,
      type: type.findingType
    })) ?? []

  return (
    <section className={styles.organizationSection}>
      <div className={styles.fileDetailHeader}>
        <div>
          <span>{module.moduleName || '未定位模块'}</span>
          <h3>{file.relativePath || '无法定位的文件'}</h3>
        </div>
        <div>
          {reportRiskTag(file.highestRisk)}
          <span>{file.findingCount} 处问题</span>
          <span>{file.findingTypeCount} 种类型</span>
        </div>
      </div>
      <div className={styles.fileTypeFilter}>
        {typesQuery.isLoading ? (
          <Spin size="small" />
        ) : typesQuery.isError ? (
          <div role="alert">
            问题类型加载失败{' '}
            <Button size="small" type="link" onClick={() => void typesQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : (
          <FindingTypeFilter
            ariaLabel="文件问题类型"
            findingCount={file.findingCount}
            options={fileTypeOptions}
            value={findingType}
            onChange={(value) => {
              setActiveFindingTooltip(undefined)
              setFindingType(value)
              setFindingPage(1)
              setSelectedFindingId(undefined)
            }}
          />
        )}
      </div>
      <div className={styles.fileWorkspace}>
        <div className={styles.findingPane} data-finding-pane>
          <div className={styles.paneHeading}>
            <strong>问题列表</strong>
            <span>{findingsQuery.data ? `${findingsQuery.data.total} 处` : '读取中'}</span>
          </div>
          {findingsQuery.isLoading ? (
            <div className={styles.paneLoading}>
              <Spin size="small" />
            </div>
          ) : findingsQuery.isError ? (
            <div className={styles.paneError} role="alert">
              问题列表加载失败{' '}
              <Button size="small" type="link" onClick={() => void findingsQuery.refetch()}>
                重试
              </Button>
            </div>
          ) : findingsQuery.data?.items.length ? (
            <>
              <div className={styles.findingList}>
                {findingsQuery.data.items.map((finding) => {
                  const selected = selectedFindingId === finding.id
                  const findingTitle = reportFindingTitleText(
                    finding.issueTitle,
                    finding.findingType
                  )
                  const evidenceText = finding.symbol?.trim()
                  const typeTooltipId = `${finding.id}:type`
                  const evidenceTooltipId = `${finding.id}:evidence`
                  const recommendationTooltipId = `${finding.id}:recommendation`
                  return (
                    <button
                      key={finding.id}
                      aria-expanded={selected}
                      className={selected ? styles.activeFinding : undefined}
                      type="button"
                      onClick={() => {
                        setActiveFindingTooltip(undefined)
                        setSelectedFindingId(finding.id)
                        setRevealFindingKey((current) => current + 1)
                      }}
                    >
                      <span className={styles.findingMeta}>
                        <span className={styles.findingIdentity}>
                          <span>
                            {finding.locationAvailable && finding.lineStart
                              ? `第 ${finding.lineStart} 行`
                              : '无法定位'}
                          </span>
                          <FindingTooltip
                            activeId={activeFindingTooltip}
                            id={typeTooltipId}
                            title={findingTitle}
                            onOpenChange={handleFindingTooltipOpenChange}
                          >
                            <span className={styles.findingType}>{findingTitle}</span>
                          </FindingTooltip>
                        </span>
                        {reportRiskTag(finding.riskLevel)}
                      </span>
                      {evidenceText ? (
                        <FindingTooltip
                          activeId={activeFindingTooltip}
                          disabled={selected}
                          id={evidenceTooltipId}
                          title={evidenceText}
                          onOpenChange={handleFindingTooltipOpenChange}
                        >
                          <code>{evidenceText}</code>
                        </FindingTooltip>
                      ) : null}
                      {finding.recommendation ? (
                        <FindingTooltip
                          activeId={activeFindingTooltip}
                          disabled={selected}
                          id={recommendationTooltipId}
                          title={finding.recommendation}
                          onOpenChange={handleFindingTooltipOpenChange}
                        >
                          <p>{finding.recommendation}</p>
                        </FindingTooltip>
                      ) : null}
                    </button>
                  )
                })}
              </div>
              {findingsQuery.data.total > 20 ? (
                <Pagination
                  current={findingPage}
                  pageSize={20}
                  showLessItems
                  size="small"
                  total={findingsQuery.data.total}
                  onChange={(nextPage) => {
                    setActiveFindingTooltip(undefined)
                    setFindingPage(nextPage)
                    setSelectedFindingId(undefined)
                  }}
                />
              ) : null}
            </>
          ) : (
            <ContentState description="暂无问题" compact />
          )}
        </div>
        <div className={styles.sourcePane}>
          <div className={styles.paneHeading}>
            <strong>联合源码上下文</strong>
            <div className={styles.paneHeadingActions}>
              {selectedFinding ? (
                <Button
                  size="small"
                  type="text"
                  onClick={() => {
                    setSelectedFindingId(undefined)
                    setRevealFindingKey((current) => current + 1)
                  }}
                >
                  返回初始位置
                </Button>
              ) : null}
              <span>
                {contextQuery.data?.totalLines ? `${contextQuery.data.totalLines} 行` : null}
              </span>
            </div>
          </div>
          {contextQuery.isLoading ? (
            <div className={styles.paneLoading}>
              <Spin size="small" />
            </div>
          ) : contextQuery.isError ? (
            <div className={styles.paneError} role="alert">
              源码上下文加载失败{' '}
              <Button size="small" type="link" onClick={() => void contextQuery.refetch()}>
                重试
              </Button>
            </div>
          ) : !contextQuery.data?.contextAvailable ? (
            <div className={styles.contextUnavailable}>
              <CodeOutlined />
              <strong>这份报告没有可用的源码上下文</strong>
              <span>{contextQuery.data?.unavailableReason ?? '未提供不可用原因'}</span>
            </div>
          ) : (
            <ReportSourceContextEditor
              key={`${reportId}:${file.fileKey}`}
              context={contextQuery.data}
              fileKey={file.fileKey}
              reportId={reportId}
              revealFindingKey={revealFindingKey}
              selectedFinding={selectedFinding}
            />
          )}
        </div>
      </div>
    </section>
  )
}
