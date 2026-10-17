import { Component, OnInit, ViewChild} from '@angular/core';
import { AgentManagementApi } from '../api/agent-management-api.service';
import { PlxModal, PlxMessage, FieldType } from 'paletx';
import { Validators, AbstractControl, ValidationErrors } from '@angular/forms';

// ---------------------------
// 表单校验器：非法字符/URL/模型名
// ---------------------------
function hasWhitespaceOrControlChars(value: string): boolean {
  // \s includes spaces/tabs/newlines; 0x00-0x1F and 0x7F are control chars
  return /[\s\x00-\x1F\x7F]/.test(value);
}

// 禁止 api_key / model 含空白或控制字符
function validateNoIllegalChars(control: AbstractControl): ValidationErrors | null {
  const value = (control.value ?? '') as string;
  if (!value) return null;
  if (hasWhitespaceOrControlChars(value)) {
    return { containsIllegalChars: true };
  }
  return null;
}

// base_url：必须 http/https，且禁止空白/控制字符
function validateHttpUrl(control: AbstractControl): ValidationErrors | null {
  const value = (control.value ?? '') as string;
  if (!value) return null;
  if (hasWhitespaceOrControlChars(value)) {
    return { invalidBaseUrl: true };
  }
  try {
    const url = new URL(value);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return { invalidBaseUrl: true };
    }
  } catch {
    return { invalidBaseUrl: true };
  }
  return null;
}

// model：限制为常见字符集（避免奇怪的换行/空白/不可预期字符）
function validateModelChars(control: AbstractControl): ValidationErrors | null {
  const value = (control.value ?? '') as string;
  if (!value) return null;
  if (hasWhitespaceOrControlChars(value)) {
    return { invalidModel: true };
  }
  // 支持如 gpt-4o-mini / opus-4.6 / vendor/model 等
  if (!/^[A-Za-z0-9._\/-]+$/.test(value)) {
    return { invalidModel: true };
  }
  return null;
}

@Component({
  selector: 'app-agent-management',
  templateUrl: './agent-management.component.html',
  styleUrls: ['./agent-management.component.css'],
  standalone: false,
})
export class AgentManagementComponent implements OnInit {
  // 数据相关
  data: Array<any> = [];
  columns: Array<any> = [];
  selectedRow: any = null;
  
  // 弹窗相关
  create_modal: any;
  delete_modal: any;
  user_name: any;
  // 模板引用
  @ViewChild('create_content') create_content: any;
  @ViewChild('delete_content') delete_content: any;
  
  // 表单配置
  create_formSetting: any;
  delete_formSetting: any;
  apikeyCorrect: boolean = false;
  apikeyTesting: boolean = false;
  // 加载状态
  isLoading: boolean = false;
  // 当前用户角色
  CurrentRole: any;
  
  constructor(
    private agentApi: AgentManagementApi,
    private modalService: PlxModal,
    private plxMessage: PlxMessage
  ) {
    this.user_name = localStorage.getItem('user_name');
    this.CurrentRole = localStorage.getItem('userRole');
  }

  // 选中的API格式
  selectedApiFormat: 'openai' | 'cursor' = 'openai';

  // Cursor格式的固定Base URL
  private readonly CURSOR_BASE_URL = 'http://api.cursor.com/';

  // 保存原始的base_url值（用于切换回来时恢复）
  private originalBaseUrl: string = '';
  // 表单数据对象（plx-form会通过srcObj绑定）
  formData: any = {
    api_key: '',
    base_url: '',
    model: ''
  };
  ngOnInit(): void {
    this.getApiKeyList();
    this.columns = this.createColumns();
    this.create_formSetting = this.create_initFormSetting();
    this.delete_formSetting = this.delete_initFormSetting();
  }
  // 组件类中添加标志
  showForm: boolean = true;
  // 计算表格高度
  calcTableHeight(): string {
    const windowHeight = window.innerHeight;
    const otherElementsHeight = 300; // 标题、按钮、间隔等高度
    return `${windowHeight - otherElementsHeight}px`;
  }

  // 创建表格列 - 根据实际数据结构调整
  createColumns() {
    return [
      {
        key: 'api_key',
        title: 'API Key',
        show: true,
        width: '200px',
      },
      {
        key: 'user_name',
        title: '用户名',
        show: true,
        width: '100px',
      },
      {
        key: 'base_url',
        title: 'Base URL',
        show: true,
        width: '350px',
      },
      {
        key: 'model',
        title: '模型',
        show: true,
        width: '200px',
      },
      {
        key: 'is_default',
        title: '默认模型',
        show: true,
        width: '100px',
      },
      {
        key: 'is_model_default',
        title: '模型选中',
        show: true,
        width: '100px',
      },
    ];
  }

  // 获取API Key列表
  getApiKeyList() {
    this.isLoading = true;
    this.agentApi.getApiKeyList().subscribe({
      next: (response: any) => {
        console.log('获取API Key列表完整响应:', response);
        
        if (response && response.code === 0) {
          if (response.apikey_list && Array.isArray(response.apikey_list)) {
            // 只提取需要的字段
            this.data = response.apikey_list.map((item: any) => ({
              api_key_id: item.api_key_id || item.id || '',
              user_name: item.user_name || '',
              api_key: item.api_key + "****" || '',
              base_url: item.base_url || '',
              model: item.model || '默认模型',
              is_default: item.is_default ? "默认" : '',
              is_model_default: item.is_model_default ? "选中" : '',
              api_format: item.api_format || '',
              original_data: item
            }));

            console.log('处理后的数据:', this.data);
          } else {
            console.warn('apikey_list字段不存在或不是数组:', response);
            this.data = [];
            this.plxMessage.warning('数据格式错误：缺少apikey_list字段', "");
          }
        } else {
          const errorMsg = response?.msg || '获取数据失败';
          this.plxMessage.error('获取API Key列表失败: ', errorMsg); 
          this.data = [];
        }

        console.info('默认的api_key:', this.selectedRow);
        this.isLoading = false;
      },
      error: (error: any) => {
        console.error('获取API Key列表失败:', error);
        this.plxMessage.warning('获取API Key列表失败，请检查网络连接', "");
        this.isLoading = false;
        this.data = [];
      },
      complete: () => {
        this.isLoading = false;
      }
    });
  }

  checkboxCallback(isckecked:any, selectedData: any) {
      // 直接使用选中的行数据
      if (isckecked) {
        this.onRowSelect(selectedData[0]);
      } else {
        // 取消选中状态
        this.selectedRow = null;
        console.log('取消选中行：', selectedData[0]);
      }
    }
  // 行选择处理
  onRowSelect(row: any) {
    if (this.selectedRow === row) {
      this.selectedRow = null; // 取消选择
    } else {
      this.selectedRow = row; // 选择新行
    }
    console.log('选中的API Key：', this.selectedRow);
  }

  // 显示API Key（后端已截取前8位）
  getDisplayApiKey(apiKey: string): string {
    return apiKey + '****';
  }

  // 打开新建弹窗
  createApiKey() {
    this.create_modal = this.modalService.open(this.create_content);
    this.create_modal.isOpen = true;
    this.apikeyCorrect = false;
    this.create_formSetting.fieldSet[0].fields = 
      this.create_formSetting.fieldSet[0].fields.map((field: any) => ({
        ...field,
        disabled: false
      }));
  }
  // 测试api_key 是否可以正常访问
  async api_key_test() {
    // 检查表单是否已初始化
    if (!this.create_formSetting || typeof this.create_formSetting.validateFields !== 'function') {
      this.plxMessage.warning('表单尚未初始化，请稍后重试', '');
      return;
    }

    const isValid = this.create_formSetting.validateFields();
    if (!isValid) return;

    this.apikeyTesting = true;
    const formValue = this.create_formSetting.formObject?.value || {};
    const api_key = formValue.api_key?.trim();
    let base_url: string;
    if (this.selectedApiFormat === 'cursor') {
      base_url = this.CURSOR_BASE_URL;
    } else {
      base_url = formValue.base_url?.trim() || '';
    }
    const model = formValue.model?.trim();

    // 简单非空校验
    if (!api_key || !base_url || !model) {
      this.plxMessage.warning('请填写完整的 API 配置', '');
      this.apikeyTesting = false;
      return;
    }

    // 非法字符校验
    if (hasWhitespaceOrControlChars(api_key)) {
      this.plxMessage.warning('API Key包含非法字符（禁止空格/换行/控制字符）', '');
      this.apikeyTesting = false;
      return;
    }
    if (hasWhitespaceOrControlChars(base_url)) {
      this.plxMessage.warning('Base URL包含非法字符（禁止空格/换行/控制字符）', '');
      this.apikeyTesting = false;
      return;
    }
    try {
      const u = new URL(base_url);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') {
        this.plxMessage.warning('Base URL必须是 http/https 开头', '');
        this.apikeyTesting = false;
        return;
      }
    } catch {
      this.plxMessage.warning('Base URL格式不正确，请输入正确的URL', '');
      this.apikeyTesting = false;
      return;
    }
    // 部分模型名称可能包含路径（例如 "vendor/model"），因此允许 "/"
    if (hasWhitespaceOrControlChars(model) || !/^[A-Za-z0-9._\/-]+$/.test(model)) {
      this.plxMessage.warning('模型名称包含非法字符', '');
      this.apikeyTesting = false;
      return;
    }

    const body = {
      api_key: api_key,
      base_url: base_url,
      model: model,
      api_format: this.selectedApiFormat
    }
    this.agentApi.TestApiKey(body).subscribe({
      next: (response: any) => {
      
        if (response && response.code === 0) {
          this.apikeyCorrect = true;
          this.apikeyTesting = false;
          console.log('测试通过！:', this.data);
          this.plxMessage.success('配置有效，测试通过！', '');
          // 测试通过之后，不允许改动api_key
          this.create_formSetting.fieldSet[0].fields = 
            this.create_formSetting.fieldSet[0].fields.map((field: any) => ({
              ...field,
              disabled: true
            }));
        } else {
          const errorMsg = response?.msg || '测试失败';
          this.plxMessage.error('测试Api Key失败: ', errorMsg); 
          this.apikeyCorrect = false;
          this.apikeyTesting = false;
        }
      },
      error: (error: any) => {
        console.error('测试API Key失败:', error);
        this.plxMessage.warning('API Key测试失败，请检查网络连接', "");
        this.apikeyCorrect = false;
        this.apikeyTesting = false;
      },
    });
  }
  // 当API格式改变时的处理
  onApiFormatChange() {
    console.log('API格式切换为:', this.selectedApiFormat);

    // 不要重新创建整个 formSetting，只更新特定字段的属性
    if (this.create_formSetting && this.create_formSetting.fieldSet && this.create_formSetting.fieldSet[0]) {
      const fields = this.create_formSetting.fieldSet[0].fields;

      // 找到 base_url 字段并更新其属性
      const baseUrlField = fields.find((f: any) => f.name === 'base_url');
      if (baseUrlField) {
        if (this.selectedApiFormat === 'cursor') {
          // 切换到Cursor格式：保存当前base_url，然后禁用该字段
          if (this.create_formSetting.formObject) {
            this.originalBaseUrl = this.create_formSetting.formObject.value?.base_url || '';
          }
          baseUrlField.disabled = true;
          baseUrlField.customClass = 'cursor-fixed-url';
          baseUrlField.placeholder = this.CURSOR_BASE_URL;

          // 设置表单值为固定值
          if (this.create_formSetting.formObject && this.create_formSetting.formObject.get) {
            const baseControl = this.create_formSetting.formObject.get('base_url');
            if (baseControl) {
              baseControl.setValue(this.CURSOR_BASE_URL);
            }
          }
        } else {
          // 切换到OpenAI格式：恢复之前保存的base_url，启用该字段
          baseUrlField.disabled = false;
          baseUrlField.customClass = '';
          baseUrlField.placeholder = '例如：https://open.bigmodel.cn/api/coding/paas/v4';

          // 恢复原始值
          if (this.create_formSetting.formObject && this.create_formSetting.formObject.get) {
            const baseControl = this.create_formSetting.formObject.get('base_url');
            if (baseControl) {
              baseControl.setValue(this.originalBaseUrl);
            }
          }
        }
      }
    }

    // 重置API Key正确性状态
    this.apikeyCorrect = false;
  }

  // 新建提交
  create_submit() {
    // 检查表单是否已初始化
    if (!this.create_formSetting || typeof this.create_formSetting.validateFields !== 'function') {
      this.plxMessage.warning('表单尚未初始化，请稍后重试', '');
      return;
    }

    const isValid = this.create_formSetting.validateFields();
    this.apikeyCorrect = false;
    if (isValid) {
      const formValue = this.create_formSetting.formObject?.value || {};

      // 统一取值：cursor 模式下 base_url 固定，避免 disabled 字段取不到导致校验绕过
      const api_key = formValue.api_key ?? '';
      const model = formValue.model ?? '';
      const base_url =
        this.selectedApiFormat === 'cursor' ? this.CURSOR_BASE_URL : (formValue.base_url ?? '');

      // 非法字符校验
      if (String(api_key).length === 0 || String(base_url).length === 0 || String(model).length === 0) {
        this.plxMessage.warning('请填写完整的 API 配置', '');
        return;
      }
      if (hasWhitespaceOrControlChars(String(api_key))) {
        this.plxMessage.warning('API Key包含非法字符（禁止空格/换行/控制字符）', '');
        return;
      }
      if (hasWhitespaceOrControlChars(String(base_url))) {
        this.plxMessage.warning('Base URL包含非法字符（禁止空格/换行/控制字符）', '');
        return;
      }
      try {
        const u = new URL(String(base_url));
        if (u.protocol !== 'http:' && u.protocol !== 'https:') {
          this.plxMessage.warning('Base URL必须是 http/https 开头', '');
          return;
        }
      } catch {
        this.plxMessage.warning('Base URL格式不正确，请输入正确的URL', '');
        return;
      }
      if (hasWhitespaceOrControlChars(String(model)) || !/^[A-Za-z0-9._\/-]+$/.test(String(model))) {
        this.plxMessage.warning('模型名称包含非法字符', '');
        return;
      }

      const body = {
        user_name: this.user_name,
        api_key: String(api_key).trim(),
        base_url: String(base_url).trim(),
        model: String(model).trim(),
        api_format: this.selectedApiFormat,
      };

      console.log('创建API Key请求体:', body);
      
      this.agentApi.addApiKey(body).subscribe({
        next: (response: any) => {
          console.log('创建API Key响应:', response);
          
          // 根据实际情况处理响应
          if (response && (response.code === 0 || response.success || response.id)) {
            // 清空表单
            this.create_formSetting.formObject.reset();
            // 刷新列表
            this.getApiKeyList();
            // 关闭弹窗
            if (this.create_modal) {
              this.create_modal.isOpen = false;
              this.create_modal.close();
            }
            this.plxMessage.success('API Key 添加成功', "");
          } else {
            const errorMsg = response?.msg || '添加失败';
            this.plxMessage.warning('添加失败: ', errorMsg);
          }
        },
        error: (error: any) => {
          console.error('添加API Key失败:', error);
          this.plxMessage.warning('添加API Key失败，请稍后重试', "");
        }
      });
    }
  }

  // 新建取消
  create_cancel() {
    if (this.create_formSetting && this.create_formSetting.formObject) {
      this.create_formSetting.formObject.reset();
    }
    if (this.create_modal) {
      this.create_modal.isOpen = false;
      this.create_modal.close();
    }
  }

  // 删除API Key
  deleteApiKey(row?: any) {
    if (row) {
      this.selectedRow = row;
    }
    
    if (!this.selectedRow) {
      this.plxMessage.warning('请先选择要删除的API Key', "");
      return;
    }
    
    this.delete_modal = this.modalService.open(this.delete_content);
    this.delete_modal.isOpen = true;
  }

  // 删除提交
  delete_submit() {
    if (!this.selectedRow) {
      this.plxMessage.warning('请先选择要删除的API Key', "");
      return;
    }

    // 使用api_key_id作为删除依据
    const deleteId = this.selectedRow.api_key_id;
    
    if (!deleteId) {
      this.plxMessage.warning('无法删除：缺少ID信息', "");
      return;
    }
    let body = {
      user_name: this.user_name,
      api_key_id: deleteId
    }
    console.log('删除ID:', deleteId);
    
    this.agentApi.deleteApiKeys(body).subscribe({
      next: (response: any) => {
        console.log('删除API Key响应:', response);
        
        if (response && response.code === 0) {
          this.data = this.data.filter(item => item.api_key_id !== deleteId);
          this.selectedRow = null;
          
          if (this.delete_modal) {
            this.delete_modal.isOpen = false;
            this.delete_modal.close();
          }
          this.plxMessage.info('删除成功', "");
        } else {
          const errorMsg = response?.msg || '删除失败';
          this.plxMessage.error('删除失败: ', errorMsg);
        }
      },
      error: (error: any) => {
        console.error('删除API Key失败:', error);
        this.plxMessage.error('删除API Key失败，请稍后重试', "");
      }
    });
  }

  // 删除取消
  delete_cancel() {
    if (this.delete_modal) {
      this.delete_modal.isOpen = false;
      this.delete_modal.close();
    }
  }

  // 设置当前用户的默认api_key（按用户隔离，每个用户独立设置）
  setDefaultApikey() {
    if (!this.selectedRow) {
      this.plxMessage.warning('请先选择一个API Key', "");
      return;
    }

    let body = {
      api_key_id: this.selectedRow.api_key_id
    }
    this.agentApi.setDefaultApiKey(body).subscribe({
      next: (response: any) => {
        console.log('设置默认API Key响应:', response);
        // 根据实际情况处理响应
        if (response && (response.code === 0 || response.success || response.id)) {
          console.log('选择的API Key:', this.selectedRow);
          this.plxMessage.info('已选择默认 API Key 模型:  ', this.selectedRow.model);
          // 刷新列表
          this.getApiKeyList();
        } else {
          const errorMsg = response?.msg || '设置默认api_key失败';
          this.plxMessage.error('设置失败: ', errorMsg);
        }
      },
      error: (error: any) => {
        console.error('设置默认api_key失败:', error);
        this.plxMessage.error('设置默认api_key失败，请稍后重试', "");
        
      }
    });
  }

  // 设置该用户在某 model 下的选中 api_key
  setModelDefaultApikey() {
    if (!this.selectedRow) {
      this.plxMessage.warning('请先选择一个API Key', "");
      return;
    }

    let body = {
      api_key_id: this.selectedRow.api_key_id
    }
    this.agentApi.setModelDefaultApiKey(body).subscribe({
      next: (response: any) => {
        console.log('设置模型选中API Key响应:', response);
        if (response && response.code === 0) {
          this.plxMessage.info('已将该模型选中为:  ', this.selectedRow.api_key + '****');
          this.getApiKeyList();
        } else {
          const errorMsg = response?.msg || '设置模型选中失败';
          this.plxMessage.error('设置失败: ', errorMsg);
        }
      },
      error: (error: any) => {
        console.error('设置模型选中失败:', error);
        this.plxMessage.error('设置模型选中失败，请稍后重试', "");
      }
    });
  }

  // 初始化新建表单配置
  create_initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-4',
      componentClass: 'col-sm-8',
      labelWidth: '120px',
      fieldWidth: '350px',
      srcObj: {},
      fieldSet: [
        {
          fields: [
            {
              name: 'api_key',
              label: 'API Key',
              type: FieldType.STRING,
              placeholder: '请输入完整的API Key',
              required: true,
              validators: [
                Validators.required,
                validateNoIllegalChars,
              ],
              validateInfos: {
                required: 'API Key不能为空',
                containsIllegalChars: 'API Key包含非法字符（禁止空格/换行/控制字符）',
              },
            },
            {
              name: 'base_url',
              label: 'Base URL',
              type: FieldType.STRING,
              placeholder: this.selectedApiFormat === 'cursor' 
              ? this.CURSOR_BASE_URL 
              : '例如：https://open.bigmodel.cn/api/coding/paas/v4',
              required: true,
              validators: [
                Validators.required,
                validateNoIllegalChars,
                validateHttpUrl,
              ],
              validateInfos: {
                required: 'Base URL不能为空',
                invalidBaseUrl: 'Base URL格式不正确（必须是 http/https 且禁止空白/控制字符）',
              },
              // 添加动态禁用功能（如果plx-form支持）
              disabled: this.selectedApiFormat === 'cursor',
              // 添加自定义样式类
              customClass: this.selectedApiFormat === 'cursor' ? 'cursor-fixed-url' : '',
            },
            {
              name: 'model',
              label: '模型名称',
              type: FieldType.STRING,
              placeholder: '请输入模型名称（如：gpt-4）',
              required: true,
              validators: [
                Validators.required,
                validateNoIllegalChars,
                validateModelChars,
              ],
              validateInfos: {
                required: '模型名称不能为空',
                invalidModel: '模型名称包含非法字符',
                containsIllegalChars: '模型名称包含非法字符（禁止空格/换行/控制字符）',
              },
            },
          ]
        }
      ]
    };
  }

  // 初始化删除表单配置
  delete_initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      labelClass: 'col-sm-4',
      componentClass: 'col-sm-8',
      labelWidth: '100px',
      fieldWidth: '300px',
      fieldSet: []
    };
  }

  ngOnDestroy(): void {
    // 清理弹窗
    const modals = [this.create_modal, this.delete_modal];
    modals.forEach(modal => {
      try {
        if (modal?.isOpen) {
          modal.close();
        }
      } catch (e) {
        console.error('关闭对话框失败', e);
      }
    });

    this.modalService.destroyModalInstance();
  }
}