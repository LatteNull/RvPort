import { useQuery } from '@tanstack/react-query'
import { Descriptions, Tag } from 'antd'

import { getProjectDependencyAnalysisResult } from '@/api/project/dependency-analysis'
import {
  getProjectKnowledgeBaseFinding,
  getProjectKnowledgeBaseFindingCodeContext
} from '@/api/project/knowledge-base'
import { getProjectMigrationInput } from '@/api/project/migration-input'
import CodeMirrorEditor from '@/components/CodeMirrorEditor'
import ContentState from '@/components/ContentState'

import { projectQueryKeys } from '../../../queryKeys'
import { DependencyResultDetailContent } from '../../components/DependencyResultDetail/index'
import { FindingDetail } from '../../components/FindingDetail/index'
import StageStateNotice from '../../components/StageStateNotice'

import styles from '../index.module.scss'

export default function ReportIssueDetail({ migrationInputId }: { migrationInputId: string }) {
  const inputQuery = useQuery({
    queryKey: projectQueryKeys.migrationInput(migrationInputId),
    queryFn: () => getProjectMigrationInput(migrationInputId)
  })
  const sourceType = inputQuery.data?.reference.sourceType
  const sourceRefId = inputQuery.data?.reference.sourceRefId
  const findingQuery = useQuery({
    queryKey: projectQueryKeys.knowledgeBaseFinding(sourceRefId),
    queryFn: () => getProjectKnowledgeBaseFinding(sourceRefId ?? ''),
    enabled: sourceType === 'KB_FINDING' && Boolean(sourceRefId)
  })
  const findingCodeContextQuery = useQuery({
    queryKey: projectQueryKeys.knowledgeBaseFindingCodeContext(sourceRefId),
    queryFn: () => getProjectKnowledgeBaseFindingCodeContext(sourceRefId ?? ''),
    enabled:
      sourceType === 'KB_FINDING' &&
      Boolean(sourceRefId) &&
      Boolean(findingQuery.data?.filePath && findingQuery.data.lineStart),
    retry: false
  })
  const dependencyQuery = useQuery({
    queryKey: projectQueryKeys.dependencyAnalysisResult(sourceRefId),
    queryFn: () => getProjectDependencyAnalysisResult(sourceRefId ?? ''),
    enabled: sourceType === 'DEPENDENCY_RESULT' && Boolean(sourceRefId)
  })

  if (inputQuery.isLoading) {
    return (
      <div className={styles.statePanel}>
        <ContentState kind="loading" description="正在加载问题详情" compact />
      </div>
    )
  }

  if (inputQuery.isError || !inputQuery.data) {
    return (
      <StageStateNotice
        description="无法解析该报告问题的来源，请重新加载。"
        embedded
        primaryAction={{ label: '重新加载', onClick: () => void inputQuery.refetch() }}
        title="报告问题详情加载失败"
        variant="request-error"
      />
    )
  }

  if (sourceType === 'KB_FINDING') {
    if (findingQuery.isError) {
      return (
        <StageStateNotice
          description="无法读取对应的知识库扫描问题，请重新加载。"
          embedded
          primaryAction={{ label: '重新加载', onClick: () => void findingQuery.refetch() }}
          title="知识库问题详情加载失败"
          variant="request-error"
        />
      )
    }
    return (
      <div className={styles.reportIssueDetail}>
        <Tag>报告问题 · 只读</Tag>
        <FindingDetail
          codeContextError={findingCodeContextQuery.isError}
          codeContextLoading={findingCodeContextQuery.isLoading}
          detail={
            findingQuery.data
              ? { ...findingQuery.data, codeContext: findingCodeContextQuery.data }
              : undefined
          }
          loading={findingQuery.isLoading}
          showMigrationInputStatus={false}
        />
      </div>
    )
  }

  if (sourceType === 'DEPENDENCY_RESULT') {
    if (dependencyQuery.isError) {
      return (
        <StageStateNotice
          description="无法读取对应的依赖分析问题，请重新加载。"
          embedded
          primaryAction={{ label: '重新加载', onClick: () => void dependencyQuery.refetch() }}
          title="依赖问题详情加载失败"
          variant="request-error"
        />
      )
    }
    return dependencyQuery.data ? (
      <div className={styles.reportIssueDetail}>
        <Tag>报告问题 · 只读</Tag>
        <DependencyResultDetailContent result={dependencyQuery.data} />
      </div>
    ) : (
      <div className={styles.statePanel}>
        <ContentState kind="loading" description="正在加载问题详情" compact />
      </div>
    )
  }

  return (
    <div className={styles.reportIssueDetail}>
      <Tag>报告问题 · 只读</Tag>
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="问题来源">{sourceType ?? '--'}</Descriptions.Item>
        <Descriptions.Item label="问题名称">
          {inputQuery.data.reference.issueTitle ?? '--'}
        </Descriptions.Item>
      </Descriptions>
      <section className={styles.genericSourceDetail}>
        <h3>来源数据</h3>
        <div className={styles.sourceDataViewport}>
          <CodeMirrorEditor
            ariaLabel="报告问题来源数据"
            height="100%"
            language="json"
            readOnly
            value={JSON.stringify(inputQuery.data.sourceDetail, null, 2)}
          />
        </div>
      </section>
    </div>
  )
}
