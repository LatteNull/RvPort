import type {
  ProjectRuntimeEnvironments,
  ProjectRuntimeEnvironmentSummary,
  UpdateProjectRuntimeEnvironmentsRequest
} from '@/types/project'

import request from '../request'

export interface BackendRuntimeEnvironmentSummary {
  id: string
  name: string
  role: 'SOURCE_X86' | 'TARGET_RISCV'
  arch: string
  status: 'UNKNOWN' | 'AVAILABLE' | 'UNAVAILABLE' | 'DISABLED'
  enabled: boolean
  configVersion: number
}

export interface BackendProjectRuntimeEnvironments {
  projectId: string
  sourceEnvironment: BackendRuntimeEnvironmentSummary | null
  targetEnvironment: BackendRuntimeEnvironmentSummary | null
  version: number
  ready: boolean
  missing: string[]
  updatedBy: string | null
  updatedAt: string | null
}

function toRuntimeEnvironmentSummary(
  environment: BackendRuntimeEnvironmentSummary
): ProjectRuntimeEnvironmentSummary {
  return {
    id: environment.id,
    name: environment.name,
    role: environment.role === 'SOURCE_X86' ? 'SOURCE' : 'TARGET',
    architecture: environment.arch as ProjectRuntimeEnvironmentSummary['architecture'],
    connectionStatus:
      environment.status === 'AVAILABLE'
        ? 'SUCCESS'
        : environment.status === 'UNAVAILABLE'
          ? 'FAILED'
          : 'UNKNOWN',
    enabled: environment.enabled,
    configVersion: environment.configVersion
  }
}

export function toProjectRuntimeEnvironments(
  environments: BackendProjectRuntimeEnvironments
): ProjectRuntimeEnvironments {
  return {
    projectId: environments.projectId,
    sourceEnvironment: environments.sourceEnvironment
      ? toRuntimeEnvironmentSummary(environments.sourceEnvironment)
      : null,
    targetEnvironment: environments.targetEnvironment
      ? toRuntimeEnvironmentSummary(environments.targetEnvironment)
      : null,
    version: environments.version,
    ready: environments.ready,
    missing: environments.missing,
    updatedBy: environments.updatedBy,
    updatedAt: environments.updatedAt
  }
}

export function updateProjectRuntimeEnvironments(
  projectId: string,
  data: UpdateProjectRuntimeEnvironmentsRequest
) {
  return request
    .patch<BackendProjectRuntimeEnvironments>(`/projects/${projectId}/runtime-environments`, data)
    .then(toProjectRuntimeEnvironments)
}
