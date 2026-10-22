import { Fragment, lazy, Suspense, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { ReloadOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Input, Segmented, Select } from 'antd'

import ContentState from '@/components/ContentState'
import type { ProjectListItem, ProjectStage } from '@/types/project'

import type { CreateProjectAction } from './components/CreateProjectModal'
import ProjectCard, { ProjectCardSkeleton } from './components/ProjectCard'
import { type ProjectListFilters, PROJECTS_QUERY_KEY, useProjectList } from './useProjectList'

import styles from './home.module.scss'

const SKELETON_CARD_COUNT = 10
const CreateProjectModal = lazy(() => import('./components/CreateProjectModal'))

const projectStatusOptions: { label: string; value: 'ACTIVE' | 'ALL' | 'ARCHIVED' }[] = [
  { label: '全部', value: 'ALL' },
  { label: '进行中', value: 'ACTIVE' },
  { label: '已归档', value: 'ARCHIVED' }
]

const projectStageOptions: { label: string; value: ProjectStage }[] = [
  { label: '项目创建', value: 'PROJECT_CREATED' },
  { label: '源码已导入', value: 'SOURCE_IMPORTED' },
  { label: '环境已配置', value: 'ENV_CONFIGURED' },
  { label: '扫描中', value: 'SCANNING' },
  { label: '报告已生成', value: 'REPORT_GENERATED' },
  { label: '等待修复', value: 'WAITING_FIX' },
  { label: '构建通过', value: 'BUILD_PASSED' },
  { label: '构建失败', value: 'BUILD_FAILED' },
  { label: '测试通过', value: 'TEST_PASSED' },
  { label: '测试失败', value: 'TEST_FAILED' },
  { label: '已归档', value: 'ARCHIVED' }
]

function ProjectSkeletonList() {
  return (
    <div className={styles.grid} aria-label="项目列表加载中">
      {Array.from({ length: SKELETON_CARD_COUNT }).map((_, index) => (
        <ProjectCardSkeleton key={index} />
      ))}
    </div>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const listTopRef = useRef<HTMLDivElement>(null)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [keywordInput, setKeywordInput] = useState('')
  const [filters, setFilters] = useState<ProjectListFilters>({})
  const {
    isError,
    isFetchNextPageError,
    isFetchingNextPage,
    isLoading,
    fetchNextPage,
    hasNextPage,
    projects,
    refetch,
    total
  } = useProjectList(filters)
  const hasActiveFilters = Boolean(filters.keyword || filters.stage || filters.status)

  const updateFilters = (nextFilters: ProjectListFilters) => {
    setFilters(nextFilters)
    listTopRef.current?.scrollIntoView({ block: 'start' })
  }

  const clearFilters = () => {
    setKeywordInput('')
    updateFilters({})
  }

  const handleProjectCreated = (project: ProjectListItem, action: CreateProjectAction) => {
    setCreateModalVisible(false)
    void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY })

    void navigate(
      action === 'configure-environment'
        ? `/projects/${project.id}/steps/env`
        : `/projects/${project.id}/workflow`
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h2 className={styles.title}>项目列表</h2>
          <p className={styles.description}>创建项目或进入已有迁移流水线</p>
        </div>
        <Button
          type="primary"
          className={styles.createButton}
          onClick={() => setCreateModalVisible(true)}
        >
          + 新建
        </Button>
      </header>

      <section className={styles.filterBar} aria-label="项目筛选">
        <Input.Search
          allowClear
          className={styles.keywordSearch}
          enterButton="搜索"
          placeholder="搜索项目名称或描述"
          value={keywordInput}
          onChange={(event) => setKeywordInput(event.target.value)}
          onSearch={(keyword) => updateFilters({ ...filters, keyword: keyword.trim() })}
        />
        <div className={styles.quickFilters}>
          <span className={styles.filterLabel}>状态</span>
          <Segmented
            aria-label="项目状态"
            className={styles.statusFilter}
            options={projectStatusOptions}
            value={filters.status ?? 'ALL'}
            onChange={(status) =>
              updateFilters({
                ...filters,
                status: status === 'ALL' ? undefined : (status as 'ACTIVE' | 'ARCHIVED')
              })
            }
          />
          <Select
            allowClear
            aria-label="流程阶段"
            className={styles.stageFilter}
            options={projectStageOptions}
            placeholder="全部流程阶段"
            value={filters.stage}
            onChange={(stage) => updateFilters({ ...filters, stage })}
          />
          {hasActiveFilters && (
            <Button className={styles.clearFilters} type="link" onClick={clearFilters}>
              重置筛选
            </Button>
          )}
        </div>
      </section>

      <div ref={listTopRef} className={styles.listSummary} aria-live="polite">
        <span>已加载 {projects.length} 个</span>
        <span>共 {total} 个项目</span>
      </div>

      {isLoading && <ProjectSkeletonList />}

      {isError && projects.length === 0 && (
        <div className={styles.statePanel}>
          <ContentState kind="error" description="项目列表加载失败，请稍后重试">
            <Button type="primary" onClick={() => void refetch()}>
              重试
            </Button>
          </ContentState>
        </div>
      )}

      {!isLoading && !isError && projects.length === 0 && (
        <div className={styles.statePanel}>
          <ContentState
            kind={hasActiveFilters ? 'filtered' : 'empty'}
            description={
              hasActiveFilters ? '没有符合筛选条件的项目' : '暂无项目，点击新建项目开始创建迁移项目'
            }
          >
            {hasActiveFilters ? <Button onClick={clearFilters}>清空筛选</Button> : null}
          </ContentState>
        </div>
      )}

      {!isLoading && projects.length > 0 && (
        <Fragment>
          <div className={styles.grid}>
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
          <div className={styles.loadMore} aria-live="polite">
            {isFetchNextPageError && (
              <div className={styles.loadMoreError}>
                <div>
                  <strong>下一批项目暂时没有加载成功</strong>
                  <span>当前已显示的 {projects.length} 个项目仍可正常使用</span>
                </div>
                <Button
                  type="primary"
                  aria-label="重试"
                  icon={<ReloadOutlined />}
                  onClick={() => void fetchNextPage()}
                >
                  重试
                </Button>
              </div>
            )}
            {hasNextPage && !isFetchNextPageError && (
              <div className={styles.loadMoreRail}>
                <button
                  aria-busy={isFetchingNextPage}
                  aria-label={isFetchingNextPage ? '正在加载' : '继续加载'}
                  className={styles.loadMoreButton}
                  disabled={isFetchingNextPage}
                  onClick={() => void fetchNextPage()}
                  type="button"
                >
                  继续加载
                </button>
              </div>
            )}
            {!hasNextPage && (
              <div className={styles.loadComplete}>
                <span>暂无更多数据</span>
              </div>
            )}
          </div>
        </Fragment>
      )}

      {createModalVisible ? (
        <Suspense fallback={null}>
          <CreateProjectModal
            visible
            onCancel={() => setCreateModalVisible(false)}
            onCreated={handleProjectCreated}
          />
        </Suspense>
      ) : null}
    </div>
  )
}
