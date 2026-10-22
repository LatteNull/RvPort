import { Fragment, type ReactNode, useState } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import { Alert, Button, Flex, Form, Input, Segmented, Upload } from 'antd'
import type { Rule } from 'antd/es/form'

import ContentState from '@/components/ContentState'
import type {
  ProjectOverviewTask,
  ProjectSourceArtifact,
  UpdateProjectSourceFromGitRequest
} from '@/types/project'
import { formatDateTime } from '@/utils/display'
import { feedback } from '@/utils/feedback'

import type { AssetsView, UploadValues } from '../types'

import styles from '../index.module.scss'

const gitRepositoryUrlRules: Rule[] = [
  { required: true, whitespace: true, message: '请输入仓库地址' },
  { max: 2000, message: '仓库地址不能超过 2000 个字符' },
  {
    validator: async (_, value?: string) => {
      const repositoryUrl = value?.trim()
      if (!repositoryUrl || !/^https?:\/\//i.test(repositoryUrl)) return

      let parsedUrl: URL
      try {
        parsedUrl = new URL(repositoryUrl)
      } catch {
        throw new Error('仓库地址格式不正确')
      }
      if (parsedUrl.username || parsedUrl.password) {
        throw new Error('仓库地址中不能包含用户名、密码或 Token，请填写在下方凭据字段中')
      }
    }
  }
]

export function AssetsOverview({
  artifact,
  gitForm,
  isEditing,
  isSaving,
  onCancel,
  onGitSubmit,
  onSourceModeChange,
  onStartUpdate,
  onUploadSubmit,
  sourceModeLocked,
  sourceMode,
  sourceTask,
  uploadForm
}: {
  artifact?: ProjectSourceArtifact
  gitForm: ReturnType<typeof Form.useForm<UpdateProjectSourceFromGitRequest>>[0]
  isEditing: boolean
  isSaving: boolean
  onCancel: () => void
  onGitSubmit: (values: UpdateProjectSourceFromGitRequest) => Promise<unknown>
  onSourceModeChange: (mode: AssetsView) => void
  onStartUpdate: () => void
  onUploadSubmit: (values: UploadValues) => Promise<unknown>
  sourceModeLocked: boolean
  sourceMode: AssetsView
  sourceTask?: ProjectOverviewTask
  uploadForm: ReturnType<typeof Form.useForm<UploadValues>>[0]
}) {
  const [submitError, setSubmitError] = useState<string>()
  const importPending = Boolean(
    sourceTask && ['PENDING', 'QUEUED', 'RUNNING'].includes(sourceTask.status)
  )
  const importFailed = Boolean(
    sourceTask && ['FAILED', 'CANCELLED', 'TIMEOUT'].includes(sourceTask.status)
  )

  const handleSubmit = async (submit: () => Promise<unknown>) => {
    setSubmitError(undefined)
    try {
      await submit()
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '源码提交失败，请稍后重试')
    }
  }

  const renderFormActions = () => (
    <Fragment>
      {submitError ? (
        <Alert className={styles.submitError} title={submitError} showIcon type="error" />
      ) : null}
      <Flex className={styles.formActions} gap={12} justify="end">
        {artifact ? (
          <Button disabled={isSaving} onClick={onCancel}>
            取消
          </Button>
        ) : null}
        <Button htmlType="submit" loading={isSaving} type="primary">
          {sourceMode === 'upload' ? '上传' : '更新'}
        </Button>
      </Flex>
    </Fragment>
  )

  return (
    <div className={styles.overview}>
      <div className={styles.sourceHeader}>
        <div>
          <h3>{artifact ? '当前有效源码' : '导入源码'}</h3>
          <p>
            {artifact
              ? '后续扫描与构建将使用此版本。'
              : '导入后将自动设为当前源码，供后续扫描与构建使用。'}
          </p>
        </div>
        {artifact && !isEditing ? (
          <Button
            className={styles.sourceActionLink}
            size="small"
            disabled={importPending}
            type="link"
            onClick={onStartUpdate}
          >
            更新当前源码
          </Button>
        ) : null}
      </div>
      {importPending || importFailed ? (
        <Alert
          showIcon
          type={importPending ? 'info' : 'error'}
          title={
            importPending
              ? 'Git 同步正在执行，请等待任务完成。'
              : 'Git 同步未完成，请检查输入后重新提交。'
          }
          description={importFailed ? sourceTask?.message : undefined}
        />
      ) : null}
      {artifact ? (
        <ArtifactInfo artifact={artifact} />
      ) : (
        <ContentState
          description={
            importPending
              ? 'Git 更新已提交，完成后将在此显示当前源码。'
              : '暂未导入源码。请选择下方方式导入。'
          }
        />
      )}
      {isEditing ? (
        <section className={styles.sourceActions}>
          <div className={styles.sourceActionsHeading}>
            <h3>{artifact ? '更新方式' : '选择导入方式'}</h3>
            <p>{artifact ? '提交后将替换当前源码版本。' : '请选择一种方式并填写源码信息。'}</p>
          </div>
          {sourceModeLocked ? (
            <span className={styles.sourceModeLocked}>
              {sourceMode === 'upload' ? '上传源码压缩包' : '从 Git 更新代码'}
            </span>
          ) : (
            <Segmented
              block
              disabled={isSaving}
              className={styles.sourceModeControl}
              options={[
                { label: '上传源码压缩包', value: 'upload' },
                { label: '从 Git 更新代码', value: 'git' }
              ]}
              value={sourceMode}
              onChange={(value) => {
                setSubmitError(undefined)
                onSourceModeChange(value as AssetsView)
              }}
            />
          )}
          {sourceMode === 'upload' ? (
            <Form
              key="upload"
              className={styles.sourceForm}
              disabled={isSaving}
              form={uploadForm}
              layout="vertical"
              onFinish={(values) => void handleSubmit(() => onUploadSubmit(values))}
            >
              <UploadSourceFields />
              {renderFormActions()}
            </Form>
          ) : (
            <Form
              key="git"
              className={`${styles.sourceForm} ${styles.gitForm}`}
              disabled={isSaving}
              form={gitForm}
              layout="vertical"
              onFinish={(values) => void handleSubmit(() => onGitSubmit(values))}
            >
              <GitSourceFields />
              {renderFormActions()}
            </Form>
          )}
        </section>
      ) : null}
    </div>
  )
}

function ArtifactInfo({ artifact }: { artifact: ProjectSourceArtifact }) {
  const sourceValue =
    artifact.type === 'ARCHIVE' ? (
      artifact.fileName
    ) : artifact.repositoryUrl ? (
      <a href={artifact.repositoryUrl} rel="noreferrer" target="_blank">
        {artifact.repositoryUrl}
      </a>
    ) : (
      '-'
    )
  const items: Array<[string, ReactNode]> = [
    ['当前版本', artifact.version],
    ['来源', artifact.type === 'ARCHIVE' ? '源码压缩包' : 'Git 仓库'],
    [artifact.type === 'ARCHIVE' ? '源码包' : '仓库地址', sourceValue ?? '-'],
    ...(artifact.type === 'GIT'
      ? ([
          ['Git 分支', artifact.branch ?? '-'],
          ['Git Commit', artifact.ref ?? '-']
        ] as Array<[string, ReactNode]>)
      : []),
    ['最近更新时间', formatDateTime(artifact.updatedAt)] as [string, ReactNode]
  ]
  return (
    <section className={styles.artifactPanel}>
      {items.map(([label, value]) => (
        <div className={styles.artifactItem} key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  )
}

function UploadSourceFields() {
  return (
    <Form.Item
      label="源码压缩包"
      name="file"
      rules={[{ required: true, message: '请选择源码压缩包' }]}
      valuePropName="fileList"
      getValueFromEvent={(event) => event.fileList}
    >
      <Upload.Dragger
        accept=".zip"
        beforeUpload={(file) => {
          if (!file.name.toLowerCase().endsWith('.zip')) {
            feedback.error('仅支持 .zip 格式的源码压缩包')
            return Upload.LIST_IGNORE
          }
          return false
        }}
        maxCount={1}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <span className={styles.uploadHint}>拖拽 .zip 文件到此处，或点击选择文件</span>
      </Upload.Dragger>
    </Form.Item>
  )
}

function GitSourceFields() {
  return (
    <Fragment>
      <Form.Item label="仓库地址" name="repositoryUrl" rules={gitRepositoryUrlRules}>
        <Input />
      </Form.Item>
      <Form.Item
        label="Ref"
        name="ref"
        rules={[
          { required: true, whitespace: true, message: '请输入分支、Tag 或 Commit' },
          { max: 255, message: 'Ref 不能超过 255 个字符' }
        ]}
      >
        <Input placeholder="main / v1.0.0 / commit SHA" />
      </Form.Item>
      <Form.Item
        label="Git 用户名（可选）"
        name="username"
        rules={[{ max: 255, message: 'Git 用户名不能超过 255 个字符' }]}
      >
        <Input autoComplete="off" />
      </Form.Item>
      <Form.Item label="Access Token（可选）" name="accessToken">
        <Input.Password autoComplete="new-password" />
      </Form.Item>
    </Fragment>
  )
}
