import { Component,Input, OnInit,ViewChild, TemplateRef } from '@angular/core';
import { interval, Subscription, forkJoin, of } from 'rxjs';
import { PlxMessage,PlxModal,ModalDismissReasons, FieldType } from 'paletx';
import { Validators, ValidatorFn, AbstractControl, FormBuilder, FormGroup } from '@angular/forms';
import { catchError } from 'rxjs/operators';
import { MatDialog } from '@angular/material/dialog';
import { UserResetComponent } from '../user-reset/user-reset.component';
import { UserModifyComponent } from '../user-modify/user-modify.component';
import { UserApi } from '../api/user-api.service'
import { AuthApi } from '../api/auth-api.service'
@Component({
  selector: 'app-user-management',
  templateUrl: './user-management.component.html',
  styleUrl: './user-management.component.css',
  standalone:false,
})
export class UserManagementComponent implements OnInit{
  rootLabel: any;
  data: Array<any> =[];
  columns: Array<any> = [];
  initOpen: any;
  rowData:any;
  CurrentUser:any;
  CurrentRole:any;
  usernameMap:Array<any> = [];
  create_formSetting:any;
  create_modal:any;
  modals:Array<any> = [];

  @ViewChild('create_content') create_content: any;

  modify_formSetting:any;
  modify_modal:any;
  @ViewChild('modify_content') modify_content: any;

  reset_formSetting:any;
  reset_modal:any;
  @ViewChild('reset_content') reset_content: any;

  delete_formSetting:any;
  delete_modal:any;

  @ViewChild('delete_content') delete_content: any;

  @ViewChild('operationTemplate', {static: true}) public operationTemplate!: TemplateRef<any>;
  @ViewChild('rowTemplate', {static: true}) public rowTemplate!: TemplateRef<any>;

  subscription!: Subscription;
  constructor(
    private userApi: UserApi,
    private authApi: AuthApi,
    private modalService: PlxModal,
    private fb: FormBuilder,
    private dialog: MatDialog
  ) {
    this.CurrentRole = localStorage.getItem('userRole');
    this.CurrentUser = localStorage.getItem('user_name');
  }

  openUserResetDialog() {
    const dialogRef = this.dialog.open(UserResetComponent, {
      data: { username: this.rowData.user_name } // 传递数据
    });

    dialogRef.afterClosed().subscribe(result => {
      console.log('对话框关闭', result);
    });
  }
  calcTableHeight(): string {
    const windowHeight = window.innerHeight;
    const otherElementsHeight = 200;
    return `${windowHeight - otherElementsHeight}px`;
  }

  private passwordPattern = /^(?![0-9a-z]+$)(?![0-9A-Z]+$)(?![0-9\W]+$)(?![a-z\W]+$)(?![a-zA-Z]+$)(?![A-Z\W]+$)[a-zA-Z0-9\W_]+$/;
  private usernamePattern = /^[a-zA-Z][a-zA-Z0-9_-]+$/;
  ngOnInit(): void {

    console.log("CurrentUser",this.CurrentUser);
    console.log("CurrentRole",this.CurrentRole);
    this.getuser();
    this.columns = this.createColumns();
    this.create_formSetting = this.create_initFormSetting();
    this.modify_formSetting = this.modify_initFormSetting();
    this.reset_formSetting = this.reset_initFormSetting();
    this.delete_formSetting = this.delete_initFormSetting();

  }


  get newPassword() { return this.reset_formSetting.formObject.value.newPassword; }
  get confirmPassword() { return this.reset_formSetting.formObject.value.confirmPassword; }


  ngAfterViewInit(){
    console.log("validators",this.reset_formSetting);
  }
  ngOnChanges() {

  }
  createColumns() {
    return [
      {
        key: 'user_name',
        title: '用户名',
        show: true,
      },
      {
        key: 'role',
        title: '角色',
        show: true,
        contentType: 'template',
        template: this.rowTemplate,
        showInDetail: false,

      },
      {
        key: 'operation',
        title: '操作',
        show: true,
        contentType: 'template',
        template: this.operationTemplate,
        showInDetail: false,
      },
    ];
  }

  getuser() {
    this.userApi.getUserList().subscribe({
      next: (response: any) => {
        if (response.code == 0){
          for (const user of response.data) {
            this.addData(user)
            this.usernameMap.push(user.user_name)
          }
        }
      },
    });
  }
  addData(user: any) {
    this.data = this.data.concat([{
      role:user.role,
      status:user.status,
      user_id:user.user_id,
      user_name:user.user_name
    }])
  }
  // openUserCreateDialog() {
  //   const dialogRef = this.dialog.open(UserCreateComponent, {
  //     data: { username: this.CurrentUser} // 传递数据
  //   });

  //   dialogRef.afterClosed().subscribe(result => {
  //     this.data = []
  //     this.getuser()
  //     console.log('对话框关闭', result);
  //   });
  // }
  create_user(){
    // this.openUserCreateDialog()
    this.create_modal = this.modalService.open(this.create_content);
    this.create_modal.isOpen = true;
  }
  formErrors = {
    username: '',
    password: '',
    admin_password: ''
  };

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

  create_submit() {
    const isValid = this.create_formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.create_formSetting.formObject.value);
      let Form = this.create_formSetting.formObject.value;
      const body = {
        user_name: Form.username,
        admin_password: Form.previousPassword,
        password: Form.newPassword,
        role:Form.role,
      };
      console.log("createbody",body)
      this.userApi.addUser(body).subscribe({
        next: (response: any) => {
          console.log("createresponse",response)
          if (response['code'] === 0) {
            //this.plxMessageService.success("新用户创建成功", "");
            this.data = []
            this.getuser()
            if (this.create_modal) {
              this.create_modal.isOpen = false
              this.create_modal.close();
            }

          } else if(response['code'] == -1 ){
            const errorTexts = this.handleErrorResponse(response);
            alert(errorTexts);
          }
        },
      });
    }
  }
  create_cancel(){
    this.create_modal.isOpen = false
    this.create_modal.close();
  }
  openUserModifyDialog() {
    const dialogRef = this.dialog.open(UserModifyComponent, {
      data: { username: this.rowData.user_name} // 传递数据
    });

    dialogRef.afterClosed().subscribe(result => {
      console.log('对话框关闭', result);
    });
  }
  modify(rowData:any) {
    this.rowData = rowData;
    this.openUserModifyDialog()
    // console.log("rowData",this.rowData)
    // this.modify_modal = this.modalService.open(this.modify_content);
    // this.modify_modal.isOpen = true
    // this.modify_formSetting = this.modify_initFormSetting()
  }
  modify_submit(){
    const isValid = this.modify_formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.modify_formSetting.formObject.value);
      let modifyPasswordFormValue = this.modify_formSetting.formObject.value;
      const body = {
        username: this.CurrentUser,
        old_password: modifyPasswordFormValue.previousPassword,
        new_password: modifyPasswordFormValue.newPassword,
      };
      console.log("body",body)
      this.authApi.modifyPassword(body).pipe(catchError((error:any) => {
        console.error('组件内静默处理错误', error);
        return of(null);
      })).subscribe({
        next: (response: any) => {
          console.log("createresponse",response)
          if (response['code'] === 0) {
            //this.plxMessageService.success("密码修改成功", "");
            if (this.modify_modal) {
              this.modify_modal.isOpen = false;
              this.modify_modal.close();
            }
          } else if(response['code'] == -1 ){
            const errorTexts = this.handleErrorResponse(response);
            alert(errorTexts);
          }
        },
      });
    }
  }

  modify_cancel(){
    this.modify_modal.isOpen = false;
    this.modify_modal.close();
  }

  checkPasswordSame(compareField: string):ValidatorFn{
    return (control: AbstractControl): { [key: string]: any } | null => {
      if (!control.parent) {
        return null;
      }
      const compareControl = control.parent.get(compareField);
      if (!compareControl) {
        return null;
      }
      // 当目标字段变化时触发当前字段的校验
      if (compareControl.value !== control.value) {
        return { passwordSamed: true };
      }
      return null;
    };
  }

  // public nameExistsValidate(): ValidatorFn {
  //   return (control: AbstractControl): { [key: string]: any } => {
  //     if (control.value !== undefined && !this.usernameMap) {
  //       return {};
  //     }
  //     if (this.usernameMap.includes(control.value)) {
  //       return {
  //         nameExists: true
  //       };
  //     }
  //     return {};
  //   };
  // }

  create_initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-3',
      componentClass: 'col-sm-8',
      labelWidth: '150px',
      fieldWidth: '360px',
      srcObj: {
        "role":"normal",
      },
      fieldSet: [
        {
          fields: [
            {
              name: 'role',
              label: '新建用户角色',
              type: FieldType.RADIO,
              required: true,
              valueSet: [
                {
                  label: "管理员",
                  value: "admin"
                },
                {
                  label: "普通用户",
                  value: "normal"
                }
              ],
              width: "400px"
            },
            {
              name: 'username',
              label: "用户名",
              type: FieldType.STRING,
              placeholder: "请输入用户名",
              required: true,
              validators: [
                // this.nameExistsValidate(),
                Validators.maxLength(32),
                Validators.minLength(5),
                Validators.pattern(this.usernamePattern),
              ],
              validateInfos: {
                // nameExists: '名称已经存在。',
                maxlength:"用户名长度不能超过32个字符",
                minlength:"用户名长度不能少于5个字符",
                pattern: "首字符必须是字母（大小写均可）后续字符可以是字母、数字、下划线 _ 或短横线 -",
              },
            },
            {
              name: 'previousPassword',
              label: "管理员密码",
              type: FieldType.PASSWORD,
              placeholder: "请输入管理员密码",
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
                minlength:"密码长度不能少于8个字符",
                maxlength:"密码长度不能超过64个字符",
                pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符",
              },
              required: true,
              // 回调函数：添加值变化监听
              callback: (values: any, $event: any, controls: any) => {
                const confirmControl = this.create_formSetting.formObject?.get('confirmNewPassword');
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
              required: true,
              passwordSwitch: true,
              validators: [
                this.checkPasswordSame('newPassword'),
                //this.createcheckPasswordSame(),
                // Validators.pattern(this.passwordPattern),
                // Validators.minLength(8),
                // Validators.maxLength(64)
              ],
              validateInfos: {
                // pattern: "长度为8-64，首字符必须是字母（大小写均可）后续字符可以是字母、数字、下划线 _ 或短横线 -  ",
                passwordSamed: "两次输入的密码不一致",  // 两次输入的密码不一致的错误信息
              },
            }
          ]
        }
      ]
    };
  }
  delete_initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-3',
      componentClass: 'col-sm-8',
      labelWidth: '150px',
      fieldWidth: '200px',
      fieldSet: [
        {
          fields: [
            {
              name: 'admin_password',
              label: '管理员密码',
              type: FieldType.PASSWORD,
              required:true,
              passwordSwitch: true,
            },
          ]
        },
      ]
    };
  }
  reset_initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-3',
      componentClass: 'col-sm-8',
      labelWidth: '120px',
      fieldWidth: '360px',
      fieldSet: [
        {
          fields: [
            {
              name: 'admin_password',
              label: '管理员密码',
              type: FieldType.PASSWORD,
              required:true,
              passwordSwitch: true,
            },
            {
              name: 'newPassword',
              label: '新密码',
              type: FieldType.PASSWORD,
              required:true,
              passwordSwitch: true,
              validators: [
                Validators.pattern(this.passwordPattern),
                Validators.minLength(8),
                Validators.maxLength(64),
              ],
              validateInfos: {
                minlength:"密码长度不能少于8个字符",
                maxlength:"密码长度不能超过64个字符",
                pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符",
              },
              // 回调函数：添加值变化监听
              callback: (values: any, $event: any, controls: any) => {
                const confirmControl = this.reset_formSetting.formObject?.get('confirmNewPassword');
                if (confirmControl) {
                  // 触发确认密码控件的重新验证
                  confirmControl.updateValueAndValidity();
                }
              }
            },
            {
              name: 'confirmNewPassword',
              label: '确认密码',
              type: FieldType.PASSWORD,
              required:true,
              passwordSwitch: true,
              validators: [this.checkPasswordSame('newPassword')],
              validateInfos: {
                passwordSamed: "两次输入的密码不一致",  // 两次输入的密码不一致的错误信息
              },
            },
          ]
        },
      ]
    };
  }
  modify_initFormSetting() {
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
                minlength:"密码长度不能少于8个字符",
                maxlength:"密码长度不能超过64个字符",
                pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符",
              },
              required: true,
              // 回调函数：添加值变化监听
              callback: (values: any, $event: any, controls: any) => {
                const confirmControl = this.modify_formSetting.formObject?.get('confirmNewPassword');
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
              required: true,
              passwordSwitch: true,
              validators: [
                this.checkPasswordSame('newPassword'),  // 确保两次输入的密码一致
                // Validators.pattern(this.passwordPattern),
                // Validators.minLength(8),
                // Validators.maxLength(64)
              ],
              validateInfos: {
                // pattern: "密码必须同时包含大写字母、小写字母、数字、特殊符号等四项中的至少三项, 且不得有超过2个连续的相同字符",
                passwordSamed: "两次输入的密码不一致",
              },
            }
          ]
        }
      ]
    };
  }

  ngOnDestroy(): void {
    this.modals = [this.delete_modal,this.create_modal,this.reset_modal,this.modify_modal]
    this.modals.forEach(modal => {
      try {
        if (modal?.isOpen) {
          modal.close();
        }
      } catch (e) {
        console.error('关闭对话框失败', e);
      }
    })

    this.modalService.destroyModalInstance();
  }

  deleteuser(rowData:any) {
    this.rowData = rowData;
    this.delete_modal = this.modalService.open(this.delete_content);
    this.delete_modal.isOpen = true
    //console.log("modalstate",this.delete_modal)
  }

  delete_submit() {
    const isValid = this.delete_formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.delete_formSetting.formObject.value);
      let modifyPasswordFormValue = this.delete_formSetting.formObject.value;
      const body = {
        admin_password: modifyPasswordFormValue.admin_password,
      };
      console.log(`/action/user/${this.rowData.user_id}`)
      console.log("deletebody",body)
      this.userApi.deleteUser(this.rowData.user_id, body).subscribe({next: (response: any) => {
        console.log("deleteresponse",response)
          if (response.msg === 'ok') {
            console.log("rowdata",this.rowData)
            this.data = this.data.filter(item => item.user_id !== this.rowData.user_id);
            if (this.delete_modal) {
              this.delete_modal.close();
              this.delete_modal.isOpen = false
            }
          } else {
            alert(response.msg);
          }
        },
      });
    }
  }

  delete_cancel(): void {
    this.delete_modal.close();
    this.delete_modal.isOpen = false
  }

  //普通用户
  resetpassword(rowData:any) {
    this.rowData = rowData;
    this.openUserResetDialog();
    // this.reset_modal = this.modalService.open(this.reset_content);
    // this.reset_modal.isOpen = true;
    // console.log("resetmodal",this.reset_formSetting);

  }
  reset_submit(){
    const isValid = this.reset_formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.reset_formSetting.formObject.value);
      let modifyPasswordFormValue = this.reset_formSetting.formObject.value;
      const body = {
        username: this.rowData.user_name,
        admin_password: modifyPasswordFormValue.admin_password,
        new_password: modifyPasswordFormValue.newPassword,
      };
      console.log("body",body)
      this.authApi.resetPassword(body).subscribe({
        next: (response: any) => {
          console.log("resetresponse",response)
          if (response['code'] === 0) {
            if (this.reset_modal) {
              this.reset_modal.isOpen = false;
              this.reset_modal.close();
            }
          } else if(response['code'] == -1){
            const errorTexts = this.handleErrorResponse(response);
            alert(errorTexts);
          }
        },
      });
    }
  }
  reset_cancel(): void {
    this.reset_modal.isOpen = false;
    this.reset_modal.close();
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

}

