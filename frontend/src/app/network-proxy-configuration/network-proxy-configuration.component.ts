import { Component, OnInit } from '@angular/core';
import { AbstractControl, FormBuilder, FormGroup, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { PlxMessage } from "paletx"
import { ConfigApi } from '../api/config-api.service'
@Component({
  selector: 'app-network-proxy-configuration',
  templateUrl: './network-proxy-configuration.component.html',
  styleUrl: './network-proxy-configuration.component.css',
  standalone: false,
})
export class NetworkProxyConfigurationComponent implements OnInit {
  proxyForm: FormGroup;
  isLoading = false;
  mapping: { [key: string]: string } = {
    httpProxy: 'docker_http_proxy',
    httpsProxy: 'docker_https_proxy',
    noProxy: 'docker_no_proxy'
  };

  private static readonly URL_SAFE_CHARS = /^[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*$/;
  private static readonly NO_PROXY_SAFE_CHARS = /^[A-Za-z0-9\-._~*/,\s:]*$/;

  private static illegalCharsValidator(allowed: RegExp): ValidatorFn {
    return (control: AbstractControl): ValidationErrors | null => {
      const value = control.value;
      if (value === null || value === undefined || value === '') return null;
      return allowed.test(String(value)) ? null : { illegalChars: true };
    };
  }

  constructor(
    private fb: FormBuilder,
    private plxMessage: PlxMessage,
    private configApi: ConfigApi,
  ) {  
    this.proxyForm = this.fb.group({
      httpProxy: ['', [
        NetworkProxyConfigurationComponent.illegalCharsValidator(NetworkProxyConfigurationComponent.URL_SAFE_CHARS),
        Validators.pattern(/^(http:\/\/|https:\/\/).*$/),
        Validators.maxLength(256),
      ]],
      httpsProxy: ['', [
        NetworkProxyConfigurationComponent.illegalCharsValidator(NetworkProxyConfigurationComponent.URL_SAFE_CHARS),
        Validators.pattern(/^(http:\/\/|https:\/\/).*$/),
        Validators.maxLength(256),
      ]],
      noProxy: ['', [
        NetworkProxyConfigurationComponent.illegalCharsValidator(NetworkProxyConfigurationComponent.NO_PROXY_SAFE_CHARS),
        Validators.maxLength(1024),
      ]]
    });
  }

  ngOnInit(): void {
    this.loadProxyConfig();
  }

  loadProxyConfig(): void {
    this.configApi.getConfig().subscribe((response: any) => {
      if (response.code === 0) {
        const data = response.data;
        this.proxyForm.patchValue({
          httpProxy: data.docker_http_proxy,
          httpsProxy: data.docker_https_proxy,
          noProxy: data.docker_no_proxy
        });
      }
    });
  }

  onSubmit(): void {
    if (this.proxyForm.invalid) {
      this.plxMessage.show('error', { title: '请检查表单中的错误', isLightweight: true });
      return;
    }
  
    const controls = this.proxyForm.controls;
    const batchPayload: any[] = [];
  
    // 1. 收集所有被修改过的字段
    Object.keys(controls).forEach(key => {
      const control = controls[key];
      if (control.dirty) {
        batchPayload.push({
          key: this.mapping[key],
          value: control.value
        });
      }
    });
  
    if (batchPayload.length === 0) {
      this.plxMessage.show('info', { title: '未检测到内容修改', isLightweight: true });
      return;
    }
  
    // 2. 发送单次批量请求
    this.configApi.postConfig(batchPayload).subscribe((response: any) => {
      if (response.code === 0) {
        this.plxMessage.show('success', { title: '修改成功', isLightweight: true });
        // 重置整个表单状态为 pristine
        this.proxyForm.markAsPristine();
      } else {
        this.plxMessage.show('error', { title: `更新失败: ${response.msg}` });
      }
    });
  }

  hasError(controlName: string): boolean {
    const control = this.proxyForm.get(controlName);
    return control ? control.invalid && (control.dirty || control.touched) : false;
  }

  getErrorMessage(controlName: string): string {
    const control = this.proxyForm.get(controlName);
    if (control?.errors?.['illegalChars']) {
      return '包含非法字符，请仅输入字母/数字及常用符号';
    }
    if (control?.errors?.['pattern']) {
      return '代理地址必须以 http:// 或 https:// 开头';
    }
    if (control?.errors?.['maxlength']) {
      const max =
        controlName === 'noProxy' ? 1024 : 256;
      return `输入长度不能超过 ${max} 个字符`;
    }
    return '输入格式不正确';
  }
}
