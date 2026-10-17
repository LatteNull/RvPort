import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { HttpClient, HTTP_INTERCEPTORS } from '@angular/common/http';
import { HttpSecurityInterceptorService } from './http-security-interceptor.service';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { Router, provideRouter } from '@angular/router';

describe('HttpSecurityInterceptorService', () => {

  let httpMock: HttpTestingController;
  let httpClient: HttpClient;
  let router: Router;


  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptorsFromDi()), // 提供 HttpClient
        provideHttpClientTesting(),
        { provide: HTTP_INTERCEPTORS, useClass: HttpSecurityInterceptorService, multi: true },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    });

    httpClient = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);

  });

  afterEach(() => httpMock.verify());

  it('应注入CSRF令牌到请求头', () => {
    localStorage.setItem('X-Csrftoken', 'test-token-123');
    httpClient.get('/api/test').subscribe();
    const req = httpMock.expectOne('/api/test');
    expect(req.request.headers.get('X-Csrftoken')).toBe('test-token-123');
    req.flush({});
  });

  it('应保存响应中的CSRF令牌', () => {
    httpClient.get('/api/test').subscribe();
    
    const req = httpMock.expectOne('/api/test');
    req.flush({}, { headers: { 'X-Csrftoken': 'new-token-123' }});
    
    expect(localStorage.getItem('X-Csrftoken')).toBe('new-token-123');
  });

  it('应处理401未授权跳转登录', () => {
    const navigateSpy = spyOn(router, 'navigateByUrl');
    localStorage.setItem('X-Csrftoken', 'valid-token');
    
    httpClient.get('/api/protected').subscribe({
      error: () => {
        expect(localStorage.getItem('X-Csrftoken')).toBeNull();
        expect(navigateSpy).toHaveBeenCalledWith('/login');
      }
    });
    
    const req = httpMock.expectOne('/api/protected');
    req.flush({ code: -1, msg: '请登录' }, { 
      headers: { 'Content-Type': 'application/json' },
      status: 401,
      statusText: '身份验证失败，请重新登录',
    });
  });


  describe('错误处理', () => {
    const testCases = [
      { 
        status: 400,
        mockError: { error: { msg: 'Invalid params' } },
        expectedMsg: 'Invalid params' 
      },
      {
        status: 401,
        mockError: { error: { msg: 'Session expired' } },
        expectedMsg: '身份验证失败，请重新登录'
      },
      {
        status: 404,
        mockError: { error: {} }, // 补充空错误体
        expectedMsg: '请求的资源不存在'
      },
      {
        status: 500,
        mockError: { error: { message: 'DB error' } },
        expectedMsg: 'DB error'
      },
      {
        status: 0,
        mockError: null,
        expectedMsg: '网络连接异常，请检查网络设置'
      }
    ];

    testCases.forEach(({ status, mockError, expectedMsg }) => {
      it(`应处理 ${status} 错误`, (done) => {
        httpClient.get(`/api/error-${status}`).subscribe({
          error: error => {
            console.log('error', error)
            done();
          }
        });

        const req = httpMock.expectOne(`/api/error-${status}`);
        
        // 特殊处理网络错误
        if (status === 0) {
          req.error(new ProgressEvent('network_error'));
        } else {
          req.flush(
            mockError?.error || null,
            { 
              status,
              statusText: 'Error',
              headers: { 'Content-Type': 'application/json' } // 确保内容类型
            }
          );
        }
      });
    });
  });

  it('应处理非JSON响应格式', () => {
    httpClient.get('/api/csv').subscribe({
      error: error => {
        expect(error.code).toBe(-1);
        expect(error.msg).toBe('无效的响应格式');
      }
    });

    const req = httpMock.expectOne('/api/csv');
    req.flush('text-data', {
      headers: { 'Content-Type': 'text/plain' }
    });
  });

  it('应原样透传text类型响应（如markdown文档）', (done) => {
    // ngx-markdown 以 responseType:'text' 拉取 .md，不应被当作非法JSON响应
    httpClient
      .get('assets/markdown/migration-tool-guide.md', { responseType: 'text' })
      .subscribe(body => {
        expect(body).toBe('# 使用手册');
        done();
      });

    const req = httpMock.expectOne('assets/markdown/migration-tool-guide.md');
    expect(req.request.responseType).toBe('text');
    req.flush('# 使用手册', {
      headers: { 'Content-Type': 'text/markdown' }
    });
  });
});