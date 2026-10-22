import { RightOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Pagination, Select } from 'antd'

import { getProjectEvaluationReportCodeModules } from '@/api/project/assessment-report'
import { usePageBounds } from '@/components/BaseTable/hooks/usePageBounds'
import { useTableViewState } from '@/components/BaseTable/TableViewStateContext'
import ContentState from '@/components/ContentState'
import DebouncedSearchInput from '@/components/DebouncedSearchInput'
import type { ProjectEvaluationReportCodeModule } from '@/types/project'

import { projectQueryKeys } from '../../../queryKeys'
import {
  reportConfidenceText,
  reportModuleBasisText,
  reportRiskTag,
  reportRiskText
} from '../reportPresentation'
import { TypeCounts } from './report-list-presentation'

import styles from '../index.module.scss'

const pageSize = 10

export default function ReportModuleIndex({
  reportId,
  onSelect
}: {
  reportId: string
  onSelect: (module: ProjectEvaluationReportCodeModule) => void
}) {
  const [{ keyword, riskLevel, page, searchResetVersion = 0 }, updateQuery] = useTableViewState<{
    keyword: string
    riskLevel?: string
    page: number
    searchResetVersion: number
  }>(projectQueryKeys.evaluationReportCodeModules(reportId), {
    keyword: '',
    page: 1,
    searchResetVersion: 0
  })
  const setKeyword = (keyword: string) => updateQuery((current) => ({ ...current, keyword }))
  const setRiskLevel = (riskLevel?: string) => updateQuery((current) => ({ ...current, riskLevel }))
  const setPage = (page: number) => updateQuery((current) => ({ ...current, page }))
  const params = {
    keyword: keyword || undefined,
    page,
    pageSize,
    riskLevel,
    sortBy: 'highestRisk',
    sortDirection: 'asc' as const
  }
  const modulesQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportCodeModules(reportId, params),
    queryFn: () => getProjectEvaluationReportCodeModules(reportId, params),
    // Keep clickable rows only within this report, never across regenerated reports.
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === reportId ? previousData : undefined
  })
  usePageBounds({
    page,
    pageSize,
    total: modulesQuery.data?.total,
    ready: modulesQuery.isSuccess && !modulesQuery.isFetching && !modulesQuery.isPlaceholderData,
    onCorrectPage: setPage
  })
  const hasFilters = Boolean(keyword || riskLevel)
  const clearFilters = () => {
    updateQuery((current) => ({
      keyword: '',
      riskLevel: undefined,
      page: 1,
      searchResetVersion: (current.searchResetVersion ?? 0) + 1
    }))
  }

  return (
    <section className={styles.organizationSection}>
      <div className={styles.sectionHeading}>
        <div>
          <h3>代码模块</h3>
          <span>先定位风险集中的模块，再进入具体文件</span>
        </div>
        <strong>{modulesQuery.data ? `${modulesQuery.data.total} 个模块` : '读取中'}</strong>
      </div>
      <div className={styles.organizationToolbar}>
        <DebouncedSearchInput
          aria-label="搜索模块、文件或问题"
          draftStateKey={projectQueryKeys.evaluationReportModuleSearchDraft(reportId)}
          resetKey={searchResetVersion}
          placeholder="搜索模块、文件或问题"
          value={keyword}
          onSearch={(value) => {
            setPage(1)
            setKeyword(value)
          }}
        />
        <Select
          aria-label="模块风险等级"
          allowClear
          options={['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map((value) => ({
            label: reportRiskText(value),
            value
          }))}
          placeholder="全部风险"
          value={riskLevel}
          onChange={(value) => {
            setPage(1)
            setRiskLevel(value)
          }}
        />
      </div>
      {modulesQuery.isLoading ? (
        <div className={styles.organizationLoading}>
          <ContentState kind="loading" description="正在加载模块信息" compact />
        </div>
      ) : modulesQuery.isError ? (
        <ContentState compact kind="error" description="模块信息加载失败">
          <Button type="primary" onClick={() => void modulesQuery.refetch()}>
            重新加载
          </Button>
        </ContentState>
      ) : modulesQuery.data?.items.length ? (
        <>
          <div className={styles.moduleList}>
            {modulesQuery.data.items.map((module) => (
              <button
                key={module.moduleKey}
                className={styles.moduleRow}
                type="button"
                onClick={() => onSelect(module)}
              >
                <div className={styles.moduleMain}>
                  <div className={styles.moduleTitleLine}>
                    <strong>{module.moduleName || '未定位模块'}</strong>
                    {reportRiskTag(module.highestRisk)}
                  </div>
                  <div className={styles.moduleMetaLine}>
                    <span>
                      {reportModuleBasisText(module.basis)} ·{' '}
                      {reportConfidenceText(module.confidence)}
                    </span>
                    <TypeCounts counts={module.typeCounts} limit={4} />
                  </div>
                </div>
                <div className={styles.moduleStats}>
                  <span className={styles.primaryModuleStat}>
                    <strong>{module.findingCount}</strong>
                    <small>处代码问题</small>
                  </span>
                  <span>
                    <strong>{module.fileCount}</strong>
                    <small>个影响文件</small>
                  </span>
                </div>
                <span className={styles.rowAction}>
                  查看模块 <RightOutlined />
                </span>
              </button>
            ))}
          </div>
          {modulesQuery.data.total > pageSize ? (
            <Pagination
              align="end"
              current={page}
              pageSize={pageSize}
              showLessItems
              size="small"
              total={modulesQuery.data.total}
              onChange={setPage}
            />
          ) : null}
        </>
      ) : (
        <div className={styles.organizationEmpty}>
          <ContentState
            kind={hasFilters ? 'filtered' : 'empty'}
            description={hasFilters ? '没有匹配的代码模块' : '暂无代码模块'}
            compact
          >
            {hasFilters ? (
              <Button size="small" onClick={clearFilters}>
                清除筛选
              </Button>
            ) : null}
          </ContentState>
        </div>
      )}
    </section>
  )
}
