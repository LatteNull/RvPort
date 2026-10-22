import { Button, Flex } from 'antd'

import RecordViewTitle from '../../components/RecordViewTitle'
import type { StageDrawerStage } from '../../types'
import type { KnowledgeBaseView } from '../types'

import styles from '../index.module.scss'

export function KnowledgeBaseTitle({
  stage,
  disabled,
  view,
  onBack
}: {
  stage?: StageDrawerStage | null
  disabled?: boolean
  view: KnowledgeBaseView
  onBack: () => void
}) {
  if (view.type === 'results') {
    return (
      <Flex align="center" className={styles.drawerTitle} gap={12}>
        <span className={styles.drawerTitleText}>{stage?.title ?? '知识库扫描'}</span>
      </Flex>
    )
  }

  const title =
    view.type === 'config'
      ? '执行知识库扫描'
      : view.type === 'detail'
        ? 'Finding 详情'
        : view.type === 'record'
          ? '扫描记录概览'
          : view.type === 'scan-info'
            ? '扫描信息'
            : '扫描记录'

  const backLabel =
    view.type === 'history'
      ? '返回最新结果'
      : view.type === 'record'
        ? '返回扫描记录'
        : view.type === 'detail' && view.returnTo === 'record'
          ? '返回扫描记录概览'
          : view.type === 'scan-info' && view.returnTo === 'history'
            ? '返回扫描记录'
            : view.type === 'scan-info' && view.returnTo === 'record'
              ? '返回扫描记录概览'
              : '返回知识库扫描'

  return <RecordViewTitle backLabel={backLabel} disabled={disabled} title={title} onBack={onBack} />
}

export function KnowledgeBaseFooter({
  isCreating,
  sourceReady,
  view,
  onCreateScan,
  onShowResults
}: {
  isCreating: boolean
  sourceReady: boolean
  view: KnowledgeBaseView
  onCreateScan: () => void
  onShowResults: () => void
}) {
  if (view.type !== 'config') return undefined

  return (
    <Flex align="center" className={styles.drawerTitle} gap={12}>
      <Button disabled={isCreating} onClick={onShowResults}>
        取消
      </Button>
      <Button disabled={!sourceReady} loading={isCreating} type="primary" onClick={onCreateScan}>
        开始扫描
      </Button>
    </Flex>
  )
}
