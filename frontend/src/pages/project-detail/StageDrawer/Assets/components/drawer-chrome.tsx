import type { StageDrawerStage } from '../../types'

import styles from '../index.module.scss'

export function AssetsTitle({ stage }: { stage?: StageDrawerStage | null }) {
  return <span className={styles.drawerTitleText}>{stage?.title ?? '源码管理'}</span>
}
