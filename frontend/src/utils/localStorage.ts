// 浏览器存储不可用时，认证和表单仍可在当前页面生命周期内使用。
export const safeLocalStorage = {
  getItem(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  setItem(key: string, value: string): void {
    try {
      window.localStorage.setItem(key, value)
    } catch {
      // 缓存写入失败不阻断已完成的业务操作。
    }
  },
  removeItem(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      // 当前内存状态仍由所属 store / 表单更新。
    }
  }
}
