import { Component, ViewChild, OnInit, ChangeDetectorRef, ElementRef } from '@angular/core';
import { AuthApi } from '../api/auth-api.service';
import { PlxMessage, PlxModal } from 'paletx';
import { Router } from '@angular/router';
import { BaseLoginComponent } from '../base-login/base-login.component';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
  standalone: false,
})
export class LoginComponent extends BaseLoginComponent implements OnInit {
  @ViewChild('passwordInput') passwordInput!: ElementRef;
  constructor(
    authApi: AuthApi,
    plxMessageService: PlxMessage,
    modalService: PlxModal,
    router: Router,
    cdr: ChangeDetectorRef,
  ) {
    super(authApi, plxMessageService, modalService, router, cdr);
  }

  // 判断登录按钮是否应该被禁用
  get isLoginDisabled(): boolean {
    return !this.username || !this.username.trim() || !this.password || this.password.length < 8;
  }

  showToast(type: any, message: any){
    this.plxMessageService.show(type, {
      title: message,
      isLightweight: true
    });
  }

  focusPassword() {
    // 通过ViewChild获取的引用，将焦点设置到密码框
    this.passwordInput.nativeElement.focus();
  }

  onSubmit() {
    if (!this.username || !this.username.trim()){
      this.showToast("warning", '请输入用户名')
      return;
    }else if (!this.password || !this.password.trim()){
      this.showToast("warning", '请输入密码')
      return;
    }else if (this.password.length < 8){
      this.showToast("warning", '密码不得小于8字符')
      return;
    }
    this.performLogin()
  }


  // 实现抽象方法：执行登录API调用
  performLogin(): void {
    this.authApi.login(
      { username: this.username, password: this.password },
      { observe: 'response' }  // 添加这个选项来获取完整响应
    ).subscribe({
        next: (response: any) => {
          // 注意这里需要使用 response.body 来访问响应体
          if (response.body['code'] === 0) {
            // 登录成功之后 再存储takon信息
            const csrfToken = response.headers.get('X-Csrftoken');
            if (csrfToken) {
              localStorage.setItem('X-Csrftoken', csrfToken);
            }
            const userData = JSON.parse(response.body.msg); // 解析JSON字符串
            this.role = userData.role;
            localStorage.setItem('userRole', this.role);
            // 浏览器缓存为浏览器共享的数据
            localStorage.setItem('user_name', this.username);
            console.log("non-first-login");
            this.plxMessageService.success(
              "登录成功！",
              "上次于 "+userData.last_login+" 使用IP "+userData.last_login_ip+" 登录 "+this.formatLoginDuration(userData.last_login_duration)+
              "，距上一次登录期间有 "+userData.auth_failed+" 次登录失败。"
            );
            this.onLoginSuccess();
          } else if (response.body['code'] === 2) {
            this.plxMessageService.success(response.body['msg'], "")
            this.openWithoutDestroy(this.content2);
          } else {
            this.plxMessageService.error("登录失败", response.body['msg'])
          }
        },
        error: (response: any) => {
          console.log(response)
          this.plxMessageService.error("登录失败", response['error']['msg'])
        }
      });
  }

  // 实现抽象方法：登录成功后的跳转逻辑
  onLoginSuccess(): void {
    this.router.navigate(['/cardmodel']);
  }

  // 实现抽象方法：修改密码成功后的跳转逻辑
  onPasswordChangeSuccess(): void {
    this.router.navigate(['/login']);
  }

  // 实现抽象方法：mode方法的具体逻辑
  mode() {
    this.formSetting = this.initFormSetting();
  }
}
