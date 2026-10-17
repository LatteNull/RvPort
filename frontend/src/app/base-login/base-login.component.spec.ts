import { of, throwError } from 'rxjs';
import { AbstractControl, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { BaseLoginComponent } from './base-login.component';

// 依赖服务 Mock
class AuthApiMock {
  modifyPassword = jasmine.createSpy('modifyPassword');
}

class PlxMessageMock {
  success = jasmine.createSpy('success');
  error = jasmine.createSpy('error');
}

class ModalRefMock {
  close = jasmine.createSpy('close');
}

class PlxModalMock {
  open = jasmine.createSpy('open').and.returnValue(new ModalRefMock());
  destroyModalInstance = jasmine.createSpy('destroyModalInstance');
}

class RouterMock {
  navigate = jasmine.createSpy('navigate');
}

// 为测试创建具体实现类（实现抽象方法）
class StubLoginComponent extends BaseLoginComponent {
  public performLoginCalled = false;
  public passwordChangedFlag = false;

  performLogin(): void {
    this.performLoginCalled = true;
  }

  onLoginSuccess(): void {}

  onPasswordChangeSuccess(): void {
    this.passwordChangedFlag = true;
  }

  mode(): void {}
}

describe('BaseLoginComponent (abstract)', () => {
  let authApi: AuthApiMock;
  let plxMessage: PlxMessageMock;
  let plxModal: PlxModalMock;
  let router: RouterMock;
  let component: StubLoginComponent;

  beforeEach(() => {
    authApi = new AuthApiMock();
    plxMessage = new PlxMessageMock();
    plxModal = new PlxModalMock();
    router = new RouterMock();
    component = new StubLoginComponent(
      authApi as any,
      plxMessage as any,
      plxModal as any,
      router as any,
    );

    // 填充必要的表单对象结构
    component.formSetting = {
      validateFields: () => true,
      formObject: {
        value: {
          previousPassword: 'oldP@ss123',
          newPassword: 'NewP@ss123',
          confirmNewPassword: 'NewP@ss123',
        },
        getRawValue: () => ({
          newPassword: component.formSetting.formObject.value.newPassword,
          confirmNewPassword: component.formSetting.formObject.value.confirmNewPassword,
        })
      }
    };
  });

  it('应切换密码可见性', () => {
    expect(component.passwordFieldType).toBe('password');
    component.togglePasswordVisibility();
    expect(component.passwordFieldType).toBe('text');
    component.togglePasswordVisibility();
    expect(component.passwordFieldType).toBe('password');
  });

  it('login() 应调用 performLogin()', () => {
    component.login();
    expect(component.performLoginCalled).toBeTrue();
  });

  it('openWithoutDestroy() 应打开模态框并设置 isOpen', () => {
    component.openWithoutDestroy({});
    expect(plxModal.open).toHaveBeenCalled();
    expect(component.isOpen).toBeTrue();
  });

  it('escCallback() 应返回 true', () => {
    expect(component["escRe"]).toBeTrue();
    expect(component.escCallback()).toBeTrue();
  });

  it('checkPasswordSame() 校验：密码一致返回 null；不一致返回错误键', () => {
    const validator = component.checkPasswordSame();
    // 一致
    component.formSetting.formObject.value.newPassword = 'A1b!aaaa';
    component.formSetting.formObject.value.confirmNewPassword = 'A1b!aaaa';
    expect(validator({} as AbstractControl)).toBeNull();
    // 不一致
    component.formSetting.formObject.value.confirmNewPassword = 'DIFF123!';
    const err = validator({} as AbstractControl);
    expect(err).toEqual({ passwordSamed: true });
  });

  it('initFormSetting() 应返回包含字段与校验规则的配置对象', () => {
    const cfg = component.initFormSetting();
    expect(cfg).toBeTruthy();
    expect(Array.isArray(cfg.fieldSet)).toBeTrue();
    const fields = cfg.fieldSet[0].fields;
    expect(fields.length).toBeGreaterThan(0);
    const newPwdField = fields.find((f: any) => f.name === 'newPassword');

    if (newPwdField && newPwdField.validators) {
      expect(Array.isArray(newPwdField.validators)).toBeTrue();
      expect(newPwdField.validators.length).toBeGreaterThanOrEqual(3);
    } else {
      fail('Field or validators are missing');
    }
  });

  it('submit() 修改密码成功路径：应调用消息、关闭模态并回调成功', () => {
    (authApi.modifyPassword as any).and.returnValue(of({ code: 0 }));

    // 模拟已经打开的模态
    component.modal = new ModalRefMock();
    component.isOpen = true;

    component.submit();

    expect(authApi.modifyPassword).toHaveBeenCalled();
    expect(plxMessage.success).toHaveBeenCalled();
    expect((component.modal as any).close).toHaveBeenCalled();
    expect(component.isOpen).toBeFalse();
    expect(component.passwordChangedFlag).toBeTrue();
  });

  it('submit() 修改密码失败路径：应提示错误', () => {
    (authApi.modifyPassword as any).and.returnValue(of({ code: 1, msg: 'bad' }));

    component.submit();

    expect(authApi.modifyPassword).toHaveBeenCalled();
    expect(plxMessage.error).toHaveBeenCalledWith('修改密码失败', 'bad');
  });

  it('submit() 请求异常路径：应提示服务异常', () => {
    (authApi.modifyPassword as any).and.returnValue(throwError(() => ({ error: { msg: 'boom' } })));

    component.submit();

    expect(authApi.modifyPassword).toHaveBeenCalled();
    expect(plxMessage.error).toHaveBeenCalledWith('服务异常', 'boom');
  });
});


