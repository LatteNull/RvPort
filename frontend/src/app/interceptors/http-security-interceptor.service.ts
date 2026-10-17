import { Injectable } from '@angular/core';
import { PlxMessage } from 'paletx';
import {
  HttpInterceptor,
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpResponse,
  HttpErrorResponse
} from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { tap, map, catchError } from 'rxjs/operators';
import { LogoutService } from '../services/logout.service';
import { SKIP_PASSWORD_VALIDATION_WARNING, SKIP_ERROR_WARNING } from './http-context-tokens';
@Injectable({
  providedIn: 'root'
})
export class HttpSecurityInterceptorService implements HttpInterceptor {

  constructor(
    private plxMessage: PlxMessage,
    private logoutService: LogoutService,
  ) {}
  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {

    const token = localStorage.getItem('X-Csrftoken');

    if (token) {
      request = request.clone({
        setHeaders: {
          'X-Csrftoken': token
        }
      });
    }

    return next.handle(request).pipe(
      tap((event: HttpEvent<any>) => {
        if (event instanceof HttpResponse) {
          this.saveHeaders(event);
        }
      }),
      map((event: HttpEvent<any>) => {
        // blob/text 类型为原始资源下载（如文件流、markdown 文档），不套用 JSON 统一响应格式
        if (request.responseType === 'blob' || request.responseType === 'text'){
          return event;
        }
        if (event instanceof HttpResponse) {
          return this.handleResponse(event, request);
        }
        return event;
      }),
      catchError((error: HttpErrorResponse) => this.handleError(error))
    );
  }

  private saveHeaders(response: HttpResponse<any>): void {
    const csrfToken = response.headers.get('X-Csrftoken');
    if (csrfToken) {
      localStorage.setItem('X-Csrftoken', csrfToken);
    }
  }

  private handleResponse(response: HttpResponse<any>, request: HttpRequest<any>): HttpEvent<any> {
    const contentType = response.headers.get('content-type') || '';
    let body = response.body;

    if (!contentType.includes('application/json')) {
      body = { code: -1, msg: '无效的响应格式' };
    } else if (!body) {
      body = { code: -1, msg: '空响应内容' };
    }

    if (body.code == -1 && body.msg == "请登录") {
      this.logoutService.logout();
    }

    // 设置统一的返回
    // 对于新建用户和修改密码的请求，如果密码校验失败，不显示拦截器的警告消息
    // 因为这些操作在组件内部已经处理了错误显示
    // SKIP_ERROR_WARNING：探测型请求（如对比缓存未命中）由组件自行处理，跳过统一告警
    const shouldSkipWarning = request.context.get(SKIP_PASSWORD_VALIDATION_WARNING)
      || request.context.get(SKIP_ERROR_WARNING);
    if (body.code == -1 && !shouldSkipWarning){
      this.plxMessage.warning(body.msg, "")
    }

    return response.clone({ body });
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = '';
    const serverMessage = error.error?.msg || error.error?.message || error.message;

    switch (error.status) {
      case 400:
        errorMessage = serverMessage || '无效的请求参数';
        break;
      case 401:
        errorMessage = serverMessage || '身份验证失败，请重新登录';
        this.logoutService.logout();
        break;
      case 404:
        errorMessage = serverMessage || '请求的资源不存在';
        break;
      case 405:
        errorMessage = serverMessage || '不支持的请求方法';
        break;
      case 500:
        errorMessage = serverMessage || '服务器内部错误，请联系管理员';
        break;
      case 0:
        errorMessage = '网络连接异常，请检查网络设置';
        break;
      default:
        errorMessage = '请求失败，请稍后重试';
        break
    }

    console.error(`HTTP错误码 ${error.status || '未知'}`);
    console.error(`错误信息 ${errorMessage || '未知'}`);
    this.plxMessage.error(errorMessage, "");

    return throwError(() => ({
      code: error.status || -1,
      msg: errorMessage
    }));
  }

}
