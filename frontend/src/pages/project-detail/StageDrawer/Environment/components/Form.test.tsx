import { useEffect } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button, Form } from 'antd'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createEnvironment } from '@/test/test-utils'

import { createEnvironmentFormValues } from '../model'
import FormView from './Form'

class Reader {
  static instances: Reader[] = []
  onload: (() => void) | null = null
  result = 'old-key'
  abort = vi.fn()
  readAsText = vi.fn()
  constructor() {
    Reader.instances.push(this)
  }
}
const environment = createEnvironment({ username: 'saved-user', credentialId: 'credential-1' })
function Harness({
  busy = false,
  id = 'env-1',
  changed = vi.fn()
}: {
  busy?: boolean
  id?: string
  changed?: () => void
}) {
  const [form] = Form.useForm()
  useEffect(() => {
    form.setFieldsValue({
      ...createEnvironmentFormValues({ ...environment, id }),
      credentialMode: 'replace'
    })
  }, [id, form])
  return (
    <Form form={form} disabled={busy}>
      <FormView
        environment={{ ...environment, id }}
        busy={busy}
        isBusy={() => busy}
        isTestingConnection={false}
        mode="edit"
        jumpHostOptions={[]}
        onTestConnection={vi.fn()}
        onValuesChange={changed}
      />
    </Form>
  )
}

describe('private key import ownership', () => {
  afterEach(() => vi.unstubAllGlobals())
  it.each(['submit', 'target', 'unmount'])(
    'ignores FileReader completion after %s',
    async (change) => {
      Reader.instances = []
      vi.stubGlobal('FileReader', Reader)
      const changed = vi.fn()
      const { container, rerender, unmount } = render(<Harness changed={changed} />)
      await waitFor(() => expect(screen.getByLabelText('登录用户名')).toHaveValue('saved-user'))
      const fileInput = container.querySelector('input[type="file"]')!
      fireEvent.change(fileInput, { target: { files: [new File(['key'], 'key.pem')] } })
      await waitFor(() => expect(Reader.instances).toHaveLength(1))
      const reader = Reader.instances[0]
      if (change === 'submit') rerender(<Harness busy changed={changed} />)
      else if (change === 'target') rerender(<Harness id="env-2" changed={changed} />)
      else unmount()
      reader.onload?.()
      expect(changed).not.toHaveBeenCalled()
      expect(reader.abort).toHaveBeenCalled()
      if (change !== 'unmount') expect(screen.getByLabelText('SSH 私钥')).toHaveValue('')
    }
  )
})

function CredentialHarness({
  authType,
  onSave
}: {
  authType: 'PASSWORD' | 'KEY'
  onSave: () => void
}) {
  const current = { ...environment, authType }
  return (
    <Form initialValues={createEnvironmentFormValues(current)} onFinish={onSave}>
      <FormView
        environment={current}
        isTestingConnection={false}
        mode="edit"
        jumpHostOptions={[]}
        onTestConnection={vi.fn()}
      />
      <Button htmlType="submit">验证保存</Button>
    </Form>
  )
}

describe('credential form validation', () => {
  it.each(['PASSWORD', 'KEY'] as const)(
    'permits retained %s and validates an explicit replacement',
    async (authType) => {
      const onSave = vi.fn(),
        user = userEvent.setup()
      render(<CredentialHarness authType={authType} onSave={onSave} />)
      await user.click(screen.getByRole('button', { name: '验证保存' }))
      await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
      expect(screen.getByLabelText('登录用户名')).toHaveValue('saved-user')
      await user.click(screen.getByRole('combobox', { name: '凭据处理' }))
      await user.click(await screen.findByText('替换凭据'))
      await user.click(screen.getByRole('button', { name: '验证保存' }))
      expect(
        await screen.findByText(authType === 'PASSWORD' ? '请输入登录密码' : '请输入私钥内容')
      ).toBeInTheDocument()
      expect(onSave).toHaveBeenCalledOnce()
    }
  )
})
