export const loadEnvironmentStage = () => import('./Environment')

export async function preloadEnvironmentStage() {
  await loadEnvironmentStage()
}
