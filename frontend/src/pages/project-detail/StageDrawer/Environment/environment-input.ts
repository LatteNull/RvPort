import type {
  ProjectEnvironment,
  ProjectEnvironmentConnectionTestRequest,
  ProjectEnvironmentInput,
  UpdateProjectEnvironmentRequest
} from '@/types/project'

import type { EnvironmentFormValues } from './model'

export function toEnvironmentInput(values: EnvironmentFormValues): ProjectEnvironmentInput {
  const input: ProjectEnvironmentInput = {
    name: values.name.trim(),
    role: values.role,
    architecture: values.architecture,
    host: values.host.trim(),
    jumpHostEnvironmentId: values.jumpHostEnvironmentId,
    sshPort: values.sshPort,
    username: values.username?.trim(),
    workdir: values.workdir.trim(),
    authType: values.authType
  }

  if (values.authType === 'PASSWORD') {
    return { ...input, password: values.password }
  }

  return { ...input, privateKey: values.privateKey }
}

export function toEnvironmentUpdateRequest(
  values: EnvironmentFormValues
): UpdateProjectEnvironmentRequest {
  const input = toEnvironmentInput(values)

  return {
    role: input.role,
    architecture: input.architecture,
    host: input.host,
    jumpHostEnvironmentId: input.jumpHostEnvironmentId,
    sshPort: input.sshPort,
    workdir: input.workdir,
    username: input.username,
    ...(values.credentialMode === 'retain'
      ? {}
      : {
          authType: input.authType,
          ...(input.authType === 'PASSWORD'
            ? { password: input.password }
            : { privateKey: input.privateKey })
        })
  }
}

export function toEnvironmentConnectionRequest(
  values: EnvironmentFormValues,
  environment?: ProjectEnvironment
): ProjectEnvironmentConnectionTestRequest {
  const input = toEnvironmentInput(values)
  if (values.credentialMode !== 'retain') return input
  if (!environment?.credentialId)
    throw new Error('当前凭据缺少引用，请替换凭据后预检，或保存配置后从列表检查')
  return {
    name: input.name,
    role: input.role,
    architecture: input.architecture,
    host: input.host,
    sshPort: input.sshPort,
    workdir: input.workdir,
    jumpHostEnvironmentId: input.jumpHostEnvironmentId,
    username: input.username,
    environmentId: environment.id,
    credentialId: environment.credentialId
  }
}
