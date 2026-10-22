import { Skeleton } from 'antd'

import ContentState from '@/components/ContentState'

import styles from './index.module.scss'

export type StageViewLoadingVariant = 'detail' | 'form' | 'spinner' | 'table'

export default function StageViewLoading({
  description = '正在加载视图',
  variant = 'spinner'
}: {
  description?: string
  variant?: StageViewLoadingVariant
}) {
  if (variant !== 'spinner') {
    return (
      <div
        aria-busy="true"
        aria-label={description}
        className={styles.skeletonView}
        data-variant={variant}
        role="status"
      >
        <div className={styles.skeletonLead}>
          {variant === 'detail' ? (
            <Skeleton.Avatar active className={styles.skeletonAvatar} shape="square" size={44} />
          ) : null}
          <div className={styles.skeletonLeadCopy}>
            <Skeleton.Input active className={styles.skeletonTitle} size="small" />
            <Skeleton.Input active className={styles.skeletonSubtitle} size="small" />
          </div>
        </div>
        <div className={styles.skeletonContent}>
          <section>
            <Skeleton active paragraph={{ rows: variant === 'table' ? 9 : 7 }} title={false} />
          </section>
          {variant !== 'table' ? (
            <aside>
              <Skeleton active paragraph={{ rows: variant === 'detail' ? 6 : 7 }} title={false} />
            </aside>
          ) : null}
        </div>
      </div>
    )
  }

  return <ContentState kind="loading" description={description} className={styles.loadingView} />
}
