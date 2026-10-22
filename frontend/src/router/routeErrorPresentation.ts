import { isRouteErrorResponse } from 'react-router'

const STALE_MODULE_PATTERN =
  /ChunkLoadError|Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk .* failed|Outdated Optimize Dep/i

interface ErrorPresentation {
  description: string
  detail?: string
  title: string
}

export function getRouteErrorPresentation(error: unknown): ErrorPresentation {
  if (isRouteErrorResponse(error)) {
    if (error.status === 403) {
      return {
        title: '没有访问权限',
        description: '当前账号无法访问此页面，请返回首页选择其他内容。',
        detail: `${error.status} ${error.statusText}`.trim()
      }
    }

    if (error.status === 404) {
      return {
        title: '页面不存在',
        description: '页面可能已移动、删除或地址不正确。',
        detail: `${error.status} ${error.statusText}`.trim()
      }
    }

    return {
      title: '页面暂时无法显示',
      description: '加载页面数据时发生错误，请重新加载后再试。',
      detail: `${error.status} ${error.statusText}`.trim()
    }
  }

  const detail = error instanceof Error ? error.message : String(error)

  if (STALE_MODULE_PATTERN.test(detail)) {
    return {
      title: '页面资源需要更新',
      description: '页面资源已更新，当前标签页仍在使用旧版本。重新加载后即可继续。',
      detail
    }
  }

  return {
    title: '页面暂时无法显示',
    description: '加载此页面时发生错误，请重新加载后再试。',
    detail
  }
}
