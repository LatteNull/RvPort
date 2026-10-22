import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StageOverview, { type StageOverviewProps } from './StageOverview'
import { StagePresentationContext } from './StagePresentationContext'
import StageSurface from './StageSurface'

vi.mock('./TaskLogPanel', () => ({
  TaskLogPanel: ({ taskId }: { taskId: string }) => <div>任务日志 {taskId}</div>
}))

function model(): StageOverviewProps {
  return {
    label: '测试分析',
    gate: {
      ready: true,
      prerequisites: [{ key: 'X86_BUILD', label: 'x86 构建', ready: true, value: '已完成' }]
    },
    request: { loading: false, error: false, hasData: true, reload: vi.fn() },
    result: {
      hasResult: true,
      freshness: 'CURRENT',
      status: 'SUCCEEDED',
      record: { taskId: 'task-old', status: 'SUCCEEDED' }
    },
    operation: { start: { label: '执行分析', onClick: vi.fn() } },
    children: <div>模块完整业务结果</div>
  }
}

describe('当前概览的事实优先级与阅读边界', () => {
  afterEach(() => vi.useRealTimers())

  it('提交同步延迟可重新加载，保持禁止重复执行并在新任务到达后恢复', () => {
    vi.useFakeTimers()
    const props = model()
    props.result = { hasResult: false, freshness: 'EMPTY' }
    props.operation!.submitting = true
    const { rerender, unmount } = render(<StageOverview {...props} />)
    expect(screen.queryByText(/状态同步较慢/)).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(10_000))
    expect(screen.getByText(/状态同步较慢/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(props.request.reload).toHaveBeenCalledOnce()
    expect(props.operation!.start!.onClick).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '执行分析' })).not.toBeInTheDocument()
    props.operation!.submitting = false
    props.result.status = 'RUNNING'
    rerender(<StageOverview {...props} />)
    expect(screen.getByText('测试分析正在执行')).toBeVisible()
    expect(screen.queryByText(/状态同步较慢/)).not.toBeInTheDocument()
    props.operation!.submitting = true
    rerender(<StageOverview {...props} />)
    expect(screen.getByText('服务端正在同步任务信息，请稍候。')).toBeVisible()
    unmount()
    act(() => vi.advanceTimersByTime(10_000))
  })
  it.each(['SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'])(
    '受阻时隐藏旧 %s 终态，但保留历史入口',
    (status) => {
      const props = model()
      props.gate.ready = false
      props.result.status = status
      render(
        <StagePresentationContext.Provider value="panel">
          <StageSurface visible onHistory={vi.fn()} title="测试分析">
            <StageOverview {...props} />
          </StageSurface>
        </StagePresentationContext.Provider>
      )
      expect(screen.getByText('暂不能执行测试分析')).toBeVisible()
      expect(screen.queryByText('模块完整业务结果')).not.toBeInTheDocument()
      expect(screen.getAllByRole('status')).toHaveLength(1)
      expect(screen.getByRole('button', { name: '查看历史记录' })).toBeVisible()
      expect(screen.queryByRole('button', { name: '执行分析' })).not.toBeInTheDocument()
    }
  )
  it.each(['PENDING', 'QUEUED', 'RUNNING'])(
    '受阻保留旧版本 %s 任务身份和日志，禁止新执行',
    (status) => {
      const props = model()
      props.gate.ready = false
      props.result = { ...props.result, freshness: 'STALE', status }
      render(<StageOverview {...props} />)
      expect(screen.getByText('已有旧版本任务仍在执行，状态以任务记录为准。')).toBeVisible()
      expect(screen.queryByText('任务日志 task-old')).not.toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: '查看日志' }))
      expect(screen.getByText('任务日志 task-old')).toBeVisible()
      expect(screen.queryByRole('button', { name: '执行分析' })).not.toBeInTheDocument()
    }
  )
  it('刷新失败保留业务内容并禁用新执行', () => {
    const props = model()
    props.result = { ...props.result, freshness: 'EMPTY', hasResult: false, status: null }
    props.request.error = true
    const { rerender } = render(<StageOverview {...props} />)
    expect(screen.getByRole('button', { name: '执行分析' })).toBeDisabled()
    props.result = model().result
    rerender(<StageOverview {...props} />)
    expect(screen.getByText('模块完整业务结果')).toBeVisible()
    expect(screen.getByText(/刷新失败，正在显示上次读取的内容/)).toBeVisible()
  })
  it('只有旧终态时展示当前条件，旧结果不冒充当前成功', () => {
    const props = model()
    props.result.freshness = 'STALE'
    render(<StageOverview {...props} />)
    expect(screen.getByText('当前版本暂无有效结果，旧结果可从历史记录查看。')).toBeVisible()
    expect(screen.getByText('x86 构建')).toBeVisible()
    expect(screen.queryByText('模块完整业务结果')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '执行分析' }))
    expect(props.operation?.start?.onClick).toHaveBeenCalledOnce()
  })
  it('提交受理但尚无新结果时不闪回可执行空态', () => {
    const props = model()
    props.result = { hasResult: false, freshness: 'EMPTY' }
    props.operation!.submitting = true
    render(<StageOverview {...props} />)
    expect(screen.getByText('已提交，正在同步状态')).toBeVisible()
    expect(screen.queryByRole('button', { name: '执行分析' })).not.toBeInTheDocument()
  })
  it('execution 先到而 result 未到时仍显示真实运行任务', () => {
    const props = model()
    props.result = {
      hasResult: false,
      freshness: 'EMPTY',
      execution: {
        id: 'run',
        taskId: 'task',
        status: 'RUNNING',
        createdAt: '',
        startedAt: null,
        finishedAt: null,
        errorCode: null,
        errorMessage: null,
        progress: 10,
        message: null
      }
    }
    render(<StageOverview {...props} />)
    expect(screen.getByText('测试分析正在执行')).toBeVisible()
    expect(screen.queryByRole('button', { name: '执行分析' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '查看日志' }))
    expect(screen.getByText('任务日志 task')).toBeVisible()
  })
})
