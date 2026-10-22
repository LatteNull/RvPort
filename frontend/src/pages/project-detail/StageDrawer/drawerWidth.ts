export const STAGE_DRAWER_WIDTH = {
  standard: 800,
  wide: 1200
} as const

const wideDrawerCanvasGutter = 96

const wideStageIds = new Set([
  'archive',
  'build',
  'kb',
  'memory-order-analysis',
  'floating-point-analysis',
  'optimize',
  'report',
  'rv-dependency-analysis',
  'test',
  'x86-build'
])

export function getStageDrawerWidth(stageId?: string) {
  return stageId && wideStageIds.has(stageId)
    ? `min(${STAGE_DRAWER_WIDTH.wide}px, calc(100vw - ${wideDrawerCanvasGutter}px))`
    : `min(${STAGE_DRAWER_WIDTH.standard}px, 100vw)`
}
