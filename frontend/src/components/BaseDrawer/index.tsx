import { isValidElement, type ReactNode } from 'react'
import type { DrawerProps } from 'antd'
import { Drawer } from 'antd'
import clsx from 'clsx'

import moduleStyles from './index.module.scss'

type AntdDrawerProps = DrawerProps
type DrawerStyles = NonNullable<DrawerProps['styles']>
type DrawerStylesObject = Exclude<DrawerStyles, (info: { props: DrawerProps }) => unknown>

interface BaseDrawerTitleObject {
  title: ReactNode
  subTitle?: ReactNode
}

type BaseDrawerTitle = ReactNode | BaseDrawerTitleObject

export type BaseDrawerProps = Omit<
  AntdDrawerProps,
  'footer' | 'height' | 'open' | 'title' | 'width'
> & {
  footer?: ReactNode
  title?: BaseDrawerTitle
  visible?: boolean
}

const baseDrawerStyles: DrawerStylesObject = {
  title: {
    fontSize: 'var(--ant-font-size-heading-4, 18px)',
    fontWeight: 500,
    lineHeight: 'var(--ant-line-height-heading-4, 1.3333333333)'
  },
  section: {
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
    background: '#ffffff'
  },
  header: {
    flex: '0 0 auto',
    padding: 'var(--base-drawer-header-padding, 12px 24px)',
    borderBottom: '1px solid rgba(28, 31, 35, 0.08)'
  },
  body: {
    flex: 1,
    maxWidth: '100%',
    minHeight: 0,
    padding: 'var(--base-drawer-body-padding, 16px 24px)',
    overflowX: 'hidden',
    overflowY: 'auto',
    overscrollBehavior: 'contain'
  },
  footer: {
    display: 'flex',
    flex: '0 0 auto',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'flex-end',
    padding: 'var(--base-drawer-footer-padding, 16px 24px)',
    borderTop: '1px solid rgba(28, 31, 35, 0.08)'
  }
}

function mergeDrawerStyles(styles?: DrawerProps['styles']): DrawerProps['styles'] {
  if (typeof styles === 'function') {
    return (info) => ({
      ...baseDrawerStyles,
      ...styles(info)
    })
  }

  return {
    ...baseDrawerStyles,
    ...styles
  }
}

function getDrawerClosable(closable?: DrawerProps['closable']): DrawerProps['closable'] {
  if (closable === false) {
    return false
  }

  if (typeof closable === 'object') {
    return {
      placement: 'end',
      ...closable
    }
  }

  return {
    placement: 'end'
  }
}

function isBaseDrawerTitleObject(title: unknown): title is BaseDrawerTitleObject {
  return (
    typeof title === 'object' &&
    title !== null &&
    !Array.isArray(title) &&
    !isValidElement(title) &&
    'title' in title
  )
}

function renderDrawerTitle(title?: BaseDrawerTitle): ReactNode {
  if (isBaseDrawerTitleObject(title)) {
    return (
      <div className={moduleStyles.drawerTitle}>
        <span className={moduleStyles.drawerTitleText}>{title.title}</span>
        {title.subTitle && <span className={moduleStyles.drawerSubTitle}>{title.subTitle}</span>}
      </div>
    )
  }

  return title as ReactNode
}

export default function BaseDrawer({
  children,
  className,
  closable,
  footer,
  keyboard = true,
  mask = { closable: true },
  placement = 'right',
  size = 520,
  styles,
  title,
  visible,
  ...props
}: BaseDrawerProps) {
  return (
    <Drawer
      {...props}
      className={clsx(moduleStyles.baseDrawer, className)}
      closable={getDrawerClosable(closable)}
      footer={footer}
      keyboard={keyboard}
      mask={mask}
      open={visible}
      placement={placement}
      size={size}
      styles={mergeDrawerStyles(styles)}
      title={renderDrawerTitle(title)}
    >
      {children}
    </Drawer>
  )
}
