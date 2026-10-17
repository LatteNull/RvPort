import { HttpContextToken } from '@angular/common/http';

/**
 * 跳过密码校验失败的警告消息
 * 用于新建用户和修改密码等操作，这些操作在组件内部已经处理了错误显示
 */
export const SKIP_PASSWORD_VALIDATION_WARNING = new HttpContextToken<boolean>(() => false);

/**
 * 跳过所有 code=-1 的统一警告弹窗
 * 用于"探测型"请求（如对比缓存查询：未命中是正常分支，组件会自行降级计算），
 * 命中统一拦截器会对正常业务分支弹出误导性告警
 */
export const SKIP_ERROR_WARNING = new HttpContextToken<boolean>(() => false);

