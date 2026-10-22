import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { StagePresentationContext } from './StagePresentationContext'
import StageSurface from './StageSurface'

describe('StageSurface', () => {
  it.each(['panel', 'drawer'] as const)(
    'uses the same scroll ownership contract in %s presentation',
    (presentation) => {
      render(
        <StagePresentationContext.Provider value={presentation}>
          <StageSurface title="详情" visible onClose={vi.fn()}>
            <div data-testid="workspace">代码与日志</div>
          </StageSurface>
        </StagePresentationContext.Provider>
      )
      const body = screen.getByTestId('workspace').parentElement
      expect(body).toHaveStyle({
        minHeight: '0',
        overflowX: 'hidden',
        overflowY: 'auto',
        padding: presentation === 'panel' ? '8px 12px' : '16px 24px'
      })
      expect(body?.style.overflow).not.toBe('hidden')
    }
  )

  it('hides the stage title and stage refresh in a Step root while keeping business actions', () => {
    const afterOpenChange = vi.fn()

    render(
      <StagePresentationContext.Provider value="panel">
        <StageSurface
          afterOpenChange={afterOpenChange}
          extra={<button type="button">刷新</button>}
          footer={<button type="button">继续</button>}
          size={1200}
          title={{ title: '源码管理', subTitle: '管理当前源码' }}
          visible
          onClose={vi.fn()}
        >
          <p>阶段业务内容</p>
          <button type="button">刷新列表</button>
        </StageSurface>
      </StagePresentationContext.Provider>
    )

    expect(screen.getByRole('region', { name: /源码管理/ })).toHaveTextContent('阶段业务内容')
    expect(screen.getByText('源码管理').closest('header')).toBeNull()
    expect(screen.getByText('管理当前源码').closest('header')).toBeNull()
    expect(screen.queryByRole('button', { name: '刷新' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新列表' })).toBeVisible()
    expect(screen.getByRole('button', { name: '继续' })).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(afterOpenChange).toHaveBeenCalledWith(true)
  })

  it('shows a nested detail title and its back action in the Step panel', () => {
    render(
      <StagePresentationContext.Provider value="panel">
        <StageSurface
          extra={<button type="button">刷新记录</button>}
          panelTitleVisible
          title={
            <>
              <button type="button">返回记录</button>
              <span>记录详情</span>
            </>
          }
          visible
          onClose={vi.fn()}
        >
          <p>详情内容</p>
        </StageSurface>
      </StagePresentationContext.Provider>
    )

    expect(screen.getByText('记录详情')).toBeVisible()
    expect(screen.getByRole('button', { name: '返回记录' })).toBeVisible()
    expect(screen.getByRole('button', { name: '刷新记录' })).toBeVisible()
  })

  it('resets Step body scrolling when entering and leaving a detail view', () => {
    const surface = (detail: boolean) => (
      <StagePresentationContext.Provider value="panel">
        <StageSurface title="阶段" visible panelTitleVisible={detail} onClose={vi.fn()}>
          <div data-testid="scroll-content">内容</div>
        </StageSurface>
      </StagePresentationContext.Provider>
    )
    const { rerender } = render(surface(false))
    const body = screen.getByTestId('scroll-content').parentElement!
    body.scrollTop = 320
    rerender(surface(true))
    expect(body.scrollTop).toBe(0)
    body.scrollTop = 450
    rerender(surface(false))
    expect(body.scrollTop).toBe(0)
  })

  it('keeps the existing Drawer presentation by default', () => {
    render(
      <StageSurface
        extra={<button type="button">刷新源码</button>}
        title="源码管理"
        visible
        onClose={vi.fn()}
      >
        <p>阶段业务内容</p>
      </StageSurface>
    )

    expect(screen.getByRole('dialog', { name: '源码管理' })).toHaveTextContent('阶段业务内容')
    expect(screen.getByRole('button', { name: '刷新源码' })).toBeVisible()
  })

  it('resets between nested details but preserves scrolling on a same-view update', () => {
    const surface = (scrollKey: string, content: string) => (
      <StagePresentationContext.Provider value="panel">
        <StageSurface
          panelScrollKey={scrollKey}
          panelTitleVisible
          title="详情"
          visible
          onClose={vi.fn()}
        >
          <div data-testid="detail-content">{content}</div>
        </StageSurface>
      </StagePresentationContext.Provider>
    )
    const { rerender } = render(surface('history', '历史记录'))
    const body = screen.getByTestId('detail-content').parentElement!
    body.scrollTop = 320
    rerender(surface('record:1', '记录一'))
    expect(body.scrollTop).toBe(0)
    body.scrollTop = 450
    rerender(surface('finding:1', 'Finding 一'))
    expect(body.scrollTop).toBe(0)
    body.scrollTop = 200
    rerender(surface('finding:1', 'Finding 一刷新'))
    expect(body.scrollTop).toBe(200)
    rerender(surface('finding:2', 'Finding 二'))
    expect(body.scrollTop).toBe(0)
  })
})
