import type { ModelProfileStage } from '@/types/admin/models'
export interface BindingFormValues {
  agentRuntimeId: string
  modelProfileId: string
}

export interface BindingMutationVariables extends BindingFormValues {
  stage: ModelProfileStage
}

export interface TestProfileVariables {
  agentRuntimeIds: string[]
  profileId: string
}

export interface ModelStagePresentation {
  readyText: string
  stage: ModelProfileStage
  title: string
}
