import styles from './index.module.scss'

export interface DistributionEntry {
  key: string
  label: string
  tone: string
  value: number
}

export default function CountDistribution({
  entries,
  title
}: {
  entries: DistributionEntry[]
  title: string
}) {
  const total = entries.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className={styles.panel}>
      <div className={styles.heading}>
        <span>{title}</span>
        <strong>{total}</strong>
      </div>
      <div className={styles.list}>
        {entries.map((item) => (
          <span key={item.key}>
            <i className={item.tone} />
            {item.label} <strong>{item.value}</strong>
          </span>
        ))}
      </div>
    </div>
  )
}
