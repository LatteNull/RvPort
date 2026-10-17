import { Directive, ViewChild, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { AbstractControl, Validators } from '@angular/forms';
import { FieldType, PlxMessage, PlxModal, ModalDismissReasons } from 'paletx';
import { AuthApi } from '../api/auth-api.service';
import { Router } from '@angular/router';

@Directive()
export abstract class BaseLoginComponent implements OnInit, OnDestroy {
  username: string = '';
  password: string = '';
  role: string = '';
  passwordFieldType: string = 'password';
  public closeResult: string = '';
  public formSetting: any;
  public modal: any;

  @ViewChild('content2') content2: any;

  private formValueChangeSubscription: any;
  private _isSubmitDisabledCache: boolean = true; // 缓存按钮禁用状态，避免每次变更检测时重复计算

  constructor(
    protected authApi: AuthApi,
    protected plxMessageService: PlxMessage,
    protected modalService: PlxModal,
    protected router: Router,
    protected cdr?: ChangeDetectorRef,
  ) {}

  togglePasswordVisibility() {
    this.passwordFieldType = this.passwordFieldType === 'password' ? 'text' : 'password';
  }

  // 抽象方法，子类需要实现具体的登录API调用
  abstract performLogin(): void;

  // 抽象方法，子类需要实现成功登录后的跳转逻辑
  abstract onLoginSuccess(): void;

  // 抽象方法，子类需要实现mode方法的具体逻辑
  abstract mode(): void;

  // 抽象方法，子类需要实现修改密码成功后的跳转逻辑
  abstract onPasswordChangeSuccess(): void;

  protected formatLoginDuration(duration: number): string {
    if (duration >= 3600) {
      // 大于等于3600秒，转换为小时
      const hours = Math.floor(duration / 3600);
      return hours + " 小时";
    } else if (duration >= 60) {
      // 60-3599秒之间，转换为分钟
      const minutes = Math.floor(duration / 60);
      return minutes + " 分钟";
    } else {
      // 小于60秒，保持秒
      return duration + " 秒";
    }
  }

  login() {
    this.performLogin();
  }

  public cancel(): void {
    this.modal.close();
    // 重置缓存状态，确保下次打开时状态正确
    this._isSubmitDisabledCache = true;
  }

  public ngOnInit() {
    this.mode();
  }

  ngOnDestroy(): void {
    // 销毁模态框实例
    this.modalService.destroyModalInstance();
    // 取消表单值变化订阅
    if (this.formValueChangeSubscription) {
      this.formValueChangeSubscription.unsubscribe();
    }
    // 重置缓存状态
    this._isSubmitDisabledCache = true;
  }

  public isOpen = true;

  public openWithoutDestroy(content: any) {
    const size: 'sm' | 'lg' | 'xs' = 'sm';
    const options = {
      size: size,
      contentClass: 'plx-modal-custom-content',
      escCallback: this.escCallback.bind(this),
      destroyOnClose: true,
      modalId: 'plx-modal-1',
      openCallback: () => {
        console.log('open111111');
        // 订阅表单值变化，以便实时更新按钮状态
        if (this.formSetting && this.formSetting.formObject) {
          this.formValueChangeSubscription = this.formSetting.formObject.valueChanges.subscribe(() => {
            // 只在表单值变化时重新计算按钮状态
            this._isSubmitDisabledCache = this.calculateSubmitDisabled();
            if (this.cdr) {
              this.cdr.detectChanges();
            }
          });
          // 初始化时计算一次
          this._isSubmitDisabledCache = this.calculateSubmitDisabled();
        }
      }
    };
    this.modal = this.modalService.open(content, options);
    setTimeout(() => {
      const btn = (document.querySelector('.modal-dialog .plx-btn-primary') as HTMLButtonElement);
      if (btn) {
        btn.focus();
      }
      // 在表单初始化后订阅值变化
      if (this.formSetting && this.formSetting.formObject) {
        if (this.formValueChangeSubscription) {
          this.formValueChangeSubscription.unsubscribe();
        }
        this.formValueChangeSubscription = this.formSetting.formObject.valueChanges.subscribe(() => {
          // 只在表单值变化时重新计算按钮状态
          this._isSubmitDisabledCache = this.calculateSubmitDisabled();
          if (this.cdr) {
            this.cdr.detectChanges();
          }
        });
        // 初始化时计算一次
        this._isSubmitDisabledCache = this.calculateSubmitDisabled();
      }
    });

    this.isOpen = true;
  }

  private escRe = true;
  public escCallback(): boolean {
    // this.escRe = !this.escRe;
    console.info('escCallback');
    return this.escRe;
  }

  private getDismissReason(reason: any): string {
    if (reason === ModalDismissReasons.ESC) {
      return 'by pressing ESC';
    } else if (reason === ModalDismissReasons.BACKDROP_CLICK) {
      return 'by clicking on a backdrop';
    } else {
      return `with: ${reason}`;
    }
  }

  // 修改密码提交按钮绑定方法
  submit() {
    // 调用validateFields方法校验表单，返回值为校验是否通过
    const isValid = this.formSetting.validateFields();

    //TODO 待修复：暂时不清楚为什么isValid一直为false
    if (isValid) {
      console.log('form value:', this.formSetting.formObject.value);
    }

    let modifyPasswordFormValue = this.formSetting.formObject.value;

    this.authApi.modifyPassword({
      username: this.username,
      old_password: modifyPasswordFormValue.previousPassword,
      new_password: modifyPasswordFormValue.newPassword
    }).subscribe({
      next: (response: any) => {
        if (response['code'] === 0) {
          // 修改成功
          this.plxMessageService.success("修改密码成功，请重新登录", "");
          this.onPasswordChangeSuccess();
        } else {
          // 修改失败
          // this.plxMessageService.error("修改密码失败", response['msg'] || '未知错误');
          alert(response['msg'] || '未知错误');
        }
      },
      error: (errorResponse: any) => {
        if (errorResponse.code !== 401) {
          const errorMessage = errorResponse.error && errorResponse.error.msg ? errorResponse.error.msg : '服务异常';
          this.plxMessageService.error("服务异常", errorMessage);
        }
        console.error(errorResponse);
      }
    });
    if (this.modal) {
      this.modal.close();
    }
    this.isOpen = false;
  }

  initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-3',
      componentClass: 'col-sm-8',
      labelWidth: '120px',
      fieldWidth: '360px',
      srcObj: {
      },
      fieldSet: [
        {
          fields: [
            {
              name: 'previousPassword',
              label: "原密码",
              type: FieldType.PASSWORD,
              placeholder: "请输入原密码",
              passwordSwitch: true,
              required: true
            },
            {
              name: 'newPassword',
              label: "新密码",
              type: FieldType.PASSWORD,
              placeholder: "请输入新密码",
              passwordSwitch: true,
              /* Started by AICoder, pid:04c269686dd684114fb20991c0ba2f082ca858f8 */
              validators: [
                Validators.pattern(this.passwordPattern),
                Validators.minLength(8),
                Validators.maxLength(64)
              ],
              validateInfos: {
                pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项，且不得有超过2个连续的相同字符",
                minlength: "密码长度不得低于8位",
                maxlength: "密码长度不得高于64位"
              },
              /* Ended by AICoder, pid:04c269686dd684114fb20991c0ba2f082ca858f8 */
              required: true,
              // 回调函数：添加值变化监听
              callback: (values: any, $event: any, controls: any) => {  
                const confirmControl = this.formSetting.formObject?.get('confirmNewPassword');
                if (confirmControl) {
                  // 触发确认密码控件的重新验证
                  confirmControl.updateValueAndValidity();
                }
              }
            },
            {
              name: 'confirmNewPassword',
              label: "确认密码",
              type: FieldType.PASSWORD,
              placeholder: "请再次输入新密码",
              passwordSwitch: true,
              required: true,
              /* Started by AICoder, pid:y5775x7d7d2ba8d1473b0ab6902a161ecbf0d2cf */
              validators: [
                this.checkPasswordSame(),  // 确保两次输入的密码一致
                // Validators.pattern(this.passwordPattern),
                // Validators.minLength(8),
                // Validators.maxLength(64)
              ],
              validateInfos: {
                // pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符, 长度为[8,64]。",
                passwordSamed: "两次输入的密码不一致",  // 两次输入的密码不一致的错误信息
              },
              /* Ended by AICoder, pid:y5775x7d7d2ba8d1473b0ab6902a161ecbf0d2cf */
            }
          ]
        }
      ]
    };
  }

  /* Started by AICoder, pid:f622b6b4750690c14f5708614001530625d1ccb9 */
  private passwordPattern = /^(?![0-9a-z]+$)(?![0-9A-Z]+$)(?![0-9\W]+$)(?![a-z\W]+$)(?![a-zA-Z]+$)(?![A-Z\W]+$)[a-zA-Z0-9\W_]+$/;
  /* Ended by AICoder, pid:f622b6b4750690c14f5708614001530625d1ccb9 */

  /* Started by AICoder, pid:l622bub475v690c14f5708614001531625d8ccb9 */
  checkPasswordSame() {
    return (control: AbstractControl): { [key: string]: any } | null => {
      if (!this.formSetting.formObject) {
        return null;
      }

      const rawValue = this.formSetting.formObject.getRawValue();
      if (rawValue.newPassword !== rawValue.confirmNewPassword) {
        return {
          passwordSamed: true // 表示密码不一致
        };
      } else {
        return null;
      }
    };
  }
  /* Ended by AICoder, pid:l622bub475v690c14f5708614001531625d8ccb9 */

  // 计算按钮禁用状态（只在表单值变化时调用，避免在变更检测时重复计算）
  private calculateSubmitDisabled(): boolean {
    if (!this.formSetting || !this.formSetting.formObject) {
      return true;
    }
    
    const formValue = this.formSetting.formObject.value || {};
    const previousPassword = formValue.previousPassword?.trim() || '';
    const newPassword = formValue.newPassword?.trim() || '';
    const confirmNewPassword = formValue.confirmNewPassword?.trim() || '';
    
    if (!previousPassword || !newPassword || !confirmNewPassword) {
      return true;
    }
    if (newPassword.length < 8 || newPassword.length > 64) {
      return true;
    }
    if (confirmNewPassword.length < 8 || confirmNewPassword.length > 64) {
      return true;
    }
    if (!this.passwordPattern.test(newPassword)) {
      return true;
    }
    if (!this.passwordPattern.test(confirmNewPassword)) {
      return true;
    }
    if (newPassword !== confirmNewPassword) {
      return true;
    }
    
    return false;
  }
  
  // 使用缓存值，避免在每次变更检测时重复计算，提升性能
  get isSubmitDisabled(): boolean {
    return this._isSubmitDisabledCache;
  }
}
