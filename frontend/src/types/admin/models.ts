export type ModelProviderType = 'OPENAI_COMPATIBLE'
export type ModelWireApi = 'CHAT' | 'RESPONSES'
export type ModelProfileStage = 'KB_AI_EXTENSION' | 'TEST_LOG_COMPARE'
export type ModelProfileConnectivityStatus = 'SUCCESS' | 'FAILED' | 'TIMEOUT'
export type ModelProfileAgentProbeStatus = 'SUCCESS' | 'FAILED' | 'TIMEOUT'
export type ModelProfileAgentProbeRunStatus =
  'PENDING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED' | 'TIMEOUT'

export interface AgentRuntimeSummary {
  agentType: string
  enabled: boolean
  id: string
  name: string
}

export interface ModelProfileAgentProbeResult {
  agentCompatible: boolean | null
  agentRuntimeId: string
  agentType: string
  basicAvailable: boolean | null
  checks: Array<Record<string, unknown>>
  createdAt: string
  details: Record<string, unknown>
  durationMs: number | null
  errorCode: string | null
  finishedAt: string | null
  id: string
  message: string | null
  modelProfileId: string
  runId: string
  startedAt: string | null
  status: ModelProfileAgentProbeStatus
  updatedAt: string
}

export interface ModelProfileAgentProbeRun {
  agentRuntimes: AgentRuntimeSummary[]
  createdAt: string
  finishedAt: string | null
  id: string
  message: string | null
  modelProfileId: string
  results: ModelProfileAgentProbeResult[]
  selectedAgentRuntimeIds: string[]
  startedAt: string | null
  status: ModelProfileAgentProbeRunStatus
  updatedAt: string
}

export interface ActiveModelProfileAgentProbeRun {
  agentRuntimes: AgentRuntimeSummary[]
  createdAt: string
  runId: string
  status: Extract<ModelProfileAgentProbeRunStatus, 'PENDING' | 'RUNNING'>
}

export interface ModelProfileConnectivityTestResult {
  details: Record<string, unknown>
  durationMs: number
  message: string
  status: ModelProfileConnectivityStatus
  success: boolean
  testedAt: string
}

export interface ModelProfile {
  apiKeyConfigured: boolean
  apiKeyMasked: string | null
  baseUrl: string | null
  createdAt: string
  enabled: boolean
  executablePath: string
  id: string
  lastConnectivityDetails: Record<string, unknown>
  lastConnectivityDurationMs: number | null
  lastConnectivityMessage: string | null
  lastConnectivityStatus: ModelProfileConnectivityStatus | null
  lastConnectivityTestedAt: string | null
  agentProbeResults: ModelProfileAgentProbeResult[]
  activeAgentProbeRun: ActiveModelProfileAgentProbeRun | null
  maxRuntimeSeconds: number
  model: string | null
  modelProviderType: ModelProviderType
  name: string
  timeoutSeconds: number
  updatedAt: string
  wireApi: ModelWireApi
}

export interface ModelProfileListParams {
  enabled?: boolean
  keyword?: string
  page: number
  pageSize: number
}

export interface ModelProfilePayload {
  apiKey?: string
  baseUrl?: string
  enabled?: boolean
  executablePath?: string
  maxRuntimeSeconds?: number
  model?: string
  modelProviderType?: ModelProviderType
  name?: string
  timeoutSeconds?: number
  wireApi?: ModelWireApi
}

export interface ModelStageAssignment {
  agentRuntime: AgentRuntime | null
  agentRuntimeId: string | null
  modelProfile: ModelProfile | null
  modelProfileId: string | null
  stage: ModelProfileStage
  updatedAt: string | null
}

export interface AgentRuntime {
  agentType: string
  createdAt: string
  enabled: boolean
  id: string
  lastProbeAt: string | null
  lastProbeMessage: string | null
  lastProbeStatus: string | null
  name: string
  updatedAt: string
}
