import { useEffect } from 'react'
import { Alert, Form, InputNumber } from 'antd'

import BaseModal from '@/components/BaseModal'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import type { WorkerInstance } from '@/types/admin/workers'

interface ConcurrencyModalProps {
  loading: boolean
  visible: boolean
  worker: WorkerInstance | null
  onCancel: () => void
  onSubmit: (concurrencyLimit: number) => Promise<void>
}

interface ConcurrencyFormValues {
  concurrencyLimit: number
}

export default function ConcurrencyModal({
  loading,
  visible,
  worker,
  onCancel,
  onSubmit
}: ConcurrencyModalProps) {
  const [form] = Form.useForm<ConcurrencyFormValues>()

  const submission = useSubmissionSession(
    `worker-concurrency:${worker?.instanceId}`,
    visible && Boolean(worker)
  )
  const busy = loading || submission.busy

  useEffect(() => {
    if (visible && worker) {
      form.setFieldsValue({ concurrencyLimit: worker.concurrencyLimit })
    }
  }, [form, visible, worker])

  return (
    <BaseModal
      busy={busy}
      confirmLoading={busy}
      okText="保存设置"
      title="设置 Worker 并发"
      visible={visible}
      width={520}
      destroyOnHidden
      onCancel={onCancel}
      onOk={() => {
        if (loading) return
        return submission.run(async (isCurrent) => {
          const values = await form.validateFields()
          if (isCurrent()) await onSubmit(values.concurrencyLimit)
        })
      }}
    >
      <Form<ConcurrencyFormValues>
        disabled={busy}
        form={form}
        initialValues={{ concurrencyLimit: worker?.concurrencyLimit }}
        layout="vertical"
        preserve={false}
      >
        <Form.Item label="Worker 实例">
          <span>{worker?.instanceId ?? '--'}</span>
        </Form.Item>
        <Form.Item
          label="任务消费并发"
          name="concurrencyLimit"
          rules={[
            { required: true, message: '请输入任务消费并发' },
            {
              type: 'integer',
              min: 0,
              message: '任务消费并发必须是大于或等于 0 的整数'
            }
          ]}
        >
          <InputNumber min={0} precision={0} style={{ width: '100%' }} />
        </Form.Item>
        <Alert
          description="设置为 0 会暂停该 Worker 接收新任务；降低并发不会取消或中断已经运行的任务。"
          showIcon
          type="info"
        />
      </Form>
    </BaseModal>
  )
}
