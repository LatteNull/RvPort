
import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule} from '@angular/material/dialog';
import { MatButtonModule, } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Router } from '@angular/router';
import { PlxMessage } from 'paletx';
import { AuthApi } from '../api/auth-api.service'


@Component({
  selector: 'app-user-modify',
  templateUrl: './user-modify.component.html',
  styleUrl: './user-modify.component.css',
  standalone:false,
})
export class UserModifyComponent implements OnInit{
  form: FormGroup;
  hideOld = true;
  hideNew = true;
  hideConfirm = true;
  passwordStrength = '';
  similar = true;
  passwordRuleErrors: string[] = [];

  private static readonly DIGIT_REGEX = /\d/;
  private static readonly LOWERCASE_REGEX = /[a-z]/;
  private static readonly UPPERCASE_REGEX = /[A-Z]/;
  private static readonly SPECIAL_CHAR_REGEX = /[^a-zA-Z0-9]/;

  private static readonly STRONG_PASSWORD_REGEX = /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[^a-zA-Z0-9])|(?=.*\d)(?=.*[a-z])(?=.*[A-Z])|(?=.*\d)(?=.*[a-z])(?=.*[^a-zA-Z0-9])|(?=.*\d)(?=.*[A-Z])(?=.*[^a-zA-Z0-9])|(?=.*[a-z])(?=.*[A-Z])(?=.*[^a-zA-Z0-9])/;
  private static readonly MEDIUM_PASSWORD_REGEX = /^(?=.*\d)(?=.*[a-z])|(?=.*\d)(?=.*[A-Z])|(?=.*\d)(?=.*[^a-zA-Z0-9])|(?=.*[a-z])(?=.*[A-Z])|(?=.*[a-z])(?=.*[^a-zA-Z0-9])|(?=.*[A-Z])(?=.*[^a-zA-Z0-9])/;

  constructor(
    private fb: FormBuilder,
    private authApi: AuthApi,
    private dialogRef: MatDialogRef<UserModifyComponent>,
    private router: Router,
    private plxMessageService: PlxMessage,
    @Inject(MAT_DIALOG_DATA) public data: { username: string }
  ) {
    this.form = this.fb.group({
      oldPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(8),Validators.maxLength(64)]],
      confirmPassword: ['', Validators.required],
    }, { validators: [
      this.passwordMatchValidator.bind(this),
      this.passwordRulesValidator.bind(this)
    ]});
  }

  ngOnInit(): void {

    this.form.get('newPassword')?.valueChanges.subscribe((value: string) => {
      if (this.form.get('newPassword')?.value == this.form.get('confirmPassword')?.value){
        this.similar = true;
      }
      else{
        this.similar = false;
      }
      this.updatePasswordStrength(value);
      // 触发密码规则验证
      this.passwordRulesValidator(this.form);
      // 当新密码变化时，重新验证确认密码
      if (this.form.get('confirmPassword')?.value) {
        this.form.get('confirmPassword')?.updateValueAndValidity();
        this.passwordMatchValidator(this.form)
      }
    });

    this.form.get('confirmPassword')?.valueChanges.subscribe(() => {
      if (this.form.get('newPassword')?.value == this.form.get('confirmPassword')?.value){
        this.similar = true;
      }
      else{
        this.similar = false;
      }
      // 确认密码变化时触发验证
      this.form.updateValueAndValidity();
      this.passwordMatchValidator(this.form)
    });

  }

  passwordRulesValidator(form: FormGroup): { [key: string]: any } | null {
    const newPwd = form.get('newPassword')?.value;
    const errors: string[] = [];

    if (!newPwd) {
      this.passwordRuleErrors = [];
      return null;
    }

    if (newPwd.length < 8) {
      errors.push('密码长度应不低于8位');
    } else if (newPwd.length > 64) {
      errors.push('密码长度应不高于64位');
    }

    const hasDigit = UserModifyComponent.DIGIT_REGEX.test(newPwd);
    const hasLowerCase = UserModifyComponent.LOWERCASE_REGEX.test(newPwd);
    const hasUpperCase = UserModifyComponent.UPPERCASE_REGEX.test(newPwd);
    const hasSpecialChar = UserModifyComponent.SPECIAL_CHAR_REGEX.test(newPwd);

    const typeCount = [hasDigit, hasLowerCase, hasUpperCase, hasSpecialChar].filter(Boolean).length;

    if (typeCount < 3) {
      errors.push('密码必须包含数字、小写字母、大写字母和特殊符号这四项中至少三项');
    }

    // 更新错误信息
    this.passwordRuleErrors = errors;

    // 如果有错误，返回错误对象；否则返回null
    return errors.length > 0 ? { passwordRules: errors } : null;
  }

  passwordMatchValidator(form: FormGroup) {
    const newPwd = form.get('newPassword')?.value;
    const confirmPwd = form.get('confirmPassword')?.value;
    return newPwd === confirmPwd ? null : { passwordMismatch: true };
  }

  updatePasswordStrength(password: string): void {
    if (!password) {
      this.passwordStrength = '';
      return;
    }
    this.passwordStrength = 'weak';
    if (password.length >= 8) {
      if (UserModifyComponent.STRONG_PASSWORD_REGEX.test(password)) {
        this.passwordStrength = 'strong';
      } else if (UserModifyComponent.MEDIUM_PASSWORD_REGEX.test(password)) {
        this.passwordStrength = 'medium';
      }
    }
  }

  getStrengthLabel() {
    switch (this.passwordStrength) {
      case 'strong': return '强';
      case 'medium': return '中';
      case 'weak': return '弱';
      default: return '';
    }
  }
  // 错误码映射
  private  errorMessages = new Map<string, string>([
    ['user.name.duplicate','用户名已存在'],
    ['user.name.length.over', '用户名长度不能超过32个字符'],
    ['user.name.illegal.character', '用户名必须以字母开头，可包含字母、数字、_和-'],
    ['user.password.cannot.contains.username', '密码不能包含用户名'],
    ['user.password.is.weak', '密码强度不足'],
    [ 'user.password.illegal', '密码格式不符合要求'],
    ['New password cannot be the same as any of your last two passwords.','新密码不能与前两次使用过的密码相同'],
    ['Authentication failed.','密码认证失败'],
    ['More than 2 consecutive identical characters are not allowed.','不允许连续出现超过 2 个相同的字符'],

  ]);
  // 错误响应处理
  private handleErrorResponse(response: any): string {
    const messages = typeof response.msg === 'string'
      ? response.msg.split('\n').filter(Boolean)
      : Array.isArray(response.msg)
        ? response.msg
        : [response.msg?.toString() || '未知错误'];

    return messages
      .map((msg: string) => this.errorMessages.get(msg.trim()) || `${msg}`)
      .join('\n');
  }
  onSubmit() {
    if (this.form.valid) {
      console.log(this.form.value)
      const body = {
        username: this.data.username,
        old_password: this.form.value.oldPassword,
        new_password: this.form.value.newPassword,
      };
      console.log("body",body)
      this.authApi.modifyPassword(body).subscribe({
        next: (response: any) => {
          console.log("resetresponse",response)
          if (response['code'] === 0) {
            this.plxMessageService.success("密码修改成功", "");
            this.dialogRef.close();
            // 密码修改成功后跳转到登录页面
            localStorage.clear();
            this.router.navigate(['/admin']);
          } else if(response['code'] == -1){
            const errorTexts = this.handleErrorResponse(response);
            alert(errorTexts);
          }
        },
      });
    }
  }

  onCancel() {
    this.dialogRef.close(null);
  }
}
