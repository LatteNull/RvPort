import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import StagePanel from './StagePanel'

describe('内嵌阶段容器', () => {
  it('激活内容但不创建 dialog，保留刷新、子视图输入与 footer', () => {
    const onVisibleChange = vi.fn()
    const onRefresh = vi.fn()
    const content = <input aria-label="环境名称" />
    const { rerender } = render(
      <StagePanel
        title="环境管理"
        onVisibleChange={onVisibleChange}
        extra={<button onClick={onRefresh}>刷新环境</button>}
        footer={<button>保存环境</button>}
      >
        {content}
      </StagePanel>
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onVisibleChange).toHaveBeenCalledWith(true)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '构建环境' } })
    fireEvent.click(screen.getByRole('button', { name: '刷新环境' }))
    expect(onRefresh).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: '保存环境' })).toBeVisible()
    rerender(
      <StagePanel title="编辑环境" onVisibleChange={onVisibleChange}>
        {content}
      </StagePanel>
    )
    expect(screen.getByRole('textbox')).toHaveValue('构建环境')
    expect(onVisibleChange).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: '返回项目总览' })).not.toBeInTheDocument()
  })

  it('加载和隐藏时不暴露操作正文，显示后可激活环境列表', () => {
    const onVisibleChange = vi.fn()
    const { rerender } = render(
      <StagePanel title="环境管理" loading onVisibleChange={onVisibleChange}>
        <button>编辑</button>
      </StagePanel>
    )
    expect(screen.getByRole('status')).toHaveAccessibleName('正在加载阶段内容')
    expect(screen.queryByRole('button', { name: '编辑' })).not.toBeInTheDocument()
    rerender(
      <StagePanel
        title="环境管理"
        visible={false}

        onVisibleChange={onVisibleChange}
      />
    )
    expect(onVisibleChange).toHaveBeenLastCalledWith(false)
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('没有独立标题时直接呈现阶段正文', () => {
    const { container } = render(
      <StagePanel>
        <h3>当前运行环境</h3>
      </StagePanel>
    )

    expect(container.querySelector('header')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '当前运行环境' })).toBeVisible()
  })
})
