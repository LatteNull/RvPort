import type { ProjectStageDetailStatus } from '@/types/project'

export interface StageDrawerStage {
  id: string
  order: number
  title: string
  subtitle: string
  status: ProjectStageDetailStatus
}

export interface StageDrawerProps {
  projectId?: string
  visible: boolean
  presentation?: 'drawer' | 'panel'
  stage?: StageDrawerStage | null
  onClose: () => void
  onStageChange?: (stageId: string) => void
  onDirtyChange?: (dirty: boolean) => void
}
