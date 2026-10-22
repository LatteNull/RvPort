import { Button, Form, type FormInstance, Input, InputNumber } from 'antd'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'

import styles from '../index.module.scss'
const buildCommandEditorHeight = 256

export default function X86BuildConfiguration({
  form,
  effectiveScript,
  setScript,
  submitBuild,
  isPending,
  disabled = false
}: {
  form: FormInstance<{ timeoutSeconds: number; environmentVariables: string }>
  effectiveScript: string
  setScript: (value: string) => void
  submitBuild: (values: { timeoutSeconds: number; environmentVariables: string }) => void
  disabled?: boolean
  isPending: boolean
}) {
  return (
    <Form
      form={form}
      initialValues={{
        environmentVariables: '',
        timeoutSeconds: 3600
      }}
      layout="vertical"
      onFinish={submitBuild}
    >
      <div className={styles.configurationGrid}>
        <Form.Item className={styles.scriptField} label="构建命令" required>
          <CodeMirrorEditor
            ariaLabel="x86 构建命令"
            className={styles.scriptEditor}
            height={buildCommandEditorHeight}
            language="shell"
            value={effectiveScript}
            onChange={setScript}
          />
        </Form.Item>
        <div className={styles.configurationSidebar}>
          <Form.Item
            className={styles.sidebarFormItem}
            label="超时时间（秒）"
            name="timeoutSeconds"
            rules={[{ required: true }]}
          >
            <InputNumber min={10} max={86400} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            className={styles.sidebarFormItem}
            label="环境变量（可选）"
            name="environmentVariables"
          >
            <Input.TextArea
              autoSize={false}
              className={styles.environmentVariables}
              placeholder="每行一个 KEY=VALUE"
              rows={8}
            />
          </Form.Item>
        </div>
      </div>
      <div className={styles.formActions}>
        <Button htmlType="submit" disabled={disabled} loading={isPending} type="primary">
          开始 x86 构建
        </Button>
      </div>
    </Form>
  )
}
