import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { PlxMessage, PlxModal, PlxModule } from 'paletx';
import { Router, provideRouter } from '@angular/router';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { LoginComponent } from './login.component';
import { FormsModule } from '@angular/forms';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let fixture: ComponentFixture<LoginComponent>;
  let httpMock: HttpTestingController;
  let router: Router;
  let plxMessageService: jasmine.SpyObj<PlxMessage>;
  let plxModalService: jasmine.SpyObj<PlxModal>;

  beforeEach(async () => {
    const plxMessageSpy = jasmine.createSpyObj('PlxMessage', ['success', 'error']);
    const plxModalSpy = jasmine.createSpyObj('PlxModal', ['open', 'destroyModalInstance']);
    await TestBed.configureTestingModule({
      declarations: [LoginComponent],
      imports: [
        PlxModule.forRoot(),
        FormsModule,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: PlxMessage, useValue: plxMessageSpy },
        { provide: PlxModal, useValue: plxModalSpy },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    plxMessageService = TestBed.inject(PlxMessage) as jasmine.SpyObj<PlxMessage>;
    plxModalService = TestBed.inject(PlxModal) as jasmine.SpyObj<PlxModal>;
    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('测试创建应用', () => {
    expect(component).toBeTruthy();
  });

  it('测试登录', () => {
    spyOn(router, 'navigate');

    component.username = 'testUser';
    component.password = 'testPass';
    component.login();

    const req = httpMock.expectOne('/action/auth/login');
    expect(req.request.method).toBe('POST');

    req.flush({ code: 0 }, { headers: { 'X-Csrftoken': 'token123' } });

    expect(localStorage.getItem('X-Csrftoken')).toBe('token123');
    expect(localStorage.getItem('user_name')).toBe('testUser');
    expect(router.navigate).toHaveBeenCalledWith(['/cardmodel']);
  });

  it('测试登录设置密码', () => {
    spyOn(router, 'navigate');

    component.username = 'testUser';
    component.password = 'testPass';
    component.login();

    const req = httpMock.expectOne('/action/auth/login');
    expect(req.request.method).toBe('POST');

    req.flush({ code: 1, msg: 'first_login' });

    expect(plxMessageService.success).toHaveBeenCalledWith('用户首次登录，请重置密码', '');
    expect(plxModalService.open).toHaveBeenCalled();
  });

  it('测试处理登录失败', () => {
    component.username = 'wrongUser';
    component.password = 'wrongPass';
    component.login();

    const req = httpMock.expectOne('/action/auth/login');
    expect(req.request.method).toBe('POST');

    req.flush({ code: 1, msg: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });

    expect(plxMessageService.error).toHaveBeenCalledWith('登陆失败', 'Invalid credentials');
  });

  it('测试成功改密码', () => {
    spyOn(router, 'navigate');

    component.username = 'testUser';
    component.formSetting = {
      validateFields: () => true,
      formObject: {
        value: {
          previousPassword: 'oldPass',
          newPassword: 'newPass123',
        }
      }
    };

    component.submit();

    const req = httpMock.expectOne('/action/auth/modify-password');
    expect(req.request.method).toBe('POST');
    req.flush({ code: 0 });

    expect(plxMessageService.success).toHaveBeenCalledWith('修改密码成功，请重新登录', '');
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('测试改密码失败', () => {
    component.username = 'testUser';
    component.formSetting = {
      validateFields: () => true,
      formObject: {
        value: {
          previousPassword: 'oldPass',
          newPassword: 'newPass123'
        }
      }
    };

    component.submit();

    const req = httpMock.expectOne('/action/auth/modify-password');
    expect(req.request.method).toBe('POST');
    req.flush({ code: 1, msg: 'Incorrect old password' });

    expect(plxMessageService.error).toHaveBeenCalledWith('修改密码失败', 'Incorrect old password');
  });

  it('测试打开对话框', () => {
    component.openWithoutDestroy({});
    expect(plxModalService.open).toHaveBeenCalled();
    expect(component.isOpen).toBeTrue();
  });

});
