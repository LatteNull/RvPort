import { isValidElement, type ReactNode } from 'react'
import type { ModalProps } from 'antd'
import { Modal } from 'antd'

import styles from './index.module.scss'

type AntdModalProps = ModalProps
type ModalStyles = NonNullable<ModalProps['styles']>
type ModalStylesObject = Exclude<ModalStyles, (info: { props: ModalProps }) => unknown>

interface BaseModalTitleObject {
  title: ReactNode
  subTitle?: ReactNode
}

type BaseModalTitle = ReactNode | BaseModalTitleObject

export type BaseModalProps = Omit<AntdModalProps, 'footer' | 'open' | 'title'> & {
  footer?: ReactNode
  title?: BaseModalTitle
  visible?: boolean
  busy?: boolean
}

const baseModalStyles: ModalStylesObject = {
  title: {
    fontSize: 'var(--ant-font-size-heading-4, 18px)',
    fontWeight: 500,
    lineHeight: 'var(--ant-line-height-heading-4, 1.3333333333)'
  },
  container: {
    display: 'flex',
    flexDirection: 'column',
    padding: 0,
    maxHeight: 'calc(100vh - 96px)',
    overflow: 'hidden'
  },
  header: {
    margin: 0,
    padding: '12px 24px',
    borderBottom: '1px solid rgba(28, 31, 35, 0.08)'
  },
  body: {
    flex: 1,
    minHeight: 0,
    padding: 24,
    overflowY: 'auto',
    overscrollBehavior: 'contain'
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    margin: 0,
    padding: '16px 24px',
    borderTop: '1px solid rgba(28, 31, 35, 0.08)'
  }
}

function mergeModalStyles(styles?: ModalProps['styles']): ModalProps['styles'] {
  if (typeof styles === 'function') {
    return (info) => ({
      ...baseModalStyles,
      ...styles(info)
    })
  }

  return {
    ...baseModalStyles,
    ...styles
  }
}

function isBaseModalTitleObject(title: unknown): title is BaseModalTitleObject {
  return (
    typeof title === 'object' &&
    title !== null &&
    !Array.isArray(title) &&
    !isValidElement(title) &&
    'title' in title
  )
}

function renderModalTitle(title?: BaseModalTitle): ReactNode {
  if (isBaseModalTitleObject(title)) {
    return (
      <div className={styles.modalTitle}>
        <span className={styles.modalTitleText}>{title.title}</span>
        {title.subTitle && <span className={styles.modalSubTitle}>{title.subTitle}</span>}
      </div>
    )
  }

  return title as ReactNode
}

export default function BaseModal({
  children,
  busy = false,
  className,
  footer,
  maskClosable,
  styles,
  title,
  visible,
  width = 640,
  ...props
}: BaseModalProps) {
  return (
    <Modal
      {...props}
      closable={busy ? false : props.closable}
      keyboard={busy ? false : props.keyboard}
      mask={
        props.mask === false
          ? false
          : {
              ...(typeof props.mask === 'object' ? props.mask : {}),
              ...(busy
                ? { closable: false }
                : maskClosable !== undefined
                  ? { closable: maskClosable }
                  : {})
            }
      }
      onCancel={(event) => {
        if (!busy) props.onCancel?.(event)
      }}
      onOk={(event) => {
        if (!busy) props.onOk?.(event)
      }}
      confirmLoading={busy || props.confirmLoading}
      cancelButtonProps={{
        ...props.cancelButtonProps,
        disabled: busy || props.cancelButtonProps?.disabled
      }}
      okButtonProps={{ ...props.okButtonProps, disabled: busy || props.okButtonProps?.disabled }}
      className={className}
      footer={footer}
      open={visible}
      styles={mergeModalStyles(styles)}
      title={renderModalTitle(title)}
      width={width}
      centered
    >
      {children}
    </Modal>
  )
}
