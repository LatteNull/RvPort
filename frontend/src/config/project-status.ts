import type {
  ProjectArchitecture,
  ProjectBuildStatus,
  ProjectStage,
  ProjectStageTone,
  ProjectTestStatus
} from '@/types/project'
import type { ProjectTaskStatus } from '@/types/project/task'

interface ProjectStageConfig {
  label: string
  tone: ProjectStageTone
}

export const projectArchitectureConfig = {
  x86_64: { value: 'x86_64', label: 'x86_64' },
  riscv64: { value: 'riscv64', label: 'RISC-V' }
} satisfies Record<ProjectArchitecture, { value: ProjectArchitecture; label: string }>

export const projectStageConfig: Record<ProjectStage, ProjectStageConfig> = {
  PROJECT_CREATED: { label: '项目创建', tone: 'primary' },
  SOURCE_IMPORTED: { label: '源码已导入', tone: 'primary' },
  ENV_CONFIGURED: { label: '环境已配置', tone: 'primary' },
  SCANNING: { label: '扫描中', tone: 'warning' },
  REPORT_GENERATED: { label: '报告已生成', tone: 'primary' },
  WAITING_FIX: { label: '等待修复', tone: 'warning' },
  BUILD_PASSED: { label: '构建通过', tone: 'primary' },
  BUILD_FAILED: { label: '构建失败', tone: 'warning' },
  TEST_PASSED: { label: '测试通过', tone: 'primary' },
  TEST_FAILED: { label: '测试失败', tone: 'warning' },
  ARCHIVED: { label: '已归档', tone: 'primary' }
}

export const projectBuildStatusText: Record<ProjectBuildStatus, string> = {
  NOT_STARTED: '未开始',
  RUNNING: '构建中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
  TIMEOUT: '超时'
}

export const projectTestStatusText: Record<ProjectTestStatus, string> = {
  NOT_STARTED: '未开始',
  RUNNING: '测试中',
  SUCCEEDED: '通过',
  FAILED: '失败',
  CANCELLED: '已取消',
  TIMEOUT: '超时'
}

export const projectTaskStatusText: Record<ProjectTaskStatus, string> = {
  PENDING: '待执行',
  QUEUED: '排队中',
  RUNNING: '执行中',
  SUCCEEDED: '已完成',
  FAILED: '执行失败',
  CANCELLED: '已取消',
  TIMEOUT: '超时'
}

const projectTaskTypeText: Record<string, string> = {
  SOURCE_GIT_SYNC: 'Git 同步',
  SOURCE_DEPLOY: '源码部署',
  ENV_TEST_CONNECTION: '环境连接测试',
  ENV_COLLECT: '环境采集',
  ENV_RUN_SCRIPT: '环境脚本执行',
  DEPENDENCY_ANALYSIS: '依赖分析',
  DEPENDENCY_AUTO_FIX: '依赖自动修复',
  KB_SCAN: '知识库扫描',
  FLOATING_POINT_ANALYSIS: '浮点精度扫描',
  MEMORY_ORDER_ANALYSIS: '强弱内存序分析',
  REPORT_GENERATE: '评估报告生成',
  REPORT_COMPARE: '评估报告对比',
  RECHECK_DIFF: '源码复检',
  BUILD_VALIDATION: '构建验证',
  AUTOMATED_TEST: '自动化测试',
  TEST_LOG_COMPARE: '测试结果对比',
  ARCHIVE_PROJECT: '项目归档'
}

const projectRecommendedActionText: Record<string, string> = {
  IMPORT_SOURCE: '导入源码',
  CONFIGURE_ENVIRONMENT: '配置迁移环境',
  START_NEXT_TASK: '启动源码分析'
}

export function getProjectTaskTypeText(type: string) {
  return projectTaskTypeText[type] ?? type
}

export function getProjectRecommendedActionText(action: string) {
  return projectRecommendedActionText[action] ?? action
}
