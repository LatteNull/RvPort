import { Fragment, lazy, Suspense } from 'react'
import { Flex, Tag } from 'antd'

import type {
  ProjectDependencyAnalysis,
  ProjectDependencyAnalysisResult
} from '@/types/project/dependency-analysis'

import { projectQueryKeys } from '../../../queryKeys'
import {
  MigrationInputDetailFooter,
  MigrationInputStatusTag
} from '../../components/MigrationInputActions'
import StageStateNotice from '../../components/StageStateNotice'
import StageViewLoading from '../../components/StageViewLoading'
import { isCurrentAnalysisContext } from './presentation'

import styles from '../index.module.scss'

const DependencyResultDetailContent = lazy(() =>
  import('../../components/DependencyResultDetail/index').then((module) => ({
    default: module.DependencyResultDetailContent
  }))
)

export function ResultDetail({
  isError,
  onRefetch,
  readOnly,
  result
}: {
  isError: boolean
  onRefetch: () => void
  readOnly: boolean
  result?: ProjectDependencyAnalysisResult
}) {
  return (
    <div className={styles.content}>
      {isError ? (
        <StageStateNotice
          description="无法读取该依赖结果，请重新加载。"
          embedded
          primaryAction={{ label: '重新加载', onClick: onRefetch }}
          title="依赖结果详情加载失败"
          variant="request-error"
        />
      ) : result ? (
        <Fragment>
          {readOnly ? (
            <Flex align="center" className={styles.detailStatusRow} gap={8} justify="flex-end">
              <Tag>历史上下文，只读</Tag>
              <MigrationInputStatusTag status={result.migrationInputStatus} />
            </Flex>
          ) : null}
          <Suspense fallback={<StageViewLoading description="正在加载依赖详情" variant="detail" />}>
            <DependencyResultDetailContent result={result} />
          </Suspense>
        </Fragment>
      ) : null}
    </div>
  )
}

export function DependencyResultFooter({
  analysis,
  projectId,
  result
}: {
  analysis: ProjectDependencyAnalysis
  projectId: string
  result?: ProjectDependencyAnalysisResult
}) {
  if (!result || !isCurrentAnalysisContext(analysis)) return null

  return (
    <MigrationInputDetailFooter
      invalidateQueryKeys={[
        projectQueryKeys.dependencyAnalysisResult(result.id),
        projectQueryKeys.dependencyAnalysisResults(analysis.id)
      ]}
      migrationInputRefId={result.migrationInputRefId}
      projectId={projectId}
      sourceRefId={result.id}
      sourceRevisionId={analysis.sourceRevisionId}
      sourceType="DEPENDENCY_RESULT"
      status={result.migrationInputStatus}
    />
  )
}
