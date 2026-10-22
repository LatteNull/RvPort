import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

const drawer = vi.hoisted(() => ({ props: null as Record<string, unknown> | null }))

vi.mock('antd', () => ({
  Drawer: (props: Record<string, unknown>) => {
    drawer.props = props
    return <div>{props.children as ReactNode}</div>
  }
}))

import BaseDrawer from '.'

describe('BaseDrawer', () => {
  it('uses the shared modern close behavior by default', () => {
    render(
      <BaseDrawer visible onClose={vi.fn()}>
        Drawer 内容
      </BaseDrawer>
    )

    expect(screen.getByText('Drawer 内容')).toBeInTheDocument()
    expect(drawer.props?.closable).toEqual({ placement: 'end' })
    expect(drawer.props?.keyboard).toBe(true)
    expect(drawer.props?.mask).toEqual({ closable: true })
  })

  it('preserves an explicit close override for exceptional drawers', () => {
    render(
      <BaseDrawer closable={false} keyboard={false} mask={{ closable: false }} visible>
        受限 Drawer
      </BaseDrawer>
    )

    expect(drawer.props?.closable).toBe(false)
    expect(drawer.props?.keyboard).toBe(false)
    expect(drawer.props?.mask).toEqual({ closable: false })
  })
})
