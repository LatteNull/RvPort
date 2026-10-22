import { lazy, Suspense } from 'react'
import { ReloadOutlined } from '@ant-design/icons'
import { Button, Flex } from 'antd'

import { getProjectArchiveDownloadUrl } from '@/api/project/archive'
import ContentState from '@/components/ContentState'

import RecordViewTitle from '../components/RecordViewTitle'
import StageOverview from '../components/StageOverview'
import type { StageStateAction } from '../components/StageStateNotice'
import StageSurface from '../components/StageSurface'
import StageViewLoading from '../components/StageViewLoading'
import { getStageDrawerWidth } from '../drawerWidth'
import { presentPrerequisites } from '../stagePresentation'
import type { StageDrawerProps } from '../types'
import { ArchiveItems } from './components/ArchiveItems'
import { ArchiveSummary } from './components/ArchiveSummary'
import { useArchiveDrawer } from './useArchiveDrawer'

import styles from './index.module.scss'

const ArchiveHistory = lazy(() =>
  import('./components/ArchiveHistory').then((module) => ({ default: module.ArchiveHistory }))
)

export default function Archive({
  projectId,
  visible,
  stage,
  onClose,
  onStageChange
}: StageDrawerProps) {
  const drawer = useArchiveDrawer(projectId, visible)
  const isDetail = drawer.view.type === 'detail'
  const archive = isDetail ? drawer.archive : drawer.latestArchive
  const back =
    drawer.view.type === 'detail' && drawer.view.returnTo === 'history'
      ? drawer.showHistory
      : drawer.showOverview
  const createAction: StageStateAction = {
    label: '创建项目归档',
    loading: drawer.isCreating,
    disabled: drawer.isError,
    confirmation: {
      title: '确认创建项目归档？',
      description: '将基于当前激活的源码版本创建不可变的项目归档快照。',
      okText: '确认创建',
      cancelText: '取消'
    },
    onClick: () => void drawer.create()
  }
  const result = archive ? (
    <div className={styles.content}>
      <ArchiveSummary
        archive={archive}
        actions={
          archive.status === 'SUCCEEDED' && archive.storedArtifactId ? (
            <Button
              type={isDetail ? 'link' : 'primary'}
              onClick={() =>
                window.open(
                  getProjectArchiveDownloadUrl(archive.id),
                  '_blank',
                  'noopener,noreferrer'
                )
              }
            >
              下载归档包
            </Button>
          ) : undefined
        }
      />
      {!isDetail && archive.status === 'SUCCEEDED' && !archive.storedArtifactId ? (
        <StageOverview
          label="归档包生成"
          request={{
            loading: false,
            error: drawer.isError,
            hasData: true,
            reload: () => void drawer.refreshCurrent()
          }}
          gate={{ ready: drawer.canCreate, prerequisites: [] }}
          result={{ hasResult: false, freshness: 'EMPTY' }}
          operation={{ start: { ...createAction, label: '重新生成归档包' } }}
        />
      ) : null}
      <section className={styles.sectionBlock}>
        <div className={styles.sectionHeading}>
          <h3>交付内容</h3>
          <p>查看本次归档收录的阶段产物，并按需下载单项文件。</p>
        </div>
        <ArchiveItems archiveId={archive.id} items={archive.items} />
      </section>
    </div>
  ) : null
  return (
    <StageSurface
      visible={visible}
      onClose={() => {
        drawer.close()
        onClose()
      }}
      afterOpenChange={(open) => {
        if (!open) drawer.finishClose()
      }}
      size={getStageDrawerWidth('archive')}
      onHistory={drawer.view.type === 'overview' ? drawer.showHistory : undefined}
      panelTitleVisible={drawer.view.type !== 'overview'}
      panelScrollKey={`${drawer.view.type}:${isDetail ? (archive?.id ?? '') : ''}`}
      title={
        drawer.view.type === 'history' ? (
          <RecordViewTitle backLabel="返回当前归档" title="归档记录" onBack={drawer.showOverview} />
        ) : isDetail ? (
          <RecordViewTitle
            backLabel={
              drawer.view.type === 'detail' && drawer.view.returnTo === 'history'
                ? '返回归档记录'
                : '返回当前归档'
            }
            title="归档记录概览"
            onBack={back}
          />
        ) : (
          (stage?.title ?? '归档')
        )
      }
      extra={
        !isDetail ? (
          <Button
            type="text"
            aria-label={drawer.view.type === 'history' ? '刷新归档记录' : '刷新归档信息'}
            icon={<ReloadOutlined />}
            onClick={() =>
              void (drawer.view.type === 'history'
                ? drawer.refreshHistory()
                : drawer.refreshCurrent())
            }
          />
        ) : undefined
      }
    >
      {isDetail ? (
        drawer.isDetailLoading ? (
          <StageViewLoading description="正在读取归档记录" variant="detail" />
        ) : drawer.isDetailError ? (
          <ContentState kind="error" description="归档详情加载失败">
            <Flex gap={12}>
              <Button onClick={back}>返回</Button>
              <Button type="primary" onClick={() => void drawer.refetchDetail()}>
                重新加载
              </Button>
            </Flex>
          </ContentState>
        ) : (
          result
        )
      ) : drawer.view.type === 'history' ? (
        <Suspense fallback={<StageViewLoading description="正在加载归档记录" variant="table" />}>
          <ArchiveHistory
            projectId={projectId ?? ''}
            onOpen={(id) => drawer.showDetail(id, 'history')}
          />
        </Suspense>
      ) : (
        <StageOverview
          label="项目归档"
          request={{
            loading: drawer.isLoading,
            error: drawer.isError,
            hasData: Boolean(drawer.readinessQuery.data && drawer.latestQuery.data),
            reload: () => void drawer.refreshCurrent()
          }}

          gate={{
            ready: drawer.canCreate,
            prerequisites: presentPrerequisites(drawer.prerequisites, onStageChange)
          }}
          result={{
            record: drawer.latestArchive ?? undefined,
            execution: drawer.latestQuery.data?.execution,
            status: drawer.latestQuery.data?.execution?.status ?? archive?.status,
            freshness: drawer.freshness,
            hasResult: Boolean(archive)
          }}
          operation={{ submitting: drawer.isCreating || drawer.submitted, start: createAction }}
        >
          {result}
        </StageOverview>
      )}
    </StageSurface>
  )
}
