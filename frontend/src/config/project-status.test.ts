import { describe, expect, it } from 'vitest'

import {
  getProjectRecommendedActionText,
  getProjectTaskTypeText,
  projectArchitectureConfig,
  projectStageConfig,
  projectTaskStatusText
} from './project-status'

describe('projectArchitectureConfig', () => {
  it('keeps backend values and display labels together', () => {
    expect(projectArchitectureConfig).toEqual({
      x86_64: { value: 'x86_64', label: 'x86_64' },
      riscv64: { value: 'riscv64', label: 'RISC-V' }
    })
  })
})

describe('projectStageConfig', () => {
  it.each([
    ['PROJECT_CREATED', '项目创建', 'primary'],
    ['SOURCE_IMPORTED', '源码已导入', 'primary'],
    ['ENV_CONFIGURED', '环境已配置', 'primary'],
    ['SCANNING', '扫描中', 'warning'],
    ['REPORT_GENERATED', '报告已生成', 'primary'],
    ['WAITING_FIX', '等待修复', 'warning'],
    ['BUILD_PASSED', '构建通过', 'primary'],
    ['BUILD_FAILED', '构建失败', 'warning'],
    ['TEST_PASSED', '测试通过', 'primary'],
    ['TEST_FAILED', '测试失败', 'warning'],
    ['ARCHIVED', '已归档', 'primary']
  ] as const)('maps %s to its display configuration', (stage, label, tone) => {
    expect(projectStageConfig[stage]).toEqual({ label, tone })
  })
})

describe('project task display mappings', () => {
  it('maps known task states, types, and next actions', () => {
    expect(projectTaskStatusText.RUNNING).toBe('执行中')
    expect(getProjectTaskTypeText('SOURCE_GIT_SYNC')).toBe('Git 同步')
    expect(getProjectRecommendedActionText('CONFIGURE_ENVIRONMENT')).toBe('配置迁移环境')
  })
})
