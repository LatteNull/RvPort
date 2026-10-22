import { Fragment, useEffect, useMemo } from 'react'
import { Button, Form, Input, InputNumber, Radio, Switch } from 'antd'

import BaseModal from '@/components/BaseModal'
import type { ModelProfile, ModelProfilePayload } from '@/types/admin/models'

interface ModelProfileFormValues {
  apiKey?: string
  baseUrl: string
  enabled: boolean
  executablePath: string
  maxRuntimeSeconds?: number
  model: string
  name: string
  timeoutSeconds?: number
  wireApi: 'CHAT' | 'RESPONSES'
}

interface ModelProfileModalProps {
  loading: boolean
  profile: ModelProfile | null
  visible: boolean
  onCancel: () => void
  onSubmit: (values: ModelProfilePayload) => Promise<void>
}

const formId = 'model-profile-form'

function getInitialValues(profile: ModelProfile | null): ModelProfileFormValues {
  return {
    apiKey: undefined,
    baseUrl: profile?.baseUrl ?? '',
    enabled: profile?.enabled ?? true,
    executablePath: profile?.executablePath ?? 'codex',
    maxRuntimeSeconds: profile?.maxRuntimeSeconds,
    model: profile?.model ?? '',
    name: profile?.name ?? '',
    timeoutSeconds: profile?.timeoutSeconds,
    wireApi: profile?.wireApi ?? 'RESPONSES'
  }
}

export default function ModelProfileModal({
  loading,
  profile,
  visible,
  onCancel,
  onSubmit
}: ModelProfileModalProps) {
  const [form] = Form.useForm<ModelProfileFormValues>()
  const isEditing = Boolean(profile)
  const initialValues = useMemo(() => getInitialValues(profile), [profile])

  useEffect(() => {
    if (!visible) return
    form.resetFields()
    form.setFieldsValue(initialValues)
  }, [form, initialValues, visible])

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
            保存配置
          </Button>
        </Fragment>
      }
      title={{
        title: isEditing ? '编辑模型 Profile' : '新增模型 Profile',
        subTitle: '模型密钥仅提交至服务端加密保存，不会在页面回显。'
      }}
      visible={visible}
      onCancel={onCancel}
    >
      <Form<ModelProfileFormValues>
        disabled={loading}
        form={form}
        id={formId}
        initialValues={initialValues}
        layout="vertical"
        preserve={false}
        onFinish={(values) => {
          if (!loading) return onSubmit(values)
        }}
      >
        <Form.Item
          label="Profile 名称"
          name="name"
          rules={[{ required: true, message: '请输入名称' }]}
        >
          <Input placeholder="例如：测试结果比较模型" />
        </Form.Item>
        <Form.Item label="启用此 Profile" name="enabled" valuePropName="checked">
          <Switch checkedChildren="已启用" unCheckedChildren="未启用" />
        </Form.Item>
        <Form.Item
          label="模型 API 地址"
          name="baseUrl"
          rules={[
            { required: true, message: '请输入模型 API 地址' },
            { type: 'url', message: '请输入有效的 URL' }
          ]}
        >
          <Input
            autoComplete="url"
            placeholder="https://api.example.com/v1"
            spellCheck={false}
            type="url"
          />
        </Form.Item>
        <Form.Item
          label="模型名称"
          name="model"
          rules={[{ required: true, message: '请输入模型名称' }]}
        >
          <Input placeholder="例如：gpt-4.1-mini" />
        </Form.Item>
        <Form.Item
          extra={profile?.apiKeyConfigured ? '已配置密钥，留空则保持不变。' : undefined}
          label="API Key"
          name="apiKey"
          rules={isEditing ? undefined : [{ required: true, message: '请输入 API Key' }]}
        >
          <Input.Password
            autoComplete="new-password"
            placeholder={isEditing ? '留空则保持不变' : '请输入 API Key'}
          />
        </Form.Item>
        <Form.Item label="API 协议" name="wireApi">
          <Radio.Group
            options={[
              { label: 'Responses API', value: 'RESPONSES' },
              { label: 'Chat Completions', value: 'CHAT' }
            ]}
          />
        </Form.Item>
        <Form.Item
          label="Codex CLI 路径"
          name="executablePath"
          rules={[{ required: true, message: '请输入 Codex CLI 路径' }]}
        >
          <Input placeholder="codex" />
        </Form.Item>
        <Form.Item label="连接超时（秒）" name="timeoutSeconds">
          <InputNumber min={1} max={600} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="最大执行时长（秒）" name="maxRuntimeSeconds">
          <InputNumber min={10} max={86400} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </BaseModal>
  )
}
