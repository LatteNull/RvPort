import { Tag } from 'antd'
export function displayValue(value: string | null | undefined) {
  return value || '--'
}

export function packageLabel(name: string | null, version: string | null) {
  const packageName = displayValue(name)
  return version ? `${packageName}@${version}` : packageName
}

export function dependencyRiskTag(risk: string) {
  const config = {
    CRITICAL: { color: 'error', label: '严重' },
    HIGH: { color: 'volcano', label: '高' },
    MEDIUM: { color: 'warning', label: '中' },
    LOW: { color: 'success', label: '低' },
    INFO: { color: 'processing', label: '提示' },
    COMMENT: { color: 'default', label: '备注' }
  }[risk]
  return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{risk}</Tag>
}

export function dependencyTypeLabel(value: string) {
  return (
    {
      BUILD_TOOL: '构建工具',
      BUILD_PACKAGE: '构建包',
      LINK_LIBRARY: '链接库',
      RUNTIME_LIBRARY: '运行时库',
      TEST_TOOL: '测试工具',
      TEST_PACKAGE: '测试包'
    }[value] ?? value
  )
}

export function dependencyTargetMatchStatusTag(status: string) {
  const config = {
    TARGET_INSTALLED: { color: 'success', label: '目标已安装' },
    PROVIDES_MATCH: { color: 'success', label: '提供能力匹配' },
    SAME_MAJOR: { color: 'success', label: '主版本兼容' },
    TARGET_NEWER: { color: 'success', label: '目标版本更高' },
    REPO_AVAILABLE: { color: 'processing', label: '仓库可用' },
    TARGET_OLDER: { color: 'warning', label: '目标版本较低' },
    TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED: { color: 'warning', label: '目标包可用，源码未归属' },
    SOURCE_BUILD_REQUIRED: { color: 'warning', label: '需从源码构建' },
    MANUAL_CONFIRM_REQUIRED: { color: 'default', label: '需人工确认' },
    NO_TARGET_VERSION_FOUND: { color: 'error', label: '未找到目标版本' },
    VERSION_MISMATCH: { color: 'error', label: '版本不匹配' },
    MISSING: { color: 'error', label: '目标缺失' }
  }[status]
  return config ? <Tag color={config.color}>{config.label}</Tag> : <Tag>{status}</Tag>
}
