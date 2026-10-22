import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Pagination } from 'antd'

import { usePageBounds } from '@/components/BaseTable/hooks/usePageBounds'
import { useTableViewState } from '@/components/BaseTable/TableViewStateContext'
import ContentState from '@/components/ContentState'
import type { ProjectEvaluationReportInput } from '@/types/project'

import { projectQueryKeys } from '../../../queryKeys'
import { getAllEvaluationReportInputs } from '../queries'
import { reportRiskTag, reportSourceTypeText } from '../reportPresentation'

import styles from '../index.module.scss'

const pageSize = 10

export default function ReportDependencyList({
  reportId,
  onOpenIssue
}: {
  reportId: string
  onOpenIssue: (migrationInputId: string) => void
}) {
  const [{ page }, updateQuery] = useTableViewState(
    projectQueryKeys.evaluationReportDependencyListState(reportId),
    { page: 1 }
  )
  const setPage = (page: number) => updateQuery(() => ({ page }))
  const inputsQuery = useQuery({
    queryKey: projectQueryKeys.evaluationReportInputs(reportId),
    queryFn: ({ signal }) => getAllEvaluationReportInputs(reportId, signal)
  })
  const inputs = useMemo(
    () =>
      (inputsQuery.data ?? []).filter(
        (input) => input.inputSnapshot.sourceType === 'DEPENDENCY_RESULT'
      ),
    [inputsQuery.data]
  )
  const visibleInputs = inputs.slice((page - 1) * pageSize, page * pageSize)
  usePageBounds({
    page,
    pageSize,
    total: inputs.length,
    ready: inputsQuery.isSuccess && !inputsQuery.isFetching && !inputsQuery.isPlaceholderData,
    onCorrectPage: setPage
  })

  return (
    <section className={styles.organizationSection}>
      {inputsQuery.isLoading ? (
        <div className={styles.organizationLoading}>
          <ContentState kind="loading" description="正在加载依赖清单" compact />
        </div>
      ) : inputsQuery.isError ? (
        <ContentState compact kind="error" description="依赖清单加载失败">
          <Button type="primary" onClick={() => void inputsQuery.refetch()}>
            重新加载
          </Button>
        </ContentState>
      ) : visibleInputs.length ? (
        <>
          <div className={styles.evidenceList}>
            {visibleInputs.map((input: ProjectEvaluationReportInput) => (
              <button key={input.id} type="button" onClick={() => onOpenIssue(input.inputId)}>
                <span>{reportRiskTag(input.inputSnapshot.detectedLevel)}</span>
                <div>
                  <strong>{input.inputSnapshot.issueTitle || '未命名问题'}</strong>
                  <span>{input.inputSnapshot.locationLabel || '暂无定位信息'}</span>
                </div>
                <small>{reportSourceTypeText(input.inputSnapshot.sourceType)}</small>
              </button>
            ))}
          </div>
          {inputs.length > pageSize ? (
            <Pagination
              align="end"
              current={page}
              pageSize={pageSize}
              showLessItems
              size="small"
              total={inputs.length}
              onChange={setPage}
            />
          ) : null}
        </>
      ) : (
        <div className={styles.organizationEmpty}>
          <ContentState description="这份报告没有依赖分析结果" compact />
        </div>
      )}
    </section>
  )
}
