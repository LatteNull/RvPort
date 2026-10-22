import { Button, Flex, Form, Input, InputNumber } from 'antd'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'

import styles from '../index.module.scss'
const buildCommandEditorHeight = 256

export default function BuildConfiguration({
  effectiveScript,
  setScript,
  timeoutSeconds,
  setTimeoutSeconds,
  environmentVariables,
  setEnvironmentVariables,
  isPending,
  disabled = false,
  onSubmit
}: {
  effectiveScript: string
  setScript: (value: string) => void
  timeoutSeconds: number
  setTimeoutSeconds: (value: number) => void
  environmentVariables: string
  setEnvironmentVariables: (value: string) => void
  disabled?: boolean
  isPending: boolean
  onSubmit: () => void
}) {
  return (
    <>
      <Form component={false} layout="vertical">
        <div className={styles.configurationGrid}>
          <Form.Item className={styles.scriptField} label="构建命令" required>
            <CodeMirrorEditor
              ariaLabel="构建命令"
              className={styles.scriptEditor}
              height={buildCommandEditorHeight}
              language="shell"
              value={effectiveScript}
              onChange={setScript}
            />
          </Form.Item>
          <div className={styles.configurationSide}>
            <Form.Item
              className={styles.sidebarFormItem}
              htmlFor="build-timeout-seconds"
              label="超时时间（秒）"
              required
            >
              <InputNumber
                autoComplete="off"
                id="build-timeout-seconds"
                min={10}
                max={86400}
                name="timeoutSeconds"
                value={timeoutSeconds}
                onChange={(value) => setTimeoutSeconds(value ?? 3600)}
              />
            </Form.Item>
            <Form.Item
              className={styles.sidebarFormItem}
              htmlFor="build-environment-variables"
              label="环境变量（每行 KEY=VALUE，可选）"
            >
              <Input.TextArea
                autoComplete="off"
                autoSize={false}
                className={styles.environmentVariables}
                id="build-environment-variables"
                name="environmentVariables"
                rows={8}
                value={environmentVariables}
                onChange={(event) => setEnvironmentVariables(event.target.value)}
              />
            </Form.Item>
          </div>
        </div>
      </Form>
      <Flex className={styles.formActions} justify="end">
        <Button
          disabled={disabled || !effectiveScript.trim()}
          loading={isPending}
          type="primary"
          onClick={onSubmit}
        >
          开始构建
        </Button>
      </Flex>
    </>
  )
}
