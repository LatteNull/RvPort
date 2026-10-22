import type { PageResponse } from '@/types'
import type {
  ProjectEnvironment,
  ProjectEnvironmentCheckResult,
  ProjectEnvironmentConnectionTestRequest,
  ProjectEnvironmentInput,
  ProjectEnvironmentListParams,
  ProjectEnvironmentScriptExecution,
  ProjectEnvironmentScriptInput,
  UpdateProjectEnvironmentRequest
} from '@/types/project'

import request from '../request'
import { type BackendTask } from './shared'

interface BackendEnvironment {
  id: string
  projectId: string
  name: string
  role: 'SOURCE_X86' | 'TARGET_RISCV' | 'GENERAL_EXECUTION'
  arch: string
  host: string
  sshPort: number
  username: string
  credential: {
    id?: string | null
    configured: boolean
    kind: 'SSH_KEY' | 'SSH_PASSWORD' | null
  }
  status: 'UNKNOWN' | 'AVAILABLE' | 'UNAVAILABLE' | 'DISABLED'
  basicInfo: {
    arch: string | null
    basicTools: Record<string, unknown>
    checkedAt: string
    kernelVersion: string | null
    osName: string | null
    osVersion: string | null
    packageManager: string | null
    permissions: Record<string, unknown>
    remoteUser: string | null
    snapshotId: string
    snapshotKind: string
    toolVersions: Record<string, unknown>
    workingDirectory: Record<string, unknown>
  } | null
  enabled: boolean
  workingDirectory?: string | null
  lastCollectedAt?: string | null
  jumpHost: {
    id: string
    name: string
  } | null
  createdAt: string
  updatedAt?: string | null
}

interface BackendScriptExecution {
  id: string
  environmentId: string
  status: 'RUNNING' | 'SUCCEEDED' | 'ERROR'
  progress: number | null
  message: string | null
  scriptSha256: string | null
  scriptLength: number | null
  exitCode: number | null
  logEventCount: number
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
}

function toEnvironmentRole(role: ProjectEnvironmentInput['role']): BackendEnvironment['role'] {
  if (role === 'SOURCE') return 'SOURCE_X86'
  if (role === 'TARGET') return 'TARGET_RISCV'
  return 'GENERAL_EXECUTION'
}

function toEnvironment(environment: BackendEnvironment): ProjectEnvironment {
  return {
    id: environment.id,
    name: environment.name,
    role:
      environment.role === 'SOURCE_X86'
        ? 'SOURCE'
        : environment.role === 'TARGET_RISCV'
          ? 'TARGET'
          : 'JUMP_HOST',
    architecture: environment.arch as ProjectEnvironment['architecture'],
    os:
      [environment.basicInfo?.osName, environment.basicInfo?.osVersion].filter(Boolean).join(' ') ||
      null,
    host: environment.host,
    jumpHostEnvironmentId: environment.jumpHost?.id ?? null,
    sshPort: environment.sshPort,
    workdir: environment.workingDirectory ?? '',
    authType: environment.credential.kind === 'SSH_PASSWORD' ? 'PASSWORD' : 'KEY',
    basicInfo: environment.basicInfo,
    username: environment.username,
    credentialId: environment.credential.id ?? null,
    credentialsConfigured: environment.credential.configured,
    enabled: environment.enabled,
    connectionStatus:
      environment.status === 'AVAILABLE'
        ? 'SUCCESS'
        : environment.status === 'UNAVAILABLE'
          ? 'FAILED'
          : 'UNKNOWN'
  }
}

function toBackendEnvironmentInput(data: ProjectEnvironmentInput) {
  return {
    name: data.name,
    role: toEnvironmentRole(data.role),
    arch: data.architecture,
    host: data.host,
    sshPort: data.sshPort,
    username: data.username,
    loginType: data.authType,
    password: data.password,
    privateKey: data.privateKey,
    jumpHostEnvironmentId: data.jumpHostEnvironmentId,
    workingDirectory: data.workdir
  }
}

function toTaskScriptExecution(task: BackendTask): ProjectEnvironmentScriptExecution {
  return {
    id: task.id,
    environmentId: String(task.resource?.id ?? task.id),
    scriptType: 'CUSTOM',
    scriptName: task.type,
    submittedAt: task.createdAt,
    startedAt: task.startedAt,
    finishedAt: task.finishedAt,
    progress: task.progress,
    message: task.message,
    scriptSha256: null,
    scriptLength: null,
    logEventCount: 0,
    exitCode: task.status === 'FAILED' ? 1 : task.status === 'SUCCEEDED' ? 0 : null,
    status:
      task.status === 'SUCCEEDED'
        ? 'SUCCEEDED'
        : task.status === 'FAILED' || task.status === 'CANCELLED' || task.status === 'TIMEOUT'
          ? 'FAILED'
          : 'RUNNING',
    stdout: task.message ?? '',
    stderr: task.errorMessage ?? ''
  }
}

function toScriptExecution(execution: BackendScriptExecution): ProjectEnvironmentScriptExecution {
  return {
    id: execution.id,
    environmentId: execution.environmentId,
    scriptType: 'CUSTOM',
    scriptName: '自定义 Bash 脚本',
    submittedAt: execution.createdAt,
    startedAt: execution.startedAt,
    finishedAt: execution.finishedAt,
    progress: execution.progress,
    message: execution.message,
    scriptSha256: execution.scriptSha256,
    scriptLength: execution.scriptLength,
    logEventCount: execution.logEventCount,
    exitCode: execution.exitCode,
    status:
      execution.status === 'SUCCEEDED'
        ? 'SUCCEEDED'
        : execution.status === 'ERROR'
          ? 'FAILED'
          : 'RUNNING',
    stdout: execution.message ?? '',
    stderr: ''
  }
}

export function getProjectEnvironments(projectId: string, params: ProjectEnvironmentListParams) {
  return request
    .get<PageResponse<BackendEnvironment>>(`/projects/${projectId}/environments`, {
      params: {
        role: params.role ? toEnvironmentRole(params.role) : undefined,
        status: params.status,
        page: params.page,
        pageSize: params.pageSize
      }
    })
    .then((page): PageResponse<ProjectEnvironment> => ({
      ...page,
      items: page.items.map(toEnvironment)
    }))
}

export function createProjectEnvironment(projectId: string, data: ProjectEnvironmentInput) {
  return request
    .post<BackendEnvironment>(
      `/projects/${projectId}/environments`,
      toBackendEnvironmentInput(data)
    )
    .then(toEnvironment)
}

export function updateProjectEnvironment(
  environmentId: string,
  data: UpdateProjectEnvironmentRequest
) {
  return request
    .patch<BackendEnvironment>(`/environments/${environmentId}`, {
      role: data.role ? toEnvironmentRole(data.role) : undefined,
      arch: data.architecture,
      host: data.host,
      sshPort: data.sshPort,
      ...(data.authType ? { loginType: data.authType } : {}),
      username: data.username,
      ...(data.authType
        ? data.authType === 'PASSWORD'
          ? { password: data.password }
          : { privateKey: data.privateKey }
        : {}),
      jumpHostEnvironmentId: data.jumpHostEnvironmentId,
      workingDirectory: data.workdir
    })
    .then(toEnvironment)
}

export function checkProjectEnvironment(projectId: string, environment: ProjectEnvironment) {
  return request
    .post<BackendTask>(`/projects/${projectId}/environments/${environment.id}/check`, {
      checkItems: ['CONNECTION', 'BASIC_TOOLS', 'WORKING_DIRECTORY', 'PERMISSIONS'],
      workingDirectory: environment.workdir
    })
    .then((): ProjectEnvironmentCheckResult => ({
      environment,
      items: [
        { label: '任务已创建', status: 'SUCCESS', detail: '环境检查已提交，结果请在任务日志中查看' }
      ]
    }))
}

export function testProjectEnvironmentConnection(
  projectId: string,
  data: ProjectEnvironmentConnectionTestRequest
) {
  return request
    .post<BackendTask>(`/projects/${projectId}/environments/test-connection`, {
      role: toEnvironmentRole(data.role),
      arch: data.architecture,
      host: data.host,
      sshPort: data.sshPort,
      username: data.username,
      ...(data.authType
        ? {
            loginType: data.authType,
            ...(data.authType === 'PASSWORD'
              ? { password: data.password }
              : { privateKey: data.privateKey })
          }
        : {}),
      jumpHostEnvironmentId: data.jumpHostEnvironmentId,
      workingDirectory: data.workdir,
      ...(data.credentialId ? { credentialId: data.credentialId } : {}),
      timeoutSeconds: 60
    })
    .then((): ProjectEnvironmentCheckResult => ({
      environment: {
        id: data.environmentId ?? '',
        name: data.name,
        role: data.role,
        architecture: data.architecture,
        os: null,
        host: data.host,
        jumpHostEnvironmentId: data.jumpHostEnvironmentId ?? null,
        sshPort: data.sshPort,
        workdir: data.workdir,
        authType: data.authType ?? 'KEY',
        basicInfo: null,
        credentialsConfigured: true,
        connectionStatus: 'UNKNOWN'
      },
      items: [{ label: '任务已创建', status: 'SUCCESS', detail: '连接测试已提交' }]
    }))
}

export function testSavedProjectEnvironmentConnection(projectId: string, environmentId: string) {
  return request.post<BackendTask>(
    `/projects/${projectId}/environments/${environmentId}/test-connection`,
    { timeoutSeconds: 60 },
    { suppressErrorToast: true }
  )
}

export function runProjectEnvironmentScript(
  projectId: string,
  environmentId: string,
  data: ProjectEnvironmentScriptInput
) {
  const scriptType =
    data.scriptType === 'COLLECTION'
      ? 'ENV_COLLECT'
      : data.scriptType === 'PRECHECK'
        ? 'ENV_CHECK'
        : 'CUSTOM_BASH'

  return request
    .post<BackendTask>(`/projects/${projectId}/environments/${environmentId}/scripts`, {
      scriptType,
      ...(scriptType === 'CUSTOM_BASH' ? { script: data.content } : {}),
      timeoutSeconds: data.timeout || 600,
      workingDirectory: data.workdir
    })
    .then(toTaskScriptExecution)
}

export function getProjectEnvironmentScriptExecutions(
  projectId: string,
  params: { environmentId: string; page: number; pageSize: number }
) {
  return request
    .get<PageResponse<BackendScriptExecution>>(`/projects/${projectId}/script-executions`, {
      params
    })
    .then((page): PageResponse<ProjectEnvironmentScriptExecution> => ({
      ...page,
      items: page.items.map(toScriptExecution)
    }))
}

export function getProjectEnvironmentScriptExecution(executionId: string) {
  return request.get<BackendTask>(`/tasks/${executionId}`).then(toTaskScriptExecution)
}

export function getProjectEnvironmentScriptLogDownloadUrl(executionId: string, logId: string) {
  return `/api/tasks/${executionId}/logs/${logId}/download`
}
