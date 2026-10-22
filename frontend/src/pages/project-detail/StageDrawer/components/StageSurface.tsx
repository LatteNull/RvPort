import { type CSSProperties, type ReactNode, useContext } from 'react'
import { Button, Flex } from 'antd'

import BaseDrawer, { type BaseDrawerProps } from '@/components/BaseDrawer'
import TableViewStateProvider from '@/components/BaseTable/TableViewStateProvider'

import StagePanel from './StagePanel'
import { StagePresentationContext } from './StagePresentationContext'

export default function StageSurface({
  afterOpenChange,
  children,
  extra,
  footer,
  onHistory,
  loading,
  panelScrollKey,
  panelTitleVisible = false,
  listStateScope = 'owned',
  styles,
  title,
  visible,
  ...drawerProps
}: BaseDrawerProps & {
  children?: ReactNode
  listStateScope?: 'owned' | 'external'
  panelTitleVisible?: boolean
  panelScrollKey?: string
  onHistory?: () => void
}) {
  const actions = onHistory ? (
    <Flex align="center" gap={4}>
      <Button type="link" onClick={onHistory}>
        查看历史记录
      </Button>
      {extra}
    </Flex>
  ) : (
    extra
  )
  const presentation = useContext(StagePresentationContext)
  // Complete detail content scrolls here; code/log viewers own their bounded inner viewport.
  const bodyStyle: CSSProperties = {
    flex: 1,
    maxWidth: '100%',
    minWidth: 0,
    minHeight: 0,
    padding: presentation === 'panel' ? '8px 12px' : '16px 24px',
    overscrollBehavior: 'contain',
    overflowX: 'hidden',
    overflowY: 'auto'
  }
  const resolvedStyles = typeof styles === 'function' ? undefined : styles
  const surfaceStyles = {
    ...resolvedStyles,
    body: { ...bodyStyle, ...resolvedStyles?.body }
  }

  const wrap = (content: ReactNode) =>
    listStateScope === 'external' ? (
      content
    ) : (
      <TableViewStateProvider active={visible}>{content}</TableViewStateProvider>
    )
  if (presentation === 'panel') {
    return wrap(
      <StagePanel
        extra={panelTitleVisible || onHistory ? actions : undefined}
        footer={footer}
        loading={Boolean(loading)}
        scrollKey={panelScrollKey}
        showTitle={panelTitleVisible}
        styles={surfaceStyles}
        title={title}
        visible={visible}
        onVisibleChange={afterOpenChange}
      >
        {children}
      </StagePanel>
    )
  }

  return wrap(
    <BaseDrawer
      {...drawerProps}
      afterOpenChange={afterOpenChange}
      extra={actions}
      footer={footer}
      loading={loading}
      styles={
        typeof styles === 'function'
          ? (info) => {
              const slots = styles(info)
              return { ...slots, body: { ...bodyStyle, ...slots?.body } }
            }
          : surfaceStyles
      }
      title={title}
      visible={visible}
    >
      {children}
    </BaseDrawer>
  )
}
