import { Button, Flex, Form, Input, InputNumber } from 'antd'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'

import styles from '../index.module.scss'
const testCommandEditorHeight = 256

export default function TestConfiguration({
  effectiveCommand,
  setCommand,
  timeoutSeconds,
  setTimeoutSeconds,
  variables,
  setVariables,
  isPending,
  canCreate,
  onSubmit
}: {
  effectiveCommand: string
  setCommand: (value: string) => void
  timeoutSeconds: number
  setTimeoutSeconds: (value: number) => void
  variables: string
  setVariables: (value: string) => void
  isPending: boolean
  canCreate: boolean
  onSubmit: () => void
}) {
  return (
    <>
      <Form component={false} disabled={isPending} layout="vertical">
        <div className={styles.configurationGrid}>
          <Form.Item className={styles.scriptField} label="测试命令" required>
            <CodeMirrorEditor
              ariaLabel="测试命令"
              className={styles.scriptEditor}
              height={testCommandEditorHeight}
              language="shell"
              readOnly={isPending}
              value={effectiveCommand}
              onChange={setCommand}
            />
          </Form.Item>
          <div className={styles.configurationSide}>
            <Form.Item
              className={styles.sidebarFormItem}
              htmlFor="test-timeout-seconds"
              label="超时时间（秒）"
              required
            >
              <InputNumber
                autoComplete="off"
                id="test-timeout-seconds"
                min={10}
                max={86400}
                name="timeoutSeconds"
                value={timeoutSeconds}
                onChange={(value) => setTimeoutSeconds(value ?? 3600)}
              />
            </Form.Item>
            <Form.Item
              className={styles.sidebarFormItem}
              htmlFor="test-environment-variables"
              label="环境变量（每行 KEY=VALUE，可选）"
            >
              <Input.TextArea
                autoComplete="off"
                autoSize={false}
                className={styles.environmentVariables}
                id="test-environment-variables"
                name="environmentVariables"
                rows={8}
                value={variables}
                onChange={(event) => setVariables(event.target.value)}
              />
            </Form.Item>
          </div>
        </div>
      </Form>
      <Flex justify="end">
        <Button
          disabled={!canCreate || !effectiveCommand.trim()}
          loading={isPending}
          type="primary"
          onClick={onSubmit}
        >
          运行自动化测试
        </Button>
      </Flex>
    </>
  )
}
