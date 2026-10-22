import { readFileSync } from 'node:fs'
import { compileString } from 'sass'
import { describe, expect, it } from 'vitest'

const stylesheet = compileString(
  readFileSync('src/pages/project-detail/Workflow/index.module.scss', 'utf8')
).css

describe('Workflow motion styles', () => {
  it('only enables the looping edge animation when reduced motion is not requested', () => {
    // 检查编译后的媒体规则，避免依赖已移除的逐节点 Sass 选择器实现。
    const motionRule = stylesheet.match(
      /@media\s*\(prefers-reduced-motion:\s*no-preference\)\s*\{\s*([^{}]+)\{([^{}]+)\}\s*\}/
    )

    expect(motionRule).not.toBeNull()
    expect(motionRule![1]).toContain('.workflow-edge-hovered .react-flow__edge-path')
    expect(motionRule![2]).toContain('animation: hoverEdgeFlow 700ms linear infinite')

    const staticStyles = stylesheet.replace(motionRule![0], '')
    expect(staticStyles).not.toMatch(/animation\s*:/)
    expect(staticStyles).toMatch(
      /\.workflow-edge-hovered \.react-flow__edge-path[^{}]*\{[^{}]*stroke-dasharray:\s*9 7/
    )
  })
})
