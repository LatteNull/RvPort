import type { ProjectBuildValidation, ProjectRuntimeEnvironmentSummary } from '@/types/project'

export interface TestBuildContext {
  role: 'SOURCE' | 'TARGET'
  environment: ProjectRuntimeEnvironmentSummary | null
  build: ProjectBuildValidation | null
  reason: string | null
}
