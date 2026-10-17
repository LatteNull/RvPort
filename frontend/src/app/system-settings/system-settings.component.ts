import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { FieldType, PlxMessage } from 'paletx';
import { HttpHeaders } from '@angular/common/http';
import { ConfigApi } from '../api/config-api.service'
import { Validators, ValidatorFn, AbstractControl,UntypedFormBuilder } from '@angular/forms';

@Component({
  selector: 'app-system-settings',
  templateUrl: './system-settings.component.html',
  styleUrl: './system-settings.component.css',
  standalone:false,
})
export class SystemSettingsComponent implements OnInit, OnDestroy{
  formSetting:any;
  data:any;
  private formValueChangeSubscription: any;
  private _isSubmitDisabledCache: boolean = true; // 缓存按钮禁用状态，避免每次变更检测时重复计算

  constructor(
    private configApi: ConfigApi,
    private plxMessage: PlxMessage,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.formSetting = this.initFormSetting();

    const url = '/action/config';
    const headers = new HttpHeaders({
      "Content-Type": 'application/json'
    });
    this.configApi.getConfig({ headers }).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          this.data = this.createdata(response.data)
          let data = response.data
          this.formSetting.formObject.patchValue({
            max_online_users: data.max_online_users,
            session_timeout: data.session_timeout,
            password_timeout:data.password_timeout,
            max_password_failed:data.max_password_failed,
            lock_time:data.lock_time,
            task_per_user:data.task_per_user,
            log_save_time:data.log_save_time
          })
          // 数据加载完成后，初始化按钮状态并开始监听表单变化
          this._isSubmitDisabledCache = this.calculateSubmitDisabled();
          this.subscribeToFormChanges();
        }
      },
    });
  }

  ngOnDestroy(): void {
    // 取消表单值变化订阅
    if (this.formValueChangeSubscription) {
      this.formValueChangeSubscription.unsubscribe();
    }
    // 重置缓存状态
    this._isSubmitDisabledCache = true;
  }

  /**
   * 订阅表单值变化，以便实时更新按钮状态
   */
  subscribeToFormChanges(): void {
    if (this.formSetting && this.formSetting.formObject) {
      this.formValueChangeSubscription = this.formSetting.formObject.valueChanges.subscribe(() => {
        // 只在表单值变化时重新计算按钮状态
        this._isSubmitDisabledCache = this.calculateSubmitDisabled();
        if (this.cdr) {
          this.cdr.detectChanges();
        }
      });
    }
  }

  /**
   * 计算按钮禁用状态（只在表单值变化时调用，避免在变更检测时重复计算）
   */
  private calculateSubmitDisabled(): boolean {
    if (!this.formSetting || !this.formSetting.formObject) {
      return true;
    }

    // 检查表单验证是否通过
    const isValid = this.formSetting.validateFields();
    if (!isValid) {
      return true;
    }

    // 检查表单是否被修改
    if (!this.data) {
      return true;
    }

    const currentValue = this.formSetting.formObject.value;
    const hasChanges = Object.keys(currentValue).some(key => {
      return String(currentValue[key]) !== String(this.data[key]);
    });

    // 只有当表单验证通过且有修改时，按钮才启用
    return !hasChanges;
  }

  /**
   * 使用缓存值，避免在每次变更检测时重复计算，提升性能
   */
  get isSubmitDisabled(): boolean {
    return this._isSubmitDisabledCache;
  }

  createdata(values:any){
    const body_result: { [key: string]: any } = {};
    body_result["max_online_users"] = values.max_online_users;
    body_result["session_timeout"] = values.session_timeout;
    body_result["password_timeout"] = values.password_timeout;
    body_result["max_password_failed"] = values.max_password_failed;
    body_result["lock_time"] = values.lock_time;
    body_result["task_per_user"] = values.task_per_user;
    body_result["log_save_time"] = values.log_save_time;
    return body_result
  }

  submit() {
    const isValid = this.formSetting.validateFields();
    if (!isValid) return;

    const value = this.formSetting.formObject.value;

    // 构造批量请求体
    const requestBodies = Object.entries(value)
      .filter(([key, val]) => String(val) !== String(this.data[key]))
      .map(([key, val]) => ({
        key: key,
        value: String(val)
      }));

    if (requestBodies.length === 0) {
      this.plxMessage.show('info', { title: '未检测到内容修改' });
      return;
    }

    this.configApi.postConfig(requestBodies).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          this.plxMessage.show('success', { title: '修改成功', isLightweight: true });
          // 同步本地数据
          this.data = this.createdata(value);
          this._isSubmitDisabledCache = this.calculateSubmitDisabled();
        } else {
          this.plxMessage.show('error', { title: `修改失败: ${response.msg}` });
        }
      }
    });
  }

  initFormSetting() {
    return {
      isShowHeader: false,
      componentClass: 'col-4',
      labelClass:'col-3',
      // fieldWidth: '800px',
      labelWidth: '180px',
      fieldSet: [
        {
          group: '系统设置',
          fields: [
            {
              name: 'max_online_users',
              label: '最大在线用户	',
              type: FieldType.STRING,
              //width: "400px",
              labelStyle: {
                'white-space': 'nowrap',
                'min-width': '180px',
                'flex-shrink': '0',
                'overflow': 'hidden',
                'text-overflow': 'ellipsis',
                'color': 'red',
              },
              required:true,
              tail: `<span style="float: left; width: 100%;">${'（1-20，默认值：10）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.max(20),
                Validators.min(1)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "最大在线用户设置：1-20",
                min: "最大在线用户设置：1-20",
              },
            },
            {
              name: 'session_timeout',
              label: '会话超时时间（分钟）',
              type: FieldType.STRING,
              //width: "400px",
              required:true,
              labelStyle: {
                'white-space': 'nowrap',
                'min-width': '180px',
                'flex-shrink': '0',
                'color': 'red',
              },
              tail: `<span>${'（10-10080，默认值：30）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(10),
                Validators.max(10080)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "会话超时时间设置:10-10080",
                min: "会话超时时间设置:10-10080",
              },
            },
            {
              name: 'password_timeout',
              label: '密码有效期（天）',
              type: FieldType.STRING,
              //width: "400px",
              required:true,
              tail: `<span>${'（0-360，默认值：0（永久））'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(0),
                Validators.max(360)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "密码有效期（天）：0-360",
                min: "密码有效期（天）：0-360",
              },
            },
            {
              name: 'max_password_failed',
              label: '密码错误锁定次数',
              type: FieldType.STRING,
              //width: "400px",
              required:true,
              tail: `<span>${'（3-10，默认值：5）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(3),
                Validators.max(10)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "密码错误锁定次数：3-10",
                min: "密码错误锁定次数：3-10",
              },
            },
            {
              name: 'lock_time',
              label: '锁定时间（分钟）',
              type: FieldType.STRING,
              required: true,
              //width:"400px",
              tail: `<span>${'（3-1440，默认值：3）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(3),
                Validators.max(1440)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "锁定时间（分钟）：3-1440",
                min: "锁定时间（分钟）：3-1440",
              },
            },
            {
              name: 'task_per_user',
              label: '每用户可创建最大任务数',
              type: FieldType.STRING,
              required: true,
              //width:"400px",
              tail: `<span>${'（20-100，默认值：30，迁移任务数不超过此值）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(20),
                Validators.max(100)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "每用户最大任务数量：20-100",
                min: "每用户最大任务数量：20-100",
              },
            },
            {
              name: 'log_save_time',
              label: '保存日志时长（天）',
              type: FieldType.STRING,
              required: true,
              //width:"400px",
              tail: `<span>${'（31-90，默认值：31）'}</span>`,
              validators: [
                Validators.pattern(/^\d+$/),
                Validators.min(31),
                Validators.max(90)
              ],
              validateInfos: {
                pattern: "请输入数字",
                max: "保存日志时长：31-90",
                min: "保存日志时长：31-90",
              },
            },
          ]
        },
      ]
    };
  }

}
