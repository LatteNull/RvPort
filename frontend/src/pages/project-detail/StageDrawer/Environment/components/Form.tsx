import { useLayoutEffect, useRef, useState } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { Button, Flex, Form, Input, InputNumber, Select, Upload } from 'antd'

import type { ProjectEnvironment } from '@/types/project'

import {
  environmentArchitectureOptions,
  environmentAuthTypeOptions,
  environmentRoleOptions
} from '../constants'
import type { EnvironmentFormValues } from '../model'

import styles from '../index.module.scss'

interface EnvironmentFormProps {
  busy?: boolean
  isBusy?: () => boolean
  environment?: ProjectEnvironment
  isTestingConnection: boolean
  jumpHostOptions: ProjectEnvironment[]
  mode: 'create' | 'edit'
  onValuesChange?: () => void
  onTestConnection: () => void
}

export default function FormView({
  environment,
  busy = false,
  isBusy,
  isTestingConnection,
  jumpHostOptions,
  mode,
  onValuesChange,
  onTestConnection
}: EnvironmentFormProps) {
  const form = Form.useFormInstance<EnvironmentFormValues>()
  const authType = Form.useWatch('authType', form)
  const credentialMode = Form.useWatch('credentialMode', form)
  const retainCredential = credentialMode === 'retain'
  const role = Form.useWatch('role', form)
  const isCreate = mode === 'create'
  const [privateKeyFileName, setPrivateKeyFileName] = useState<string>()
  const readerRef = useRef<FileReader | null>(null)
  useLayoutEffect(() => {
    return () => {
      readerRef.current?.abort()
      readerRef.current = null
    }
  }, [busy, environment?.id, mode, authType, credentialMode])
  const handlePrivateKeyUpload: UploadProps['beforeUpload'] = (file) => {
    if (busy || isBusy?.()) return false
    readerRef.current?.abort()
    const reader = new FileReader()
    readerRef.current = reader
    reader.onload = () => {
      if (readerRef.current !== reader || isBusy?.()) return
      form.setFieldValue('privateKey', String(reader.result ?? ''))
      setPrivateKeyFileName(file.name)
      onValuesChange?.()
    }
    reader.readAsText(file)
    return false
  }
  const replaceCredential = () => {
    readerRef.current?.abort()
    readerRef.current = null
    setPrivateKeyFileName(undefined)
    form.setFieldsValue({ credentialMode: 'replace', password: undefined, privateKey: undefined })
    onValuesChange?.()
  }

  return (
    <div className={styles.environmentFormSections}>
      <section className={styles.environmentFormSection}>
        <header className={styles.formSectionHeading}>
          <strong>基础信息</strong>
          <span>定义环境在项目中的用途和工作位置。</span>
        </header>
        <div className={styles.environmentFormGrid}>
          <Form.Item
            label="服务器名称"
            name="name"
            rules={[{ required: true, message: '请输入服务器名称' }]}
          >
            <Input disabled={busy || !isCreate} />
          </Form.Item>
          <Form.Item
            label="环境角色"
            name="role"
            rules={[{ required: true, message: '请选择环境角色' }]}
          >
            <Select
              options={environmentRoleOptions}
              onChange={(nextRole) => {
                if (nextRole === 'JUMP_HOST') form.setFieldValue('jumpHostEnvironmentId', undefined)
              }}
            />
          </Form.Item>
          <Form.Item
            label="架构"
            name="architecture"
            rules={[{ required: true, message: '请选择架构' }]}
          >
            <Select options={environmentArchitectureOptions} />
          </Form.Item>
          <Form.Item
            label="工作目录"
            name="workdir"
            rules={[{ required: true, message: '请输入工作目录' }]}
          >
            <Input placeholder="/workspace/project" />
          </Form.Item>
        </div>
      </section>

      <section className={styles.environmentFormSection}>
        <header className={styles.formSectionHeading}>
          <strong>连接配置</strong>
          <span>配置 SSH 地址、端口和可选的跳板机。</span>
        </header>
        <div className={styles.environmentFormGrid}>
          <Form.Item
            label="主机 / IP"
            name="host"
            rules={[{ required: true, message: '请输入主机或 IP' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="SSH 端口"
            name="sshPort"
            rules={[{ required: true, message: '请输入 SSH 端口' }]}
          >
            <InputNumber className={styles.fullWidth} min={1} max={65535} precision={0} />
          </Form.Item>
          <Form.Item className={styles.formFullRow} label="跳板机环境" name="jumpHostEnvironmentId">
            <Select
              allowClear
              disabled={busy || role === 'JUMP_HOST'}
              options={jumpHostOptions.map((item) => ({
                label: `${item.name} (${item.host})`,
                value: item.id
              }))}
              placeholder={role === 'JUMP_HOST' ? '跳板机环境不能引用跳板机' : '不使用跳板机'}
            />
          </Form.Item>
        </div>
      </section>

      <section className={styles.environmentFormSection}>
        <header className={styles.formSectionHeading}>
          <strong>认证信息</strong>
          <span>凭据只用于连接该环境。</span>
        </header>
        <div className={styles.environmentFormGrid}>
          <Form.Item
            label="登录类型"
            name="authType"
            rules={[{ required: true, message: '请选择登录类型' }]}
          >
            <Select options={environmentAuthTypeOptions} onChange={replaceCredential} />
          </Form.Item>
          <Form.Item
            label="登录用户名"
            name="username"
            rules={
              isCreate || !retainCredential
                ? [{ required: true, whitespace: true, message: '请输入登录用户名' }]
                : undefined
            }
          >
            <Input
              placeholder={environment?.credentialsConfigured ? '重新填写才会覆盖' : undefined}
            />
          </Form.Item>
          {environment?.credentialsConfigured ? (
            <Form.Item label="凭据处理" name="credentialMode">
              <Select
                options={[
                  { label: '保留已有凭据', value: 'retain' },
                  { label: '替换凭据', value: 'replace' }
                ]}
                onChange={(value) => {
                  readerRef.current?.abort()
                  readerRef.current = null
                  form.setFieldsValue({ password: undefined, privateKey: undefined })
                  setPrivateKeyFileName(undefined)
                  if (value === 'retain') form.setFieldValue('authType', environment.authType)
                  onValuesChange?.()
                }}
              />
            </Form.Item>
          ) : null}
          {!retainCredential && authType === 'PASSWORD' ? (
            <Form.Item
              className={styles.formFullRow}
              label="密码"
              name="password"
              rules={[{ required: true, message: '请输入登录密码' }]}
            >
              <Input.Password
                placeholder={environment?.credentialsConfigured ? '重新填写才会覆盖' : undefined}
              />
            </Form.Item>
          ) : null}
        </div>

        {retainCredential || authType === 'PASSWORD' ? null : (
          <div className={styles.privateKeySection}>
            <Form.Item
              className={styles.privateKeyFormItem}
              label="SSH 私钥"
              name="privateKey"
              rules={[{ required: true, message: '请输入私钥内容' }]}
            >
              <Input.TextArea
                placeholder={
                  environment?.credentialsConfigured ? '重新填写才会覆盖' : '请输入私钥内容'
                }
                rows={4}
              />
            </Form.Item>
            <Upload.Dragger
              disabled={busy}
              beforeUpload={handlePrivateKeyUpload}
              maxCount={1}
              showUploadList={false}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <span className={styles.uploadHint}>拖拽私钥文件至此处，或点击导入</span>
              {privateKeyFileName && (
                <span className={styles.uploadFileName}>已导入：{privateKeyFileName}</span>
              )}
            </Upload.Dragger>
          </div>
        )}
        <Flex align="center" justify="space-between" className={styles.connectionTest}>
          <span>
            {retainCredential && !environment?.credentialId
              ? '当前凭据缺少引用，可保存配置后从列表检查，或替换凭据后预检。'
              : '建议保存前先验证 SSH 配置是否可用。'}
          </span>
          <Button
            disabled={busy || (retainCredential && !environment?.credentialId)}
            loading={isTestingConnection}
            onClick={onTestConnection}
          >
            测试连接
          </Button>
        </Flex>
      </section>
    </div>
  )
}
