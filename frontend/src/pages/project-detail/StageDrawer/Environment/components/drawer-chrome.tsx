import { LeftOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Flex, Popconfirm, Tooltip } from 'antd'

import type { StageDrawerStage } from '../../types'
import type { EnvironmentView } from '../model'

import styles from '../index.module.scss'

interface EnvironmentDrawerChromeProps {
  isRunningScript: boolean
  isSaving: boolean
  isTestingConnection: boolean
  onRunScript: () => Promise<void>
  onSave: () => Promise<void>
  onShowList: () => void
  stage?: StageDrawerStage | null
  view: EnvironmentView
}

interface EnvironmentDrawerTitleProps extends Pick<EnvironmentDrawerChromeProps, 'stage' | 'view'> {
  showBack?: boolean
  busy?: boolean
  onBack: () => void
  onRefresh: () => Promise<void>
}

export function EnvironmentDrawerTitle({
  onBack,
  onRefresh,
  showBack = false,
  busy = false,
  stage,
  view
}: EnvironmentDrawerTitleProps) {
  const title =
    view.type === 'create'
      ? '新建环境'
      : view.type === 'edit'
        ? '修改环境'
        : view.type === 'script'
          ? '运行脚本'
          : view.type === 'history'
            ? '执行记录'
            : view.type === 'log'
              ? '执行日志'
              : (stage?.title ?? '环境管理')
  const subtitle =
    view.type === 'list'
      ? (stage?.subtitle ?? 'x86/RISC-V SSH')
      : view.type === 'script' || view.type === 'history' || view.type === 'log'
        ? '环境脚本执行与审计记录'
        : '环境配置与连接状态'
  const refreshLabel =
    view.type === 'history' ? '刷新执行记录' : view.type === 'log' ? '刷新执行日志' : '刷新环境列表'
  const canRefresh = view.type === 'list' || view.type === 'history' || view.type === 'log'

  return (
    <Flex align="center" justify="space-between" className={styles.drawerTitle} gap={12}>
      <Flex align="center" gap={12}>
        {showBack || view.type === 'log' ? (
          <Tooltip title="返回">
            <Button
              disabled={busy}
              aria-label="返回"
              icon={<LeftOutlined />}
              type="text"
              onClick={onBack}
            />
          </Tooltip>
        ) : null}
        <Flex align="baseline" gap={4}>
          <span className={styles.drawerTitleText}>{title}</span>
          <span className={styles.drawerSubTitle}>{subtitle}</span>
        </Flex>
      </Flex>
      {canRefresh ? (
        <Tooltip title={refreshLabel}>
          <Button
            aria-label={refreshLabel}
            icon={<ReloadOutlined />}
            type="text"
            onClick={() => void onRefresh()}
          />
        </Tooltip>
      ) : null}
    </Flex>
  )
}

export function EnvironmentDrawerFooter({
  isRunningScript,
  isSaving,
  isTestingConnection,
  onRunScript,
  onSave,
  onShowList,
  view
}: EnvironmentDrawerChromeProps) {
  const isFormView = view.type === 'create' || view.type === 'edit'
  if (view.type === 'list') return undefined
  if (isFormView) {
    return (
      <Flex gap={12}>
        <Button disabled={isSaving || isTestingConnection} onClick={onShowList}>
          取消
        </Button>
        <Popconfirm
          disabled={isSaving || isTestingConnection}
          cancelText="取消"
          description="保存后将更新当前环境连接配置。"
          okButtonProps={{ loading: isSaving }}
          okText="确认保存"
          onConfirm={onSave}
          title={view.type === 'create' ? '确认保存环境？' : '确认保存修改？'}
        >
          <Button disabled={isSaving || isTestingConnection} loading={isSaving} type="primary">
            保存
          </Button>
        </Popconfirm>
      </Flex>
    )
  }
  if (view.type === 'script') {
    return (
      <Flex gap={12}>
        <Button disabled={isRunningScript} onClick={onShowList}>
          取消
        </Button>
        <Popconfirm
          disabled={isRunningScript}
          cancelText="取消"
          description="将在当前环境执行脚本并生成审计记录。"
          okButtonProps={{ loading: isRunningScript }}
          okText="确认执行"
          onConfirm={onRunScript}
          title="确认运行脚本？"
        >
          <Button disabled={isRunningScript} loading={isRunningScript} type="primary">
            运行脚本
          </Button>
        </Popconfirm>
      </Flex>
    )
  }
  return undefined
}
