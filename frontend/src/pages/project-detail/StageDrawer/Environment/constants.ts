import type {
  ProjectArchitecture,
  ProjectEnvironmentAuthType,
  ProjectEnvironmentConnectionStatus,
  ProjectEnvironmentRole,
  ProjectEnvironmentScriptStatus,
  ProjectEnvironmentScriptType
} from '@/types/project'
import { toLabelOptions } from '@/utils/display'

export const environmentRoleText: Record<ProjectEnvironmentRole, string> = {
  SOURCE: 'x86 源环境',
  TARGET: 'RISC-V 目标环境',
  JUMP_HOST: '跳板机环境'
}

export const environmentArchitectureText: Record<ProjectArchitecture, string> = {
  x86_64: 'x86_64',
  riscv64: 'riscv64'
}

export const environmentAuthTypeText: Record<ProjectEnvironmentAuthType, string> = {
  PASSWORD: '账号密码登录',
  KEY: '密钥登录'
}

export const environmentScriptTypeText: Record<ProjectEnvironmentScriptType, string> = {
  CUSTOM: '自定义 Bash 脚本',
  COLLECTION: '环境信息采集',
  PRECHECK: '构建前检查'
}

export const environmentRoleOptions = toLabelOptions(environmentRoleText)
export const environmentArchitectureOptions = toLabelOptions(environmentArchitectureText)
export const environmentAuthTypeOptions = toLabelOptions(environmentAuthTypeText)
export const environmentScriptTypeOptions = toLabelOptions(environmentScriptTypeText)

export const environmentConnectionStatusConfig: Record<
  ProjectEnvironmentConnectionStatus,
  { color: 'default' | 'error' | 'success'; text: string }
> = {
  UNKNOWN: { color: 'default', text: '未检查' },
  SUCCESS: { color: 'success', text: '连接成功' },
  FAILED: { color: 'error', text: '连接失败' }
}

export const environmentScriptStatusConfig: Record<
  ProjectEnvironmentScriptStatus,
  { color: 'default' | 'error' | 'success'; text: string }
> = {
  RUNNING: { color: 'default', text: '进行中' },
  SUCCEEDED: { color: 'success', text: '成功' },
  FAILED: { color: 'error', text: '失败' }
}
