import { ArrowRightOutlined } from '@ant-design/icons'
import clsx from 'clsx'

import { projectArchitectureConfig } from '@/config/project-status'
import type { ProjectArchitecture } from '@/types/project'

import styles from './index.module.scss'

interface ProjectArchitectureFlowProps {
  className?: string
  sourceArchitecture: ProjectArchitecture
  targetArchitecture: ProjectArchitecture
}

export default function ProjectArchitectureFlow({
  className,
  sourceArchitecture,
  targetArchitecture
}: ProjectArchitectureFlowProps) {
  const source = projectArchitectureConfig[sourceArchitecture]
  const target = projectArchitectureConfig[targetArchitecture]

  return (
    <div
      className={clsx(styles.flow, className)}
      aria-label={`源架构 ${source.label}，目标架构 ${target.label}`}
    >
      <span className={styles.sourceTag}>{source.label}</span>
      <ArrowRightOutlined className={styles.arrow} aria-hidden="true" />
      <span className={styles.targetTag}>{target.label}</span>
    </div>
  )
}
