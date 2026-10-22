import { Fragment } from 'react'
import { EditOutlined } from '@ant-design/icons'
import { Button, Flex, Form, type FormInstance, Input, Popconfirm } from 'antd'

import type { BackendProject } from '@/api/project/projects'
import ContentState from '@/components/ContentState'

import { DrawerInfoItem } from '../components'
import StageSurface from '../components/StageSurface'
import { useStageDraft } from '../components/useStageDraft'
import { getStageDrawerWidth } from '../drawerWidth'
import type { StageDrawerProps } from '../types'
import { type ProjectFormValues, useProjectDrawer } from './useProjectDrawer'

import styles from '../index.module.scss'

function ProjectBody({
  data,
  form,
  isDescriptionEditing,
  isSaving,
  onCancelDescriptionEdit,
  onDescriptionEdit,
  onSave
}: {
  data: BackendProject
  form: FormInstance<ProjectFormValues>
  isDescriptionEditing: boolean
  isSaving: boolean
  onCancelDescriptionEdit: () => void
  onDescriptionEdit: () => void
  onSave: () => Promise<void>
}) {
  return (
    <div className={styles.drawerContent}>
      <section className={styles.projectDrawerSection}>
        <h3>项目基本信息</h3>
        <DrawerInfoItem label="项目名称" value={data.name || '-'} />
        <div className={styles.projectInfoGrid}>
          <DrawerInfoItem label="源架构" value={data.sourceArch || '-'} />
          <DrawerInfoItem label="目标架构" value={data.targetArch || '-'} />
        </div>

        <Form
          disabled={isSaving}
          form={form}
          initialValues={{ description: data.description ?? '' }}
        >
          <div className={styles.projectDescription}>
            <Flex align="center" gap={4} className={styles.projectDescriptionHeader}>
              <span className={styles.projectDescriptionLabel}>项目描述</span>
              {!isDescriptionEditing && (
                <Button
                  aria-label="编辑项目描述"
                  icon={<EditOutlined size={12} />}
                  size="small"
                  title="编辑项目描述"
                  color="primary"
                  variant="text"
                  onClick={onDescriptionEdit}
                />
              )}
            </Flex>

            {isDescriptionEditing ? (
              <Fragment>
                <Form.Item name="description" noStyle>
                  <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
                </Form.Item>
                <Flex justify="flex-end" gap={8}>
                  <Button disabled={isSaving} size="small" onClick={onCancelDescriptionEdit}>
                    取消
                  </Button>
                  <Popconfirm
                    cancelText="取消"
                    description="保存后将更新当前项目的基础信息。"
                    okButtonProps={{ loading: isSaving }}
                    okText="确认保存"
                    onConfirm={onSave}
                    title="确认保存项目描述？"
                  >
                    <Button loading={isSaving} size="small" type="primary">
                      保存
                    </Button>
                  </Popconfirm>
                </Flex>
              </Fragment>
            ) : (
              <p className={styles.projectDescriptionValue}>{data.description || '-'}</p>
            )}
          </div>
        </Form>
      </section>
    </div>
  )
}

export default function Project({
  projectId,
  visible,
  presentation,
  stage,
  onClose,
  onStageChange,
  onDirtyChange
}: StageDrawerProps) {
  const drawer = useProjectDrawer(projectId, visible)
  const description = Form.useWatch('description', { form: drawer.form, preserve: true })
  useStageDraft(
    description ?? drawer.detail?.description ?? '',
    drawer.detail?.description ?? '',
    visible && drawer.isDescriptionEditing,
    onDirtyChange
  )
  const drawerTitle = (
    <Flex align="center" gap={12} className={styles.projectDrawerTitle}>
      <Flex align="baseline" gap={4}>
        <span className={styles.projectDrawerTitleText}>项目基础配置</span>
        <span className={styles.projectDrawerSubTitle}>
          {stage?.subtitle ?? '展示项目当前迁移进展、风险概况和下一步入口'}
        </span>
      </Flex>
    </Flex>
  )
  return (
    <StageSurface
      afterOpenChange={(open) => {
        if (!open) drawer.resetAfterClose()
      }}
      footer={
        presentation === 'panel' ? undefined : (
          <Flex gap={12}>
            <Button
              disabled={drawer.isDescriptionEditing}
              type="primary"
              onClick={() => onStageChange?.('env')}
            >
              进入环境管理
            </Button>
            <Button
              disabled={drawer.isDescriptionEditing}
              type="primary"
              onClick={() => onStageChange?.('assets')}
            >
              进入源码管理
            </Button>
          </Flex>
        )
      }
      visible={visible}
      loading={drawer.isLoading}
      title={drawerTitle}
      size={getStageDrawerWidth('project')}
      onClose={onClose}
    >
      {drawer.isError || !drawer.detail ? (
        <ContentState kind="error" description="项目基础配置加载失败" />
      ) : (
        <ProjectBody
          data={drawer.detail}
          form={drawer.form}
          isDescriptionEditing={drawer.isDescriptionEditing}
          isSaving={drawer.isSaving}
          onCancelDescriptionEdit={drawer.handleCancelDescriptionEdit}
          onDescriptionEdit={() => drawer.setIsDescriptionEditing(true)}
          onSave={drawer.handleSave}
        />
      )}
    </StageSurface>
  )
}
