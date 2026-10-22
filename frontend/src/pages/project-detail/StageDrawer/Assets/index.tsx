import { ReloadOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

import ContentState from '@/components/ContentState'

import StageSurface from '../components/StageSurface'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import { AssetsOverview } from './components/content'
import { AssetsTitle } from './components/drawer-chrome'
import { useAssetsDrawer } from './useAssetsDrawer'

import styles from './index.module.scss'

export default function Assets({
  projectId,
  visible,
  stage,
  onClose,
  onDirtyChange
}: StageDrawerProps) {
  const drawer = useAssetsDrawer(projectId, visible, onDirtyChange)

  return (
    <StageSurface
      afterOpenChange={(open) => {
        if (!open) drawer.resetSourceInput()
      }}
      extra={
        <Tooltip title="刷新">
          <Button
            aria-label="刷新"
            icon={<ReloadOutlined />}
            loading={drawer.isFetching}
            type="text"
            onClick={() => void drawer.refetch()}
          />
        </Tooltip>
      }
      loading={drawer.isLoading}
      size={getStageDrawerWidth('assets')}
      title={<AssetsTitle stage={stage} />}
      visible={visible}
      onClose={onClose}
    >
      {drawer.isError ? (
        <div className={styles.statePanel}>
          <ContentState kind="error" description="源码制品详情加载失败">
            <Button type="primary" onClick={() => void drawer.refetch()}>
              重试
            </Button>
          </ContentState>
        </div>
      ) : null}
      {!drawer.isLoading && !drawer.isError ? (
        <AssetsOverview
          artifact={drawer.artifact}
          gitForm={drawer.gitForm}
          isEditing={drawer.isEditing}
          isSaving={drawer.isUploading || drawer.isUpdatingGit}
          sourceModeLocked={Boolean(drawer.lockedSourceMode)}
          sourceTask={drawer.sourceTask}
          onCancel={drawer.resetSourceInput}
          onGitSubmit={drawer.handleGitUpdate}
          onSourceModeChange={drawer.setSourceMode}
          onStartUpdate={drawer.startSourceUpdate}
          onUploadSubmit={drawer.handleUpload}
          sourceMode={drawer.view}
          uploadForm={drawer.uploadForm}
        />
      ) : null}
    </StageSurface>
  )
}
