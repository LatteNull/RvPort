import type { ProjectStageReadiness } from '@/types/project'

import { presentPrerequisites } from '../../stagePresentation'

export function dependencyReadinessPresentation(
  readiness: ProjectStageReadiness | undefined,
  onStageChange?: (stageId: string) => void
) {
  const items = ['X86_BUILD', 'TARGET_ENVIRONMENT'].map((key) =>
    readiness?.prerequisites.find((item) => item.key === key)
  )
  return {
    ready: items.every((item) => item?.status === 'SATISFIED'),
    missingPrerequisiteCount: items.filter((item) => item?.status !== 'SATISFIED').length,
    prerequisiteItems: presentPrerequisites(items, onStageChange)
  }
}
