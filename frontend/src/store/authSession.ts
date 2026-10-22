let generation = 0
const listeners = new Set<() => void>()

export class SessionChangedError extends Error {
  constructor() {
    super('认证会话已改变')
    this.name = 'SessionChangedError'
  }
}

export const getAuthGeneration = () => generation
export const isAuthGenerationCurrent = (value: number) => value === generation

export function advanceAuthSession() {
  generation += 1
  for (const listener of listeners) listener()
}

export function subscribeAuthSession(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
