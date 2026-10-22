import { FileTextOutlined, RightOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Pagination, Tag } from 'antd'

import { getProjectEvaluationReportCodeFiles } from '@/api/project/assessment-report'
import { usePageBounds } from '@/components/BaseTable/hooks/usePageBounds'
import { useTableViewState } from '@/components/BaseTable/TableViewStateContext'
import ContentState from '@/components/ContentState'
import type {
  ProjectEvaluationReportCodeFile,
  ProjectEvaluationReportCodeModule
} from '@/types/project'

import { projectQueryKeys } from '../../../queryKeys'
import {
  reportConfidenceText,
  reportFindingTypeText,
  reportModuleBasisText,
  reportRiskTag
} from '../reportPresentation'
import { FindingTypeFilter, SummaryFact, TypeCounts } from './report-list-presentation'

import styles from '../index.module.scss'

const pageSize = 10

export default function ReportModuleDetail({
  module,
  reportId,
  onSelectFile
}: {
  module: ProjectEvaluationReportCodeModule
  reportId: string
  onSelectFile: (file: ProjectEvaluationReportCodeFile) => void
}) {
  const [{ findingType, page }, updateQuery] = useTableViewState<{
    findingType?: string
    page: number
  }>(projectQueryKeys.evaluationReportCodeFiles(reportId, module.moduleKey), { page: 1 })
  const setFindingType = (findingType?: string) =>
    updateQuery((current) => ({ ...current, findingType }))
  const setPage = (page: number) => updateQuery((current) => ({ ...current, page }))
  const params = {
    keyword: findingType,
    page,
    pageSize,
    sortBy: 'highestRisk',
    sortDirection: 'asc' as const
  }
  const filesQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportCodeFiles(reportId, module.moduleKey, params),
    queryFn: () => getProjectEvaluationReportCodeFiles(reportId, module.moduleKey, params)
  })
  usePageBounds({
    page,
    pageSize,
    total: filesQuery.data?.total,
    ready: filesQuery.isSuccess && !filesQuery.isFetching && !filesQuery.isPlaceholderData,
    onCorrectPage: setPage
  })
  const typeOptions = Object.entries(module.typeCounts)
    .sort(([, left], [, right]) => right - left)
    .map(([type, count]) => ({ count, type }))

  return (
    <section className={styles.organizationSection}>
      <div className={styles.moduleDetailHeader}>
        <div>
          <div className={styles.moduleTitleLine}>
            <h3>{module.moduleName || '未定位模块'}</h3>
            {reportRiskTag(module.highestRisk)}
          </div>
          <p>
            {reportModuleBasisText(module.basis)} · {reportConfidenceText(module.confidence)}
          </p>
          {module.relatedModuleKeys.length ? (
            <span>关联构建目标：{module.relatedModuleKeys.join('、')}</span>
          ) : null}
        </div>
        <div className={styles.moduleDetailFacts}>
          <SummaryFact label="影响文件" value={`${module.fileCount} 个`} />
          <SummaryFact label="代码问题" value={`${module.findingCount} 处`} />
          <SummaryFact label="问题类型" value={`${module.findingTypeCount} 种`} />
        </div>
      </div>
      <div className={styles.moduleTypeFilter}>
        <FindingTypeFilter
          ariaLabel="模块问题类型"
          findingCount={module.findingCount}
          options={typeOptions}
          value={findingType}
          onChange={(value) => {
            setFindingType(value)
            setPage(1)
          }}
        />
      </div>
      <div className={styles.sectionHeading}>
        <div>
          <h3>受影响文件</h3>
          <span>
            {findingType ? `当前只看${reportFindingTypeText(findingType)}` : '按风险优先排列'}
          </span>
        </div>
        <strong>{filesQuery.data ? `${filesQuery.data.total} 个文件` : '读取中'}</strong>
      </div>
      {filesQuery.isLoading ? (
        <div className={styles.organizationLoading}>
          <ContentState kind="loading" description="正在加载文件列表" compact />
        </div>
      ) : filesQuery.isError ? (
        <ContentState compact kind="error" description="文件列表加载失败">
          <Button type="primary" onClick={() => void filesQuery.refetch()}>
            重新加载
          </Button>
        </ContentState>
      ) : filesQuery.data?.items.length ? (
        <>
          <div className={styles.fileList}>
            {filesQuery.data.items.map((file) => (
              <button
                key={file.fileKey}
                className={styles.fileRow}
                type="button"
                onClick={() => onSelectFile(file)}
              >
                <FileTextOutlined />
                <div className={styles.fileMain}>
                  <strong>{file.relativePath || '无法定位的文件'}</strong>
                  <TypeCounts counts={file.typeCounts} limit={4} />
                </div>
                <div className={styles.fileStats}>
                  {reportRiskTag(file.highestRisk)}
                  <span>{file.findingCount} 处问题</span>
                  <span>{file.findingTypeCount} 种类型</span>
                  {!file.contextAvailable ? <Tag>无源码上下文</Tag> : null}
                </div>
                <span className={styles.rowAction}>
                  查看文件 <RightOutlined />
                </span>
              </button>
            ))}
          </div>
          {filesQuery.data.total > pageSize ? (
            <Pagination
              align="end"
              current={page}
              pageSize={pageSize}
              showLessItems
              size="small"
              total={filesQuery.data.total}
              onChange={setPage}
            />
          ) : null}
        </>
      ) : (
        <div className={styles.organizationEmpty}>
          <ContentState description="当前类型没有对应文件" compact />
        </div>
      )}
    </section>
  )
}
