import { type ReactNode, useState } from 'react'
import { ApiOutlined, DownOutlined, FileSearchOutlined } from '@ant-design/icons'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'

import { formatEvidenceValue } from './presentation'

import styles from './index.module.scss'

function FindingDisclosure({
  title,
  description,
  icon,
  className,
  children
}: {
  title: string
  description: string
  icon: ReactNode
  className: string
  children: ReactNode | (() => ReactNode)
}) {
  const [open, setOpen] = useState(false)

  return (
    <details className={className} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className={styles.findingFactsSummary}>
        <div>
          <div>
            <h3>
              {icon}
              {title}
            </h3>
            <p>{description}</p>
          </div>
        </div>
        <span className={styles.findingDisclosureAction}>
          <span>{open ? '收起详情' : '展开详情'}</span>
          <DownOutlined aria-hidden="true" />
        </span>
      </summary>
      {typeof children === 'function' ? (open ? children() : null) : children}
    </details>
  )
}

export function FindingFacts({ children }: { children: ReactNode }) {
  return (
    <FindingDisclosure
      title="扫描事实"
      description="用于复核规则命中与当前选中位置"
      icon={<ApiOutlined aria-hidden="true" />}
      className={styles.findingFactsPanel}
    >
      {children}
    </FindingDisclosure>
  )
}

export function FindingRawData({ value }: { value: unknown }) {
  return (
    <FindingDisclosure
      title="原始扫描数据"
      description="用于诊断与复核接口返回的原始数据"
      icon={<FileSearchOutlined aria-hidden="true" />}
      className={styles.rawEvidenceDisclosure}
    >
      {() => (
        <div>
          <p>用于诊断与复核，主要迁移判断已在上方整理。</p>
          <div
            aria-label="原始扫描数据代码视口"
            className={styles.rawEvidenceCodeViewport}
            role="region"
          >
            <CodeMirrorEditor
              ariaLabel="原始扫描数据"
              className={styles.evidenceCode}
              height="100%"
              language="json"
              readOnly
              value={formatEvidenceValue(value)}
            />
          </div>
        </div>
      )}
    </FindingDisclosure>
  )
}
