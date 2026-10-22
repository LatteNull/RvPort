import type {
  ProjectEnvironment,
  ProjectEnvironmentInput,
  ProjectEnvironmentScriptInput
} from '@/types/project'

export type EnvironmentView =
  | { type: 'list' }
  | { type: 'create' }
  | { environment: ProjectEnvironment; type: 'edit' }
  | { environment: ProjectEnvironment; type: 'script' }
  | { environment: ProjectEnvironment; type: 'history' }
  | { environment: ProjectEnvironment; executionId: string; type: 'log' }

export type EnvironmentFormValues = ProjectEnvironmentInput & {
  credentialMode?: 'retain' | 'replace'
}
export type EnvironmentScriptFormValues = ProjectEnvironmentScriptInput
export const initialEnvironmentFormValues: EnvironmentFormValues = {
  name: '',
  role: 'TARGET',
  architecture: 'riscv64',
  host: '',
  sshPort: 22,
  workdir: '',
  credentialMode: 'replace',
  authType: 'KEY'
}

export const initialEnvironmentScriptFormValues: EnvironmentScriptFormValues = {
  scriptType: 'CUSTOM',
  workdir: '',
  timeout: 600,
  content: '#!/usr/bin/env bash\nset -eu\n\npwd'
}

export function createEnvironmentFormValues(
  environment: ProjectEnvironment
): EnvironmentFormValues {
  return {
    name: environment.name,
    role: environment.role,
    architecture: environment.architecture,
    host: environment.host,
    jumpHostEnvironmentId: environment.jumpHostEnvironmentId ?? undefined,
    sshPort: environment.sshPort,
    workdir: environment.workdir,
    username: environment.username,
    credentialMode: environment.credentialsConfigured ? 'retain' : 'replace',
    authType: environment.authType
  }
}
