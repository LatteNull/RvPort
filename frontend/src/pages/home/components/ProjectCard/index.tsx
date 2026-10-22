import { Link } from 'react-router'
import { Skeleton } from 'antd'
import clsx from 'clsx'

import EllipsisText from '@/components/EllipsisText'
import ProjectArchitectureFlow from '@/components/ProjectArchitectureFlow'
import { projectStageConfig } from '@/config/project-status'
import type { ProjectBuildStatus, ProjectListItem } from '@/types/project'
import type { ProjectTaskStatus } from '@/types/project/task'
import { formatDateTime, formatDisplayValue } from '@/utils/display'

import styles from './index.module.scss'

interface ProjectCardProps {
  project: ProjectListItem
}

const projectStatusLabels: Record<ProjectListItem['status'], string> = {
  ACTIVE: '进行中',
  ARCHIVED: '已归档'
}

function getResultLabel(
  kind: 'build' | 'test',
  status: ProjectBuildStatus | ProjectTaskStatus | null
) {
  if (!status || status === 'NOT_STARTED') return null
  if (status === 'PENDING' || status === 'QUEUED') return '待执行'
  if (status === 'RUNNING') return kind === 'build' ? '构建中' : '测试中'
  if (status === 'SUCCEEDED') return kind === 'build' ? '成功' : '通过'
  if (status === 'FAILED') return '失败'
  if (status === 'TIMEOUT') return '超时'
  return '已取消'
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const stage = projectStageConfig[project.stage]
  const stageToneClass = stage.tone === 'primary' ? styles.primaryStage : styles.warningStage

  return (
    <Link
      className={clsx(styles.cardBase, styles.card)}
      aria-label={`${project.name} 项目`}
      to={`/projects/${project.id}/workflow`}
    >
      <div className={styles.header}>
        <div className={styles.identity}>
          <h2 className={styles.name}>
            <EllipsisText>{project.name}</EllipsisText>
          </h2>
          <ProjectArchitectureFlow
            className={styles.architectures}
            sourceArchitecture={project.sourceArch}
            targetArchitecture={project.targetArch}
          />
        </div>
        <span
          className={clsx(styles.projectStatus, {
            [styles.activeStatus]: project.status === 'ACTIVE'
          })}
        >
          {projectStatusLabels[project.status]}
        </span>
      </div>

      <div className={clsx(styles.stageBar, stageToneClass)}>
        <span>当前阶段</span>
        <span>• {stage.label}</span>
      </div>

      <dl className={styles.statusGrid}>
        <div>
          <dt>最近扫描时间</dt>
          <dd>{formatDateTime(project.latestScanAt)}</dd>
        </div>
        <div>
          <dt>最近构建状态</dt>
          <dd>{formatDisplayValue(getResultLabel('build', project.latestBuildStatus))}</dd>
        </div>
        <div>
          <dt>最近测试状态</dt>
          <dd>{formatDisplayValue(getResultLabel('test', project.latestTestStatus))}</dd>
        </div>
      </dl>

      <div className={styles.hoverAction} aria-hidden="true">
        进入流水线
      </div>
    </Link>
  )
}

export function ProjectCardSkeleton() {
  return (
    <div className={clsx(styles.cardBase, styles.skeletonCard)}>
      <Skeleton active />
    </div>
  )
}
