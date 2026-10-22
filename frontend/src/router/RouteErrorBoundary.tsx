import { useRouteError } from 'react-router'

import logo from '@/assets/images/logo.svg'

import { getRouteErrorPresentation } from './routeErrorPresentation'

import styles from './RouteErrorBoundary.module.scss'

export default function RouteErrorBoundary() {
  const error = useRouteError()
  const presentation = getRouteErrorPresentation(error)

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <img src={logo} alt="RvPort" className={styles.logo} height={33} width={121} />
        <span>页面恢复</span>
      </header>
      <main className={styles.main}>
        <section className={styles.errorPanel} aria-labelledby="route-error-title">
          <div className={styles.interruptedPipeline} aria-hidden="true">
            <span />
            <i />
            <strong />
            <i />
            <span />
          </div>
          <p className={styles.eyebrow}>加载中断</p>
          <h1 id="route-error-title">{presentation.title}</h1>
          <p className={styles.description}>{presentation.description}</p>
          <div className={styles.actions}>
            <button type="button" onClick={() => window.location.reload()}>
              重新加载
            </button>
            <a href="/home">返回首页</a>
          </div>
          {import.meta.env.DEV && presentation.detail ? (
            <details className={styles.details}>
              <summary>错误详情</summary>
              <code>{presentation.detail}</code>
            </details>
          ) : null}
        </section>
      </main>
    </div>
  )
}
