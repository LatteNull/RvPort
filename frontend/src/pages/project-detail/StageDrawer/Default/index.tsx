import { Alert } from 'antd'

import { getStageStatusText } from '../../stageStatus'
import { DrawerInfoItem } from '../components'
import StageSurface from '../components/StageSurface'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps, StageDrawerStage } from '../types'

import styles from '../index.module.scss'

function DefaultBody({ stage }: { stage: StageDrawerStage }) {
  return (
    <div className={styles.drawerContent}>
      {stage.status === 'blocked' && (
        <Alert
          showIcon
          description="当前阶段的前置条件尚未满足，请先处理上游阻断事项。"
          title="当前模块仅可查看"
          type="warning"
        />
      )}
      <DrawerInfoItem label="阶段状态" value={getStageStatusText(stage.status)} />
      <DrawerInfoItem label="阶段说明" value={stage.subtitle} />
    </div>
  )
}

export default function Default({ visible, stage, onClose }: StageDrawerProps) {
  return (
    <StageSurface
      size={getStageDrawerWidth(stage?.id)}
      visible={visible}
      title={stage ? { title: stage.title, subTitle: stage.subtitle } : undefined}
      onClose={onClose}
    >
      {stage && <DefaultBody stage={stage} />}
    </StageSurface>
  )
}
