export const modelQueryKeys = {
  assignments: () => ['admin-model-stage-assignments'] as const,
  runtimes: () => ['admin-agent-runtimes'] as const,
  profilesState: () => ['admin-model-profiles-state'] as const,
  profiles: () => ['admin-model-profiles'] as const,
  probeRun: (id: string) => ['admin-model-profile-agent-probe-run', id] as const
}
