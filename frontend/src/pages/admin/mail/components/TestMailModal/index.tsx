import { Fragment, useEffect } from 'react'
import { Button, Form, Input } from 'antd'

import BaseModal from '@/components/BaseModal'

interface TestMailFormValues {
  to: string
}

interface TestMailModalProps {
  loading: boolean
  visible: boolean
  onCancel: () => void
  onSubmit: (values: TestMailFormValues) => Promise<void>
}

const formId = 'admin-test-mail-form'

export default function TestMailModal({
  loading,
  visible,
  onCancel,
  onSubmit
}: TestMailModalProps) {
  const [form] = Form.useForm<TestMailFormValues>()

  useEffect(() => {
    if (visible) form.resetFields()
  }, [form, visible])

  return (
    <BaseModal
      busy={loading}
      destroyOnHidden
      footer={
        <Fragment>
          <Button disabled={loading} onClick={onCancel}>
            取消
          </Button>
          <Button
            form={formId}
            htmlType="submit"
            disabled={loading}
            loading={loading}
            type="primary"
          >
            发送测试邮件
          </Button>
        </Fragment>
      }
      title={{ title: '发送测试邮件', subTitle: '将使用当前已保存的邮箱配置发送测试邮件。' }}
      visible={visible}
      onCancel={onCancel}
    >
      <Form<TestMailFormValues>
        disabled={loading}
        form={form}
        id={formId}
        layout="vertical"
        preserve={false}
        onFinish={(values) => {
          if (!loading) return onSubmit(values)
        }}
      >
        <Form.Item
          label="收件人邮箱"
          name="to"
          rules={[
            { required: true, message: '请输入收件人邮箱' },
            { type: 'email', message: '请输入有效的邮箱地址' }
          ]}
        >
          <Input
            autoComplete="email"
            placeholder="name@example.com"
            spellCheck={false}
            type="email"
          />
        </Form.Item>
      </Form>
    </BaseModal>
  )
}
