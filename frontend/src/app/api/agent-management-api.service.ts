import { Injectable } from '@angular/core';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface ApiKeyItem {
  user_name: string;
  api_key_id: number,
  model: string;
  api_key: string;
  base_url: string;
  create_time: string;
  is_default: boolean;
  is_model_default?: boolean;
  api_format?: string;  // API 格式: cursor 或 openai
}

export interface ModelOption {
  value: string;
  label: string;
  api_format?: string;  // 对应的 API 格式
}

@Injectable({
  providedIn: 'root'
})
export class AgentManagementApi{
  constructor(private http: HttpClient) { }

  apikeyMessage: string = ''; // 新增：存储提示信息
  selectedApiKey: string = ''; // 选中的API Key标识
  showModelSelect = false;

  selectedModel: string = ''; // 选中的模型
  selectedApiformat: string = ''; // 选中的API格式
  onAiModeChange(value: string) {
    console.log('选中的模式:', value);
    // 根据 value 执行你的逻辑
    if (value === 'agent') {
      this.getSavedKeyByModel();
      this.showModelSelect = true;
    }
    else{
      this.showModelSelect = false;
      this.selectedModel = '';
      this.selectedApiformat = '';
    }
  }
  
  async getSavedKeyByModel() {
    this.apikeyMessage = '正在加载数据...'; // 加载中提示

    try {
        // 向后端发送 GET 请求
        const response = await fetch('/action/plugin/codemig/advise/api_key_get', {
          method: 'GET',
          headers: {
          'Content-Type': 'application/json',
          'X-Csrftoken': localStorage.getItem('X-Csrftoken') || ''
        },
      });
  
      if (!response.ok) {
        const errorMsg = await response.text();
        throw new Error(`查询失败: ${response.status} ${errorMsg}`);
      }
      const responseData = await response.json();
      // 检查返回码
      if (responseData.code !== 0) {
        throw new Error(`查询失败: ${responseData.msg}`);
      }
      
      return responseData.apikey_list;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '未知错误';
      console.error('查询已保存 API Key 时出错:', error);
      this.apikeyMessage = `加载失败: ${errorMsg}`;
      alert('加载已保存配置失败：' + errorMsg);
      return ;
    }
  }
  
  /**
   * 计算单条记录用于排序的权重数组，与后端 get_agent_config 的 order_by 逐级一致。
   * - admin：order_by(api_key_id asc)，不含"自己的 key"层和默认层
   * - 普通用户：order_by(手动选中 desc, 用户默认 desc, 自己的 desc, api_key_id asc)
   *   1) is_model_default（user_model_selection 手动选中）> 其他
   *   2) is_default（user_default_selection 用户默认，按用户隔离）> 其他
   *   3) 自己的 key（user_name == 当前用户）> admin 的 key
   *   4) api_key_id 升序（主键最小优先）
   */
  private modelSortWeight(item: ApiKeyItem, currentUser: string, isAdmin: boolean): number[] {
    const modelDefaultFlag = item.is_model_default ? 1 : 0;
    const defaultFlag = item.is_default ? 1 : 0;
    const idRank = -(item.api_key_id || 0);
    if (isAdmin) {
      // 与后端 admin 分支一致：不区分"自己的"和默认
      return [0, idRank];
    }
    const ownFlag = currentUser && item.user_name === currentUser ? 1 : 0;
    return [modelDefaultFlag, defaultFlag, ownFlag, idRank];
  }

  private compareWeight(a: number[], b: number[]): number {
    for (let i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) {
        return a[i] - b[i];
      }
    }
    return 0;
  }

  extractUniqueModels(data: ApiKeyItem[], currentUser: string = '', isAdmin: boolean = false) {

    // 使用 Map 存储 model -> { apiFormat, keyPrefix, weight } 的映射
    // 同一个 model 可能存在多条不同 key 的记录，按与后端一致的优先级只保留最高优先级的前缀
    const modelMap = new Map<string, { apiFormat: string; keyPrefix: string; weight: number[] }>();

    data.forEach(item => {
      const modelStr = (item.model && item.model.trim()) ? item.model.trim() : '未知模型';
      const apiFormat = item.api_format || 'openai';
      // 后端已脱敏，api_key 仅返回前8位，取前3位用于显示
      const keyPrefix = (item.api_key || '').substring(0, 3);

      // 权重与后端 get_agent_config 的 order_by 对齐；admin 与普通用户规则不同
      const weight = this.modelSortWeight(item, currentUser, isAdmin);
      const existing = modelMap.get(modelStr);
      if (!existing || this.compareWeight(weight, existing.weight) > 0) {
        modelMap.set(modelStr, { apiFormat, keyPrefix, weight });
      }

      // 下拉框默认选中哪个 model 由 is_default 决定（该用户的默认模型，按用户隔离）
      if (item.is_default) {
        this.selectedModel = modelStr;
        this.selectedApiformat = apiFormat;
        console.log('selectedApiformat: ', this.selectedApiformat);
        console.log('selectedModel: ', this.selectedModel);
      }
    });

    // 转换为数组，在 label 上附加 key 前缀（历史上有过"基础模型"BASE_MODEL
    // 占位选项，内置推理端点下线后已移除——模型一律来自用户配置的 Key 记录）
    const modelOptions = Array.from(modelMap.entries()).map(([model, info]) => {
      const keyHint = info.keyPrefix ? ` (${info.keyPrefix}...)` : '';
      return {
        label: model + keyHint,
        value: model,
        api_format: info.apiFormat
      };
    });
    return modelOptions;
  }
  
    /**
     * 获取模型的显示名称
     * 用于在没有model字段时显示友好的名称
     */
    getModelDisplayName(item: ApiKeyItem): string {
      if (item.model) {
        return item.model;
      } else {
        return '未知模型';
      }
    }
    getRandomUUID(): string {
      // 优先使用crypto.randomUUID标准 API
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
      }
      
      // 若不支持使用Web Crypto API 兼容方案
      try {
        // @ts-ignore
        const randomValues = new Uint8Array(16);
        crypto.getRandomValues(randomValues);
        
        // 设置版本号 (第四位为 4)
        randomValues[6] = (randomValues[6] & 0x0f) | 0x40;
        // 设置变体 (第八位为 8, 9, A, 或 B)
        randomValues[8] = (randomValues[8] & 0x3f) | 0x80;
        
        const hex = Array.from(randomValues)
          .map(b => b.toString(16).padStart(2, '0'))
          .join('');
        
        return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
      } catch (e) {
        // 保底方案
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
          const r = Math.random() * 16 | 0;
          const v = c === 'x' ? r : (r & 0x3 | 0x8);
          return v.toString(16);
        });
      }
    }

    public getApiKeyList(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_get'
      return this.http.get(url, options)
    }

    public addApiKey(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_store'
      return this.http.post(url, options)
    }

    public deleteApiKeys(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_del'
      return this.http.post(url, options)
    }
    public setDefaultApiKey(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_set_default'
      return this.http.post(url, options)
    }
    public setModelDefaultApiKey(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_set_model_default'
      return this.http.post(url, options)
    }
    public TestApiKey(options?: any){
      const url = '/action/plugin/codemig/advise/api_key_test'
      return this.http.post(url, options)
    } 
    public setAiScore(options?: any){
      const url = '/action/plugin/codemig/advise/ai_score_set'
      return this.http.post(url, options)
    }
    public getAiScore(options?: any){
      const url = '/action/plugin/codemig/advise/ai_score_get'
      return this.http.post(url, options)
    }
    public reopenAiSuggestion(options?: any){
      const url = '/action/plugin/codemig/advise/reopen_ai_suggestion'
      return this.http.post(url, options)
    }
}
