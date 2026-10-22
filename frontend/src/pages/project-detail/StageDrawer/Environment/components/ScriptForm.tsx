import { Form, Input, InputNumber, Select } from 'antd'

import CodeMirrorEditor from '@/components/CodeMirrorEditor'
import type { ProjectEnvironment } from '@/types/project'

import { environmentScriptTypeOptions } from '../constants'
import type { EnvironmentScriptFormValues } from '../model'

import styles from '../index.module.scss'

interface ScriptFormProps {
  busy?: boolean
  environment: ProjectEnvironment
}

export default function ScriptForm({ environment, busy = false }: ScriptFormProps) {
  const form = Form.useFormInstance<EnvironmentScriptFormValues>()
  const scriptType = Form.useWatch('scriptType', form)
  const isCustomScript = scriptType === 'CUSTOM'

  return (
    <>
      <div className={styles.environmentFormGrid}>
        <Form.Item label="目标环境">
          <Input disabled value={environment.name} />
        </Form.Item>
        <Form.Item
          label="脚本类型"
          name="scriptType"
          rules={[{ required: true, message: '请选择脚本类型' }]}
        >
          <Select options={environmentScriptTypeOptions} />
        </Form.Item>
        <Form.Item
          label="工作目录"
          name="workdir"
          rules={[{ required: true, message: '请输入工作目录' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          label="超时时间"
          name="timeout"
          rules={[
            { required: true, message: '请输入超时时间' },
            { type: 'number', min: 1, max: 86400, message: '超时时间需介于 1 至 86400 秒' }
          ]}
        >
          <InputNumber addonAfter="秒" className={styles.fullWidth} max={86400} min={1} />
        </Form.Item>
      </div>
      {isCustomScript ? (
        <Form.Item
          label="脚本内容"
          name="content"
          rules={[{ required: true, whitespace: true, message: '请输入脚本内容' }]}
        >
          <CodeMirrorEditor
            readOnly={busy}
            ariaLabel="脚本内容"
            className={styles.scriptCodeEditor}
            height={320}
            language="shell"
          />
        </Form.Item>
      ) : null}
    </>
  )
}
