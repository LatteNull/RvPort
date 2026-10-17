import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule} from '@angular/material/dialog';
import { MatButtonModule, } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { AuthApi } from '../api/auth-api.service'


@Component({
  selector: 'user-reset-component',
  templateUrl: './user-reset.component.html',
  styleUrls: ['./user-reset.component.css'],
  standalone:false,

})
export class UserResetComponent implements OnInit {
  form: FormGroup;
  hideOld = true;
  hideNew = true;
  hideConfirm = true;
  passwordStrength = '';

  constructor(
    private fb: FormBuilder,
    private authApi: AuthApi,
    private dialogRef: MatDialogRef<UserResetComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { username: string }
  ) {
    this.form = this.fb.group({
      oldPassword: ['', Validators.required],
      newPassword: ['', [
        Validators.required,
        Validators.minLength(8),
        Validators.maxLength(64),
        Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?])|(?=.*[a-z])(?=.*[A-Z])(?=.*\d)|(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?])|(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?])|(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?])[a-zA-Z\d!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/)
      ]],
      confirmPassword: ['', Validators.required],
    }, {
      validators: this.passwordMatchValidator,
      updateOn: 'change'
    });
  }

  passwordMatchValidator(form: FormGroup) {
    const newPwd = form.get('newPassword')?.value;
    const confirmPwd = form.get('confirmPassword')?.value;
    return newPwd === confirmPwd ? null : { passwordMismatch: true };
  }
  similar = true;

  ngOnInit(): void {
    this.form.get('newPassword')?.valueChanges.subscribe(value => {
      console.log("11",this.form.get('newPassword')?.value)
      this.form.get('newPassword')?.markAsTouched();
      this.updatePasswordStrength(value);
      // 当新密码变化时，重新验证确认密码
      if (this.form.get('newPassword')?.value == this.form.get('confirmPassword')?.value){
        this.similar = true;
      }else{
        this.similar = false;
      }
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



  updatePasswordStrength(password: string) {
    const strongRegex = /^(?![0-9a-z]+$)(?![0-9A-Z]+$)(?![0-9\W]+$)(?![a-z\W]+$)(?![a-zA-Z]+$)(?![A-Z\W]+$)[a-zA-Z0-9\W_]+$/;
    const mediumRegex = /^(?![a-z]*$)(?![A-Z]*$)(?![0-9]*$)(?![^a-zA-Z0-9]*$)|^(?=.{2,})(?=.*[a-zA-Z])(?=.*[0-9])|^(?=.{2,})(?=.*[a-zA-Z])(?=.*[^a-zA-Z0-9])|^(?=.{2,})(?=.*[0-9])(?=.*[^a-zA-Z0-9])/;
    this.passwordStrength = 'weak';
    if (password.length >= 8) {
      if (strongRegex.test(password)) {
        this.passwordStrength = 'strong';
      } else if (mediumRegex.test(password)) {
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
      const { username, oldPassword, newPassword } = this.form.value;
      console.log(this.form.value)
      const body = {
        username: this.data.username,
        admin_password: this.form.value.oldPassword,
        new_password: this.form.value.newPassword,
      };
      console.log("body",body)
      this.authApi.resetPassword(body).subscribe({
        next: (response: any) => {
          console.log("resetresponse",response)
          if (response['code'] === 0) {
            this.dialogRef.close();
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
