import logo from '@/assets/images/logo.svg'

import styles from './RouteFallback.module.scss'

export default function RouteFallback() {
  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <img src={logo} alt="RvPort" className={styles.logo} height={33} width={121} />
          <span className={styles.headerStatus}>正在连接</span>
        </div>
        <div aria-hidden="true" className={styles.topProgress} />
      </header>
      <main className={styles.main}>
        <div aria-live="polite" className={styles.loading} role="status">
          <div aria-hidden="true" className={styles.pipeline}>
            <span className={styles.pipelineLine} />
            <span className={styles.pipelineNode} />
            <span className={styles.pipelineNode} />
            <span className={styles.pipelineNode} />
          </div>
          <p className={styles.title}>正在准备工作台</p>
          <p className={styles.description}>载入页面与必要数据</p>
        </div>
      </main>
    </div>
  )
}
