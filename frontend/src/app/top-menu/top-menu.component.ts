import { Component,ViewChild,OnInit, OnDestroy, Input, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import { LogoutService } from '../services/logout.service';
import { AbstractControl, Validators } from '@angular/forms';
import { FieldType, PlxMessage, PlxModal } from 'paletx';
import { AuthApi } from '../api/auth-api.service'
import { HttpClient } from '@angular/common/http';
@Component({
  selector: 'app-top-menu',
  templateUrl: './top-menu.component.html',
  styleUrl: './top-menu.component.css',
  standalone: false,
})
export class TopMenuComponent implements OnInit, OnDestroy{
  @Input() title!: string;
  @Input() is_goback: boolean = true;
  @Input() tool: 'platform' | 'codemig' | 'none' = 'none';
  user_name: any;
  role:any;
  Csrftoken:any;
  formSetting:any;
  public modal:any;
  masterVersion: string = '';

  @ViewChild('content') content: any;
  @ViewChild('aboutContent') aboutContent: any;

  private formValueChangeSubscription: any;

  private _isSubmitDisabledCache: boolean = true; // 缓存按钮禁用状态，避免每次变更检测时重复计算

  constructor(
    private router: Router,
    private logoutService: LogoutService,
    private authApi: AuthApi,
    private plxMessageService: PlxMessage,
    private modalService: PlxModal,
    private cdr: ChangeDetectorRef,
    private http: HttpClient,
    ) {
    this.user_name = localStorage.getItem('user_name');
    this.role = localStorage.getItem('userRole');
    this.Csrftoken=localStorage.getItem('X-Csrftoken');
  }
  ngOnInit(): void {
    this.formSetting = this.initFormSetting();
  }
  public goBack() {
    this.router.navigate(['cardmodel']);
  }

  public logout() {
    this.logoutService.logout();
  }

  public goSettings() {
    this.router.navigate(['settings']);
  }

  public openHelpManual() {
    if (this.tool === 'codemig') {
      this.router.navigate(['codemig/guide']);
    } else {
      this.router.navigate(['platform/overview']);
    }
  }

  private get versionUrl(): string {
    switch (this.tool) {
      case 'codemig':
        return '/action/plugin/codemig/version';
      default:
        return '/action/version';
    }
  }

  get toolLabel(): string {
    switch (this.tool) {
      case 'codemig':
        return 'RISC-V 迁移工具';
      default:
        return 'RISC-V 迁移工具';
    }
  }

  public openAboutDialog() {
    const options = {
      size: 'xs' as 'xs',
      contentClass: 'about-modal-content',
      destroyOnClose: true,
      modalId: 'plx-modal-about',
      centered: true,
    };
    this.http.get<any>(this.versionUrl).subscribe({
      next: (resp) => {
        this.masterVersion = resp?.data?.version || '';
        this.modal = this.modalService.open(this.aboutContent, options);
      },
      error: () => {
        this.masterVersion = '';
        this.modal = this.modalService.open(this.aboutContent, options);
      }
    });
  }
  public usermanagement() {
    this.router.navigate(['settings/usermanagement']);
  }

  public isOpen = true;
  public modify_password(content: any) {
    const size: 'sm' | 'lg' | 'xs' = 'sm';
    const options = {
      size: size,
      contentClass: 'plx-modal-custom-content',
      destroyOnClose: true,
      modalId: 'plx-modal-1',
      openCallback: () => {
        console.log('open111111');
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
          this.cdr.detectChanges();
        });
        // 初始化时计算一次
        this._isSubmitDisabledCache = this.calculateSubmitDisabled();
      }
    });

    this.isOpen = true;
  }
  public cancel(): void {
    this.modal.close();
    // 重置缓存状态，确保下次打开时状态正确
    this._isSubmitDisabledCache = true;
  }
  submit(){
    const isValid = this.formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.formSetting.formObject.value);
    }
    let modifyPasswordFormValue = this.formSetting.formObject.value;
    const body = {
      username: this.user_name,
      old_password: modifyPasswordFormValue.previousPassword,
      new_password: modifyPasswordFormValue.newPassword,
    };
    console.log("body",body)
    this.authApi.modifyPassword(body).subscribe({
      next: (response: any) => {
        console.log("createresponse",response)
        console.log("response",response)
        if (response['code'] === 0) {
          this.plxMessageService.success("密码修改成功", "");
          if (this.modal) {
            this.modal.close();
          }
          this.logout();
        } else {
          alert(response['msg'] || '未知错误');
        }
      },
    });

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
              label: "旧密码",
              type: FieldType.PASSWORD,
              placeholder: "请输入旧密码",
              required: true,
              passwordSwitch: true,
            },
            {
              name: 'newPassword',
              label: "新密码",
              type: FieldType.PASSWORD,
              placeholder: "请输入新密码",
              passwordSwitch: true,
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
              required: true,
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
              validators: [
                this.checkPasswordSame(),  
                Validators.pattern(this.passwordPattern),  
                // Validators.minLength(8),  
                // Validators.maxLength(64)   
              ],
              validateInfos: {
                // pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符, 长度为[8,64]。",
                passwordSamed: "两次输入的密码不一致",  // 两次输入的密码不一致的错误信息
              },
            }
          ]
        }
      ]
    };
  }

  private passwordPattern = /^(?![0-9a-z]+$)(?![0-9A-Z]+$)(?![0-9\W]+$)(?![a-z\W]+$)(?![a-zA-Z]+$)(?![A-Z\W]+$)[a-zA-Z0-9\W_]+$/;
  checkPasswordSame() {
    return (control: AbstractControl): { [key: string]: any } | null => {
      if (!this.formSetting.formObject) {
        return null;
      }

      const rawValue = this.formSetting.formObject.getRawValue();
      if (rawValue.newPassword !== rawValue.confirmNewPassword) {
        return {
          passwordSamed: true 
        };
      } else {
        return null;
      }
    };
  }

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

  ngOnDestroy(): void {
    // 取消表单值变化订阅
    if (this.formValueChangeSubscription) {
      this.formValueChangeSubscription.unsubscribe();
    }
    // 重置缓存状态
    this._isSubmitDisabledCache = true;
  }
  
}
