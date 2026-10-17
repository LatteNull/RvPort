import { Component, ChangeDetectorRef, ViewChild, OnInit, ElementRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Router } from '@angular/router';
// import * as monaco from 'monaco-editor';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.js';
import { IOption, PlxMessage, PlxModal } from 'paletx';
import { Clipboard } from '@angular/cdk/clipboard';
import { environment } from '../environment/environment';
import { SolverType } from '../environment/solver-type';
import { LogoutService } from '../services/logout.service'
import { CodeMigApi } from '../api/codemig-api.service'
import { CodemigFileSidebarService } from '../services/codemig-file-sidebar.service';
import { ApiKeyItem, ModelOption, AgentManagementApi } from '../api/agent-management-api.service'
import { tap, switchMap, of } from 'rxjs';

// AI/Agent 流式输出可能携带裸的 <s>/<strike>/<del> 原始 HTML 标签（如回显
// HTML/JSP 源码）。marked 透传 + Angular 消毒器白名单放行后，未闭合的 <s> 在
// innerHTML 片段解析时会吞掉其后所有兄弟节点，渲染成"后面全部内容带删除线"。
// 在数据层直接剥离这三个纯样式标签（不触碰 details/summary/div 等结构标签）。
const STRIKE_TAGS = ['s', 'strike', 'del'] as const;

const STRIKE_TAG_PATTERNS: ReadonlyArray<{ open: RegExp; close: RegExp }> = STRIKE_TAGS.map(
  (tag) => ({
    // 开标签：`<s>`、`<s attr>`；负向前瞻排除 `</s>` 与 `<span>` 等更长标签名
    open: new RegExp(`<${tag}(?![a-zA-Z0-9_-])[^>]*>`, 'g'),
    close: new RegExp(`</${tag}\\s*>`, 'g'),
  }),
);

// 流式输出中的 think 边界标签（pi 协议 <think/>/</think/> 与历史 <think>/</think>，
// 含流开头的引导 </think>）。不再据此做思考/正文分流——流式期间无法保证标签
// 序列完整（后端多协议变体），分流一旦失配内容会整体卡进思考折叠区且刷新后
// 又消失。改为与刷新后 reopen 恢复行为一致：剥掉标签本身，思考与正文一律
// 按普通文本进建议面板。
const THINK_TAG_VARIANTS = ['<think/>', '</think/>', '<think>', '</think>'] as const;

// 匹配 ``` 围栏行（含前导空白）；折叠块内围栏据此识别
const FENCE_LINE_RE = /^(\s*)`{3,}/;

/**
 * <details> 折叠块内的 ``` 围栏行统一加 4 空格缩进（与 migrate-view 同款）。
 *
 * 背景：Agent 过程流里的思考/工具折叠块由后端拼装，块内的裸 ``` 围栏
 * （模型或工具展示层输出，不知道自己正嵌在 HTML 块里）经 marked 按
 * CommonMark 解析，未闭合围栏会把块后所有内容吞进一个巨型代码块——
 * 其后全部 <details>/</details> 被转义成纯文本，表现为"思考和正文全包在
 * 一个思考块里"，同时折叠块元素消失导致展开态回放失效。
 *
 * 后端已在展示层与入库出口做过同样清洗，这里是前端最后一道兜底：
 * ① 兼容历史入库数据（清洗上线前的记录）；② 兜住任何后端遗漏路径。
 */
function sanitizeFencesInDetails(text: string): string {
  if (!text.includes('<details>') || !text.includes('```')) return text;
  const out: string[] = [];
  let inDetails = false;
  for (const line of text.split('\n')) {
    const stripped = line.replace(/^[ \t]+/, '');
    if (stripped.startsWith('<details>')) {
      inDetails = true;
      out.push(line);
      continue;
    }
    if (stripped.startsWith('</details>') || stripped.startsWith('</div></details>')) {
      inDetails = false;
      out.push(line);
      continue;
    }
    if (inDetails && FENCE_LINE_RE.test(line)) {
      out.push('    ' + stripped);
      continue;
    }
    out.push(line);
  }
  return out.join('\n');
}

@Component({
  selector: 'app-codemig-file-change-view',
  templateUrl: './codemig-file-change-view.component.html',
  styleUrls: ['./codemig-file-change-view.component.css', '../../assets/markdown/markdown.css'],
  standalone: false,
})
export class CodemigFileChangeViewComponent implements OnInit {
  user_name: any;
  task_id!: number;
  dir_id!: number;
  file_id!: number;
  dependence_id!: number;
  editorRef!: monaco.editor.IStandaloneDiffEditor;
  originalModel: any = { value: ''};
  modifiedModel: any = { value: ''};
  decorationsCollection!: monaco.editor.IEditorDecorationsCollection;
  globalClickListenerAdded:boolean = false;
  currentChanges: any[] | null = null;
  showAIPanel = false;

  // 选中的行号信息
  selectedLineNumbers: { startLine: number; endLine: number; lineCount: number } | null = null;
  selectionDisposable: monaco.IDisposable | null = null;

  // suggestion 经 getter/setter 拦截：写入时剥离裸 s/strike/del 标签，
  // 根治未闭合 <s> 吞兄弟节点导致的"后面全部内容带删除线"（见文件头部注释）。
  // += 追加、reopen 恢复、清空等全部赋值路径对 getter/setter 透明。
  private _suggestion: string = '';

  // ── 流式渲染时 <details> 展开状态保持 ──
  // ngx-markdown 每次 [data] 变化都整块替换 innerHTML，<details> 的展开态存在
  // DOM 上（不在 markdown 源串里），流式期间的重渲染会把它销毁重建为缩略态。
  // 修复（与 migrate-view 同款）：赋值前快照已展开块的锚点（summary 文本 +
  // 同名出现次序），渲染完成后按锚点回放。
  @ViewChild('suggestionMarkdown') suggestionMarkdownRef?: ElementRef<HTMLDivElement>;
  /** 最近一次渲染前快照的已展开 details 锚点集合 */
  private openDetailsAnchors: string[] = [];

  get suggestion(): string {
    return this._suggestion;
  }

  set suggestion(value: string) {
    // 重渲染前快照当前已展开的 <details>（用户点击产生的 open 状态只存在于
    // DOM 上，innerHTML 整块替换后即丢失），渲染完成后回放。
    this.snapshotOpenDetails();
    // 围栏清洗：折叠块内裸 ``` 会让 marked 吞掉块后内容（详见
    // sanitizeFencesInDetails 注释），后端已洗，此处兜底历史数据与遗漏路径。
    this._suggestion = typeof value === 'string'
      ? sanitizeFencesInDetails(this.stripStrikeTags(value))
      : value;
  }

  /** 收集当前 DOM 中所有已展开 <details> 的锚点（summary 文本 + 同名出现次序），用于重渲染后回放展开态 */
  private snapshotOpenDetails(): void {
    const host = this.suggestionMarkdownRef?.nativeElement;
    if (!host) return;
    const list = host.querySelectorAll<HTMLDetailsElement>('details');
    if (list.length === 0) { this.openDetailsAnchors = []; return; }
    // 仅按 summary 文本匹配（不用全局序号）：流式期间重渲染会随新增折叠块
    // 让全局序号整体后移，序号锚点必然失配。同名 summary 用出现次序区分。
    const seen = new Map<string, number>();
    const anchors: string[] = [];
    list.forEach((el) => {
      const summary = (el.querySelector('summary')?.textContent || '').trim();
      if (!el.open || !summary) return;
      const occur = seen.get(summary) || 0;
      seen.set(summary, occur + 1);
      anchors.push(`${occur}|${summary}`);
    });
    this.openDetailsAnchors = anchors;
  }

  /** ngx-markdown (ready)：本次渲染完成，回放快照的展开态 */
  onSuggestionRenderReady(): void {
    if (this.openDetailsAnchors.length === 0) {
      this.followStreamOutput();
      return;
    }
    const host = this.suggestionMarkdownRef?.nativeElement;
    if (!host) return;
    const wanted = new Set(this.openDetailsAnchors);
    const seen = new Map<string, number>();
    host.querySelectorAll<HTMLDetailsElement>('details').forEach((el) => {
      const summary = (el.querySelector('summary')?.textContent || '').trim();
      if (!summary) return;
      const occur = seen.get(summary) || 0;
      seen.set(summary, occur + 1);
      if (wanted.has(`${occur}|${summary}`)) {
        el.open = true;
      }
    });
    this.followStreamOutput();
  }

  // ── 流式输出智能跟随滚动 ──
  // 问题：流式期间 suggestion 每 ~200ms 整块重渲染一次，浏览器保持旧
  // scrollTop，新输出在视口之外，用户必须手动滚到最底才能看到最新内容。
  // 策略（与常见终端/聊天窗一致）：
  //   1. 用户在底部附近（≤40px）→ 每次渲染后自动滚到底，跟随最新输出；
  //   2. 用户向上翻看历史 → 暂停跟随，不再抢夺滚动位置；
  //   3. 滚回底部附近 → 自动恢复跟随。
  // 仅在流式生成（isGenerating）中主动跟随；静态查看时不改变用户位置。
  @ViewChild('panelContent') panelContentRef?: ElementRef<HTMLDivElement>;
  /** 是否处于"跟随最新输出"状态；用户上翻即置 false */
  private streamFollowEnabled = true;

  /** 滚动事件：根据位置更新跟随状态（近底部=跟随，上方=暂停） */
  onPanelScroll(): void {
    const el = this.panelContentRef?.nativeElement;
    if (!el) return;
    this.streamFollowEnabled =
      el.scrollHeight - el.scrollTop - el.clientHeight <= 40;
  }

  /** 渲染完成后：若在跟随状态则滚到最新输出处 */
  private followStreamOutput(): void {
    if (!this.isGenerating) return;
    if (!this.streamFollowEnabled) return;
    const el = this.panelContentRef?.nativeElement;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  suggestionOptions: Array<IOption> = [];
  selectedSuggestionOption: string = '';
  refreshSuggestionOption: string = '';
  loading: boolean = true;

  // 用于存储原始的建议选项（不包含选中行号）
  private originalSuggestionOptions: Array<IOption> = [];

  leftPanelFlex = 6;
  rightPanelFlex = 4;
  isResizing = false;
  aiMode = 'reasoning';  // 初始状态为建议模式

  isGenerating: boolean = false; // 新增：标记是否正在生成中

  // 点赞/点踩选中状态，再次点击取消选中
  isLiked = false;
  isDisliked = false;
  isCleared = false;

  // 保存 widget 引用
  private aiActionWidget: monaco.editor.IContentWidget | null = null;

  abortController: AbortController | null = null;
  currentRequestId = 0;
  currentRequestUUID : string = '';
  editorOptions = {
    theme: 'vs',
    rules: [
      { token: 'custom-keyword', foreground: 'd63384', fontStyle: 'bold' },
      { token: 'number', foreground: '17a2b8' },
      { token: 'string', foreground: 'fd7e14' },
      { token: 'comment', foreground: '6c757d', fontStyle: 'italic' },
    ],
    colors: {
      'editor.background': '#ffffff',
    },
    language: 'cpp',
    readOnly: false,
    automaticLayout: true,
    fixedOverflowWidgets: true,
    // Diff Editor specific options
    originalEditable: false,
    enableSplitViewResizing: true,
    renderSideBySide: false,
  };

  deleteSuggestionModal:any;
  deleteSuggestionOption:any;
  @ViewChild('content') public content:any;

  constructor(
    private codeMigApi: CodeMigApi,
    private agentApi: AgentManagementApi,
    private route: ActivatedRoute,
    private router: Router,
    private plxMessage: PlxMessage,
    private clipboard: Clipboard,
    private cdr: ChangeDetectorRef,
    private logoutService: LogoutService,
    private codemigFileSidebarService: CodemigFileSidebarService,
    private modalService: PlxModal,
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  ngOnInit() {
    // 组件初始化时加载模型列表，确保建议模式默认也能选择模型
    this.fileChange_getApikeyList();
    this.showModelSelect = true;
  }
  selectedModel: string = ''; // 选中的模型
  selectedApiformat : string = '';
  apikeyList: ApiKeyItem[] = [];  // 存储API Key列表
  modelOptions: ModelOption[] = []; // 当前模式下可用的模型选项列表
  allModelOptions: ModelOption[] = []; // 所有模型选项列表
  showModelSelect = false;
  onAiModeChange(value: string) {
    // 根据 value 执行你的逻辑
    if (value === 'normal') {
      this.showModelSelect = false;
      this.selectedModel = '';
      this.selectedApiformat = '';
    } else {
      // reasoning 和 agent 模式都支持模型选择
      this.showModelSelect = true;
      this._updateModelOptionsForMode(value);
    }
    // 切到非 agent 模式时，Agent 专有的"全部建议"项不再存在于 options，需重置选择
    if (value !== 'agent' && this.selectedSuggestionOption === CodemigFileChangeViewComponent.PLACEHOLDER_VALUE) {
      this.selectedSuggestionOption = '';
    }
    // 切换模式时，placeholder 文案变化，需重建 options 让第一项 label 同步
    this.updateSuggestionOptions();
  }

  /**
   * 建议列表 placeholder：按 AI 模式区分
   * - reasoning：必须选择一条建议
   * - agent：未选择时默认选择全部建议生成
   */
  get suggestionSelectPlaceholder(): string {
    return this.aiMode === 'agent'
      ? 'Agent模式默认为当前文件全部建议进行AI生成'
      : '建议模式请选择一条建议进行 AI 生成';
  }

  /** placeholder / "全部建议" 选项的特殊 value 标记 */
  static readonly PLACEHOLDER_VALUE = '__placeholder__';

  /** 判断 option 是否为 placeholder（提示/全部建议）项 */
  isPlaceholderOption(option: any): boolean {
    return !!option && option.value === CodemigFileChangeViewComponent.PLACEHOLDER_VALUE;
  }

  /**
   * 根据AI模式更新模型选项列表（agent/建议模式共用同一份用户配置模型列表）
   */
  private _updateModelOptionsForMode(mode: string) {
    this.modelOptions = [...this.allModelOptions];
  }

  async fileChange_getApikeyList(){
    this.apikeyList = await this.agentApi.getSavedKeyByModel();
    // 获取API Key列表
    const data = this.apikeyList  || [];
    this.allModelOptions = this.agentApi.extractUniqueModels(
      data, this.user_name, localStorage.getItem('userRole') === 'admin');
    this.selectedModel = this.agentApi.selectedModel;
    this.selectedApiformat = this.agentApi.selectedApiformat;
    this._updateModelOptionsForMode(this.aiMode);
  }

  /**
   * 选择模型改变时触发
   */
  onModelChange(model: string): void {
    this.selectedModel = model;
    // 根据 model 从 modelOptions 中找到对应的 api_format
    const selectedOption = this.modelOptions.find(opt => opt.value === model);
    this.selectedApiformat = selectedOption?.api_format || '';
    console.log('selectedApiformat: ', this.selectedApiformat);
    console.log('selectedModel: ', this.selectedModel);
  }

  /** 无可用模型时，下拉框给出引导文案 */
  get modelSelectPlaceholder(): string {
    return this.modelOptions.length === 0
      ? '暂无可用模型，请先配置 API Key'
      : '请选择模型';
  }

  /** 跳转到 API Key 管理页面 */
  goToApiKeyManagement(): void {
    this.router.navigate(['/settings/agentmanagement']);
  }
  toggleAIPanel() {
    this.showAIPanel = !this.showAIPanel;
    if (this.showAIPanel && !this.isCleared && !this.isGenerating) {
      this.loadAiSuggestionOnReopen();
    }
  }

  /** 显示 AI 面板时从后端拉取已保存的 AI 建议 */
  loadAiSuggestionOnReopen() {
    const body = {
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: this.file_id,
    };
    this.agentApi.reopenAiSuggestion(body).subscribe({
      next: (res: any) => {
        if (res?.code === 0 && res?.data != null) {
          this.suggestion = res.data;
          // 获取评分状态
          this.getAiScore();
        }
      },
      error: () => {},
    });
  }

  /** 获取AI建议的评分状态 */
  getAiScore() {
    const body = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      uuid: this.currentRequestUUID,
    };
    this.agentApi.getAiScore(body).subscribe({
      next: (res: any) => {
        if (res?.code === 0 && res?.data !== undefined) {
          // 根据评分状态设置显示
          // 0: 点踩, 4: 点赞, 5: 未评分
          const score = res.data;
          if (score === 0) {
            this.isDisliked = true;
            this.isLiked = false;
          } else if (score === 4) {
            this.isLiked = true;
            this.isDisliked = false;
          } else {
            // 未评分状态或其他情况
            this.isLiked = false;
            this.isDisliked = false;
          }
          this.cdr.detectChanges();
        }
      },
      error: (error: any) => {
        console.error('获取评分状态失败:', error);
        // 获取失败时重置状态
        this.isLiked = false;
        this.isDisliked = false;
        this.cdr.detectChanges();
      },
    });
  }

  onDeselected(){
    this.selectedSuggestionOption = ''
    this.refreshSuggestionOption = ''
  }

  onSelected(){
    // 检查是否是选中行号选项
    if (this.selectedSuggestionOption && Array.isArray(this.selectedSuggestionOption)) {
      if (this.selectedSuggestionOption[0]) {
        // 普通建议选项
        this.revealLine(parseInt(String(this.selectedSuggestionOption[0])));
      }
    }
  }

  revealLine(lineNumber: number) {
    if (this.editorRef) {
      // 滚动到指定行
      this.editorRef.revealLineNearTop(lineNumber, 0);
    }
  }

  check(){
    const isPlaceholderSelected = this.selectedSuggestionOption === CodemigFileChangeViewComponent.PLACEHOLDER_VALUE;
    // 建议模式：未选 / 选中提示项都视为"未选具体建议"，需提示
    if (this.aiMode != 'agent' && (!this.selectedSuggestionOption || isPlaceholderSelected)) {
      this.plxMessage.warning("建议模式请选择一条建议进行 AI 生成", "")
      return;
    }
    if(!this.selectedModel && (this.aiMode === 'agent' || this.aiMode === 'reasoning')){
      this.plxMessage.warning("请选择模型", "")
      return;
    }
    // 取消之前的请求
    this.cancelRequest()
    // 为当前请求生成唯一ID
    const requestId = ++this.currentRequestId;
    this.suggestion = ''
    this.showAIPanel = true
    this.isGenerating = true;
    // 新一轮流式开始：恢复"跟随最新输出"，与上翻暂停配合
    this.streamFollowEnabled = true;
    this.refreshSuggestionOption = this.selectedSuggestionOption
    this.currentRequestUUID = this.agentApi.getRandomUUID();
    this.abortController = new AbortController();
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      think_mode: this.aiMode,
      agent_model: this.selectedModel,
      api_format: this.selectedApiformat,
      request_uuid: this.currentRequestUUID
    };

    // 检查是否当前新增的建议，而非后端返回的建议
    if (this.selectedSuggestionOption && Array.isArray(this.selectedSuggestionOption)) {
      if (this.selectedSuggestionOption[4] === null && this.selectedSuggestionOption[5] == null) {
        body.selected_start_line = this.selectedSuggestionOption[0];
        body.selected_end_line = this.selectedSuggestionOption[1];
      } else {
        // 后端返回的建议选项，传递 change_id
        body.change_id = this.selectedSuggestionOption[4];
      }
    }
    // 选中提示项（仅 Agent 模式可能走到这里）= 不传 change_id / selected_*_line，
    // 后端按"全部建议"逻辑处理。

    if (this.dependence_id){
      body.dependence_id = this.dependence_id
    }
    this.queryAI(body, requestId)
  }

  async queryAI(payload: any, requestId: any){
    const url = this.codeMigApi.queryAISuggestionUrl()

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Csrftoken': localStorage.getItem('X-Csrftoken') || ''
        },
        body: JSON.stringify(payload),
        signal: this.abortController?.signal
      });

       // 检查请求是否已被新请求取代
      if (requestId !== this.currentRequestId) {
        return;
      }
      // 显式检查 401 状态码
      if (response.status === 401) {
        this.plxMessage.error("身份验证失效、请重新登录", "");
        this.logoutService.logout(); // 触发登出
        return;
      }
      if (!response.ok) throw new Error('请求失败');
      if (response.body != null){
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        // think 标签只剥除不分流：思考与正文一律按普通文本进建议面板（与刷新后
        // reopen 恢复的数据形态一致），避免分流失配导致内容卡思考区/刷新后消失。
        /** 是否已通过 BACKEND_ERROR/TIMEOUT/UNKNOWN 等行提示过，避免与 DONE 重复弹窗 */
        let agentStreamErrorReported = false;
        while (true) {

          // 检查请求是否已被取消或取代
          if (requestId !== this.currentRequestId) {
            reader.cancel(); // 主动取消流读取
            return;
          }
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value);
          // 处理缓冲区中的完整行
          let lineEndIndex;
          while ((lineEndIndex = buffer.indexOf('\n')) >= 0) {
            const line = buffer.substring(0, lineEndIndex).trim();
            buffer = buffer.substring(lineEndIndex + 1);

            if (line) {
              try {
                const jsonData = JSON.parse(line);
                if (jsonData.status === 3) {
                  try {
                    const keyInfo = JSON.parse(jsonData.value || '{}');
                    const prefix = keyInfo.key_prefix ? `（Key: ${keyInfo.key_prefix}...）` : '';
                    this.plxMessage.info(`正在使用模型：${keyInfo.model || ''} ${prefix}`, "");
                  } catch { /* 忽略解析失败 */ }
                } else if (jsonData.status === 1) {
                  this.suggestion += this._stripThinkTags(jsonData.value ?? '');
                  this.cdr.detectChanges();
                } else if (jsonData.status === 0) {
                  // DONE：后端携带 has_result、returncode、result_ok（result 行业务是否成功）
                  let doneInfo: any = null;
                  try {
                    doneInfo = jsonData.value ? JSON.parse(jsonData.value) : null;
                  } catch {
                    doneInfo = null;
                  }
                  const hasResult = doneInfo?.has_result;
                  const returnCode = doneInfo?.returncode;
                  const resultOk = doneInfo?.result_ok;
                  const doneAbnormal =
                    hasResult === false ||
                    (typeof returnCode === 'number' && returnCode !== 0) ||
                    resultOk === false;
                  if (doneAbnormal && !agentStreamErrorReported) {
                    const msg =
                      resultOk === false && hasResult === true
                        ? 'AI 生成未正常完成（服务返回失败或已取消）'
                        : `AI Agent 异常结束（has_result=${String(hasResult)}, returncode=${String(returnCode)}）`;
                    this.plxMessage.error(msg, "");
                    this.suggestion += `\n\n[ERROR] ${msg}\n`;
                    this.cdr.detectChanges();
                  }
                } else if (jsonData.status === -1 || jsonData.status === -2 || jsonData.status === -3) {
                  // BACKEND_ERROR / TIMEOUT / UNKNOWN_ERROR
                  agentStreamErrorReported = true;
                  const errText = (jsonData.value ?? '').toString();
                  this.plxMessage.error("AI 生成失败", errText);
                  this.cdr.detectChanges();
                }
              } catch (e) {
                console.error('解析JSON失败:', e);
              }
            }
          }
        }
      }
    } catch (error: any) {
      // 只处理未被取消的请求错误
      if (error.name !== 'AbortError' && requestId === this.currentRequestId) {
        this.plxMessage.error("请求错误", "");
        console.error('请求错误:', error);
      }
    } finally {
      // 只有当前请求是活动请求时才清理
      this.isGenerating = false;
      if (requestId === this.currentRequestId) {
        this.isCleared = false;
        // agent模式下，查询完成后刷新diff页面
        if (this.aiMode === 'agent' && this.editorRef) {
          this.refreshDiffAfterAgentQuery();
        }
        if (this.aiMode === 'agent') {
          this.refreshFileTree();
        }
        this.abortController = null;
      }
    }
  }

    // 更新编辑器显示AI建议的代码
    updateEditorWithAISuggestion(aiSuggestedCode: string) {
      if (!this.editorRef) {
        console.error('❌ 编辑器引用未初始化');
        return;
      }

      const diffModel = this.editorRef.getModel();
      if (!diffModel || !diffModel.modified) {
        console.error('❌ diff模型未正确初始化');
        return;
      }

      diffModel.modified.setValue(aiSuggestedCode);

      this.editorRef.layout();

      // 延迟刷新确保显示正确
      setTimeout(() => {
        if (this.editorRef) {
          this.editorRef.layout();
        }
      }, 100);
    }
  async cancel_agent(){
    let payload: any = {
      dir_id: this.dir_id,
      request_uuid: this.currentRequestUUID
    };

    try {
      const url = this.codeMigApi.cancelAISuggestionUrl()
      // 向后端发送 POST 请求
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Csrftoken': localStorage.getItem('X-Csrftoken') || ''
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorMsg = await response.text();
        throw new Error(`取消失败: ${response.status} ${errorMsg}`);
      } else {
        this.currentRequestUUID = ''
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '未知错误';
      console.error('取消时出错:', error);

      this.plxMessage.warning("取消失败", "")
    }
  }
  // 添加取消方法（可由外部调用）
  cancelRequest() {
    if(this.aiMode == 'agent' && this.currentRequestUUID){
      this.cancel_agent();
    }

    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  copyContent(){
    this.clipboard.copy(this.suggestion);
    this.plxMessage.success("复制成功", "")
  }

  /**
   * 剥离裸的 s/strike/del 标签（开+闭）。无标签时返回原引用，避免流式热路径上
   * 每 200ms 全量重赋值产生多余字符串分配。与 migrate-view 同款实现。
   */
  private stripStrikeTags(text: string): string {
    if (!text) return text;
    let has = false;
    for (const { open, close } of STRIKE_TAG_PATTERNS) {
      open.lastIndex = 0;
      close.lastIndex = 0;
      if (open.test(text) || close.test(text)) { has = true; break; }
    }
    if (!has) return text;
    let result = text;
    for (const { open, close } of STRIKE_TAG_PATTERNS) {
      open.lastIndex = 0;
      close.lastIndex = 0;
      result = result.replace(open, '').replace(close, '');
    }
    return result;
  }

  /**
   * 剥离流式输出中的 think 边界标签（4 种变体见 THINK_TAG_VARIANTS），内容不分流。
   * 与刷新后 reopen 恢复行为保持一致：思考与正文都是普通文本，全部进建议面板。
   * 无标签时返回原引用，避免流式热路径上的多余字符串分配。
   */
  private _stripThinkTags(text: string): string {
    if (!text) return text;
    let has = false;
    for (const tag of THINK_TAG_VARIANTS) {
      if (text.includes(tag)) { has = true; break; }
    }
    if (!has) return text;
    let result = text;
    for (const tag of THINK_TAG_VARIANTS) {
      result = result.split(tag).join('');
    }
    return result;
  }

  clearContent(){
    this.suggestion = ''
    this.isLiked = false
    this.isDisliked = false
    this.isCleared = true
    this.plxMessage.success("清除成功", "")
  }
  likeContent(){
    if (this.isLiked) {
      this.isLiked = false;
      return;
    }
    this.isDisliked = false;
    this.isLiked = true;
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      score: 4, // 点赞 (0-4)
    };
    this.agentApi.setAiScore(body).subscribe({
      next: (response: any) => {
        if (response.code === 0){
          this.plxMessage.success("点赞成功", "");
          this.getAiScore();
        }
        else{
          this.plxMessage.show(response.msg, "");
        }
      },
    });
  }
  dislikeContent(){
    if (this.isDisliked) {
      this.isDisliked = false;
      return;
    }
    this.isLiked = false;
    this.isDisliked = true;
    this.plxMessage.success("点踩成功", "")
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      score: 0, // 点踩 (0-4)
    };
    this.agentApi.setAiScore(body).subscribe({
      next: (response: any) => {
        console.log(response.msg);
        // 点踩成功后重新获取评分状态以确保前后端状态一致
        this.getAiScore();
      },
    });
  }

  init(){
    this.showAIPanel = false
    this.selectedSuggestionOption = ''
    this.suggestion = ``
    this.isLiked = false
    this.isDisliked = false
  }

  processSaveResponse(response: any) {
    if (response?.new_file_id) {
      this.file_id = response.new_file_id;
      const savedAIState = {
        showAIPanel: this.showAIPanel,
        suggestion: this.suggestion,
        selectedSuggestionOption: this.selectedSuggestionOption,
        isLiked: this.isLiked,
        isDisliked: this.isDisliked,
      };
      this.httpQuery(this.editorRef, () => {
        this.showAIPanel = savedAIState.showAIPanel;
        this.suggestion = savedAIState.suggestion;
        this.selectedSuggestionOption = savedAIState.selectedSuggestionOption;
        this.isLiked = savedAIState.isLiked;
        this.isDisliked = savedAIState.isDisliked;
      });
    } else {
      // 文件没有其他建议，跳转回到任务页面
      this.goBack();
    }
  }

  goBack() {
    // 跳转回到任务页面
    if (this.dependence_id){
      this.router.navigate(['/codemig/dependence'], {
        queryParams: { task_id: this.task_id, dependence_id: this.dependence_id },
      });
    }else{
      this.router.navigate(['/codemig/task'], {
        queryParams: { task_id: this.task_id },
      });
    }
  }

  saveChanges() {
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      content: this.editorRef.getModel()?.modified.getValue(),
    };
    if (this.dependence_id){
      body.dependence_id = this.dependence_id
    }
    this.codeMigApi.saveTaskFileChange(body).subscribe({
      next: (response: any) => {
        if (response.code == 0){
          this.processSaveResponse(response);
        }
      },
      error: (errorResponse: any) => {
        console.error('保存失败', errorResponse);
        alert('保存失败');
      },
    });
  }

  // 保存并回退文件
  saveAndRollback() {
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      content: this.editorRef.getModel()?.modified.getValue(),
    };
    if (this.dependence_id){
      body.dependence_id = this.dependence_id
    }

    // 先保存，保存成功后再回退
    this.codeMigApi.saveTaskFileChange(body).pipe(
      switchMap((saveResponse: any) => {
        if (saveResponse.code == 0) {
          this.processSaveResponse(saveResponse);
          // 保存成功后调用回退
          let rollbackBody: any = {
            user_name: this.user_name,
            task_id: this.task_id,
            dir_id: this.dir_id,
            file_id: this.file_id,
          };
          if (this.dependence_id) {
            rollbackBody.dependence_id = this.dependence_id;
          }
          return this.codeMigApi.rollbackFile(rollbackBody);
        } else {
          alert('保存失败');
          return of({ code: -1, msg: '保存失败' });
        }
      })
    ).subscribe({
      next: (rollbackResponse: any) => {
        if (rollbackResponse.code === 0) {
          this.plxMessage.success('文件回退成功', '');
          // 回退成功后重新加载文件内容
          const savedAIState = {
            showAIPanel: this.showAIPanel,
            suggestion: this.suggestion,
            selectedSuggestionOption: this.selectedSuggestionOption,
            isLiked: this.isLiked,
            isDisliked: this.isDisliked,
          };
          this.httpQuery(this.editorRef, () => {
            this.showAIPanel = savedAIState.showAIPanel;
            this.suggestion = savedAIState.suggestion;
            this.selectedSuggestionOption = savedAIState.selectedSuggestionOption;
            this.isLiked = savedAIState.isLiked;
            this.isDisliked = savedAIState.isDisliked;
          });
        }
      },
      error: (errorResponse: any) => {
        console.error('Error rollback file: ', errorResponse);
        this.plxMessage.error('文件回退失败', '');
      },
    });
  }

  onEditorInit(editor: monaco.editor.IStandaloneDiffEditor) {
    this.editorRef = editor;

    // 获取右侧（Modified）编辑器实例
    const modifiedEditor = editor.getModifiedEditor();

    modifiedEditor.onDidChangeCursorSelection((e: monaco.editor.ICursorSelectionChangedEvent) => {
      this.updateFloatingWidget(e);
    });

    // 注册右键菜单动作
    modifiedEditor.addAction({
        id: 'add-selection-to-suggestions', // 唯一ID
        label: '✨ 将选中代码添加到AI生成建议', // 右键菜单显示的文字
        contextMenuGroupId: 'navigation', // 菜单分组，'navigation' 通常在顶部
        contextMenuOrder: 1.5,
        precondition: 'editorHasSelection',
        keybindings: [
            monaco.KeyMod.CtrlCmd | monaco.KeyCode.F10
        ],
        run: (ed) => {
            // 执行添加逻辑
            this.addSelectionToManualOptions(ed);
        }
    });

    this.route.queryParams.subscribe((params) => {
      this.task_id = Number(params['task_id']);
      this.dir_id = Number(params['dir_id']);
      this.file_id = Number(params['file_id']);
      this.dependence_id = Number(params["dependence_id"]);
      this.cancelRequest()
      this.httpQuery(editor);
    });

  }

  updateFloatingWidget(e: monaco.editor.ICursorSelectionChangedEvent) {
    const selection = e.selection;

    // 1. 如果没有选中内容，或者选区为空，移除按钮
    if (selection.isEmpty()) {
        this.removeAiWidget();
        return;
    }

    // 2. 如果已经存在，先移除旧的（避免重复）
    this.removeAiWidget();

    // 3. 创建新的 Widget
    this.createAiWidget(selection);
  }

  // 【新增方法】创建 Widget
  createAiWidget(selection: monaco.Selection) {
    const that = this; // 保存 this 指向

    this.aiActionWidget = {
        allowEditorOverflow: true, // 允许溢出编辑器边界
        getId: function() {
            return 'ai.suggestion.floating.widget';
        },
        getDomNode: function() {
          const domNode = document.createElement('div');

          // 直接设置内联样式
          Object.assign(domNode.style, {
              backgroundColor: '#0366d6',
              color: 'white',
              padding: '6px 10px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              zIndex: '2000',
              fontWeight: '500',
              transition: 'background 0.2s',
              whiteSpace: 'nowrap' // 防止按钮文字换行
          });

          domNode.innerHTML = '<span>✨</span> 将选中代码添加到AI生成建议中';

          // 悬停效果
          domNode.onmouseenter = () => domNode.style.backgroundColor = '#0256b9';
          domNode.onmouseleave = () => domNode.style.backgroundColor = '#0366d6';

          // 点击事件
          domNode.onclick = (e) => {
              e.stopPropagation(); // 防止点击导致选区消失
              that.addSelectionToManualOptions(that.editorRef.getModifiedEditor());
              that.removeAiWidget(); // 点击后隐藏按钮
          };
          return domNode;
        },
        getPosition: function() {
            // 将按钮定位在选区的结束位置 (右上角或右下角)
            return {
                position: {
                    lineNumber: selection.endLineNumber,
                    column: selection.endColumn
                },
                // 优先显示在选区上方，如果不够位置则显示在下方
                preference: [
                    monaco.editor.ContentWidgetPositionPreference.ABOVE,
                    monaco.editor.ContentWidgetPositionPreference.BELOW
                ]
            };
        }
    };

    // 将 Widget 添加到编辑器
    this.editorRef.getModifiedEditor().addContentWidget(this.aiActionWidget);
  }

  // 【新增方法】移除 Widget
  removeAiWidget() {
    if (this.aiActionWidget) {
        this.editorRef.getModifiedEditor().removeContentWidget(this.aiActionWidget);
        this.aiActionWidget = null;
    }
  }

  addSelectionToManualOptions(ed: any){
    // 获取当前选区
    const selection = ed.getSelection();
    if (selection) {
        const startLine = selection.startLineNumber;
        const endLine = selection.endLineNumber;

        const isDuplicate = this.originalSuggestionOptions.some(option => {
          const optionValue = option.value;
          // option.value 格式为 [startLine, endLine, type, description, change_id, solver_type, ignored, is_manual]
          return optionValue[0] === startLine && optionValue[1] === endLine;
        });

        // 如果是重复的行号范围，跳过更新
        if (isDuplicate) {
          return;
        }

        // 格式化提示内容：第开始行到结束行，请转化为适配riscv架构的代码
        const labelText = startLine === endLine
          ? `第${startLine}行，请转化为适配riscv架构的代码`
          : `第${startLine}行到第${endLine}行，请转化为适配riscv架构的代码`;
        // v4.0：8 元组契约对齐后端 SELECT_SUGGESTION_SQL
        // [0]start, [1]end, [2]append_or_replace, [3]suggestion, [4]change_id, [5]type, [6]ignored, [7]is_manual
        const change = [startLine, endLine, 2, '请转化为适配riscv架构的代码', null, null, 0, 1];
        this.originalSuggestionOptions.unshift({
          label: labelText,
          value: change as any,
          disabled: false
        });
        this.updateSuggestionOptions();
        this.refreshDecorationsAfterDelete();
        this.cdr.detectChanges();

        // v4.0：立即入库，避免刷新页面后丢失
        // 单文件视图的 manual 选中也会出现在一键迁移的 scan_result.json 中
        // （_query_manual_suggestions_for_project_migrate 是按 is_manual=1 全 dir 查询）
        if (this.file_id && this.dir_id) {
          this.codeMigApi.insertManualSuggestion({
            user_name: this.user_name,
            dir_id: this.dir_id,
            file_id: this.file_id,
            start_line: startLine,
            end_line: endLine,
            suggestion: '请转化为适配riscv架构的代码',
            append_or_replace: 2,
          }).subscribe({
            next: (res: any) => console.info('[单文件视图] manual_selection 已入库', {
              fileId: this.file_id, start: startLine, end: endLine, res,
            }),
            error: (err) => console.warn('[单文件视图] manual_selection 入库失败（已忽略）', err),
          });
        }
    }
  }

  /**
 * 手动删除选项
 * @param event 点击事件
 * @param optionToKill 待删除的选项对象
 */
  removeOption(event: MouseEvent, optionToKill: IOption) {
    // 1. 阻止事件冒泡，防止点击删除图标时触发下拉框的选择事件
    event.stopPropagation();
    event.preventDefault();
    this.deleteSuggestionOption = optionToKill
    this.deleteSuggestionModal = this.modalService.open(this.content, {size: 'xs'});
  }
  deleteSuggestion() {
    if (this.deleteSuggestionOption.value[4] === null && this.deleteSuggestionOption.value[5] == null) {
      // v4.0：手动选中条目同步删除 DB
      this.executeDeleteUIUpdate();
      this.codeMigApi.deleteManualSuggestion({
        user_name: this.user_name,
        dir_id: this.dir_id,
        file_id: this.file_id,
        start_line: this.deleteSuggestionOption.value[0],
        end_line: this.deleteSuggestionOption.value[1],
      }).subscribe({
        next: (res: any) => console.info('[单文件视图] manual_selection 已删除', {
          fileId: this.file_id,
          start: this.deleteSuggestionOption.value[0],
          end: this.deleteSuggestionOption.value[1],
          res,
        }),
        error: (err) => console.warn('[单文件视图] manual_selection 删除失败（已忽略）', err),
      });
    } else {
      // todo 增加后端屏蔽建议功能接口
      let body: any = {
        dir_id: this.dir_id,
        file_id: this.file_id,
        change_id: this.deleteSuggestionOption.value[4],
        ignored: true
      };
      this.codeMigApi.updateSuggestionIgnored(body).subscribe({
        next: (response: any) => {
          if (response.code === 0) {
            this.executeDeleteUIUpdate()
          }
        },
      });
    }
  }

  executeDeleteUIUpdate(){
    this.originalSuggestionOptions = this.originalSuggestionOptions.filter(opt => opt.value !== this.deleteSuggestionOption.value);
    if (this.selectedSuggestionOption === this.deleteSuggestionOption.value) {
      this.selectedSuggestionOption = '';
      this.onDeselected(); // 触发原有的清空逻辑
    }
    this.updateSuggestionOptions();
    this.refreshDecorationsAfterDelete();
    this.cdr.detectChanges();
    this.plxMessage.show("success", {
      title: "该建议信息已删除",
      isLightweight: true
    });
    this.deleteSuggestionModal.close();
  }

  /**
   * 删除选项后重新绘制编辑器高亮
   */
  refreshDecorationsAfterDelete() {
    if (!this.editorRef) return;
    const changes = this.suggestionOptions.map(opt => opt.value);
    this.decorateEditor(this.editorRef, changes);
  }

  /**
   * 设置编辑器选择监听器，获取选中的行号
   */
  setupSelectionListener(editor: monaco.editor.IStandaloneDiffEditor) {
    // 先清理之前的监听器
    if (this.selectionDisposable) {
      this.selectionDisposable.dispose();
    }

    // 监听修改侧编辑器的选择变化
    const modifiedEditor = editor.getModifiedEditor();

    this.selectionDisposable = modifiedEditor.onDidChangeCursorSelection((e) => {
      const selection = modifiedEditor.getSelection();
      if (selection) {
        // 判断是否是真正的选择（而不是仅仅光标位置）
        const isRealSelection = this.isRealSelection(selection);

        if (isRealSelection) {
          const startLine = selection.startLineNumber;
          const endLine = selection.endLineNumber;
          const lineCount = endLine - startLine + 1;

          // 更新选中的行号信息
          this.selectedLineNumbers = {
            startLine: startLine,
            endLine: endLine,
            lineCount: lineCount
          };

          // 更新选项列表（包含选中行号）
          this.updateSuggestionOptions();

          // 触发变更检测
          this.cdr.detectChanges();
        } else {
          // 如果没有真正的选择，清空选中行号信息
          if (this.selectedLineNumbers) {
            this.selectedLineNumbers = null;
            this.updateSuggestionOptions();
            this.cdr.detectChanges();
          }
        }
      }
    });
  }

  /**
   * 获取选中的行号信息（用于在页面显示）
   */
  getSelectedLineInfo(): string {
    if (!this.selectedLineNumbers) {
      return '未选中任何行';
    }

    const { startLine, endLine, lineCount } = this.selectedLineNumbers;

    if (startLine === endLine) {
      return `第 ${startLine} 行`;
    } else {
      return `第 ${startLine} - ${endLine} 行（共 ${lineCount} 行）`;
    }
  }

  /**
   * 获取选中的行号范围（用于传递给后端）
   */
  getSelectedLineRange(): { startLine: number; endLine: number } | null {
    if (!this.selectedLineNumbers) {
      return null;
    }

    return {
      startLine: this.selectedLineNumbers.startLine,
      endLine: this.selectedLineNumbers.endLine
    };
  }

  /**
   * 判断是否是真正的选择（而不是仅仅光标位置）
   * @param selection Monaco Editor 的选择对象
   * @returns true 表示是真正的选择，false 表示只是光标位置
   */
  isRealSelection(selection: monaco.Selection | null): boolean {
    if (!selection) {
      return false;
    }

    const startLine = selection.startLineNumber;
    const endLine = selection.endLineNumber;
    const startColumn = selection.startColumn;
    const endColumn = selection.endColumn;

    // 情况1: 选择了多行（跨行选择）
    if (startLine !== endLine) {
      return true;
    }

    // 情况2: 同一行内选择了内容（列位置不同）
    if (startColumn !== endColumn) {
      return true;
    }

    // 情况3: 单行单列位置（只是光标位置，不是选择）
    return false;
  }

  /**
   * 获取包含选中行号选项的完整选项列表
   * 仅 Agent 模式在最前面插入"选择全部建议进行AI生成（默认）"项，作为回到全量批处理的入口；
   * 建议模式不插入该项（折叠状态由 placeholder 文字提示，展开后只剩真实建议）。
   */
  getSuggestionOptionsWithSelectedLine(): Array<IOption> {
    const options: Array<IOption> = [];
    if (this.aiMode === 'agent') {
      options.push({
        label: '选择全部建议进行AI生成（默认）',
        value: CodemigFileChangeViewComponent.PLACEHOLDER_VALUE as any,
        disabled: false
      });
    }
    options.push(...this.originalSuggestionOptions);
    return options;
  }

  /**
   * 更新建议选项列表，将选中行号添加到选项开头
   */
  updateSuggestionOptions() {
    this.suggestionOptions = this.getSuggestionOptionsWithSelectedLine();
  }

  httpQuery(editor: monaco.editor.IStandaloneDiffEditor, afterProcessCallback?: () => void) {
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
    };
    if (this.dependence_id){
      body.dependence_id = this.dependence_id
      this.codeMigApi.getTaskDependenceFileChange(body).subscribe({
        next: (response: any) => {
          this.processFileChangeResponse(editor, response);
          afterProcessCallback?.();
        },
        error: (errorResponse: any) => {
          console.error('❌ getTaskDependenceFileChange 错误:', errorResponse);
        },
      });
    }
    else{
      this.codeMigApi.getTaskFileChange(body).subscribe({
        next: (response: any) => {
          this.processFileChangeResponse(editor, response);
          afterProcessCallback?.();
        },
        error: (errorResponse: any) => {
          console.error('Error: ', errorResponse);
        },
      });
    }
  }

  escapeMarkdownHeaders(text: string): string {
    let result = text.replace(/_/g, '&lowbar;');
    result = text.replace(/#/g, '\\#');
    result = result.replace(/\n/g, '  \n');
    return result;
  }
  processFileChangeResponse(editor: monaco.editor.IStandaloneDiffEditor, response: any) {
    // 恢复查询
    this.init();
    // 处理建议选项，保存到原始选项列表
    this.originalSuggestionOptions = response.changes
    .filter((change: any) => change[6] == 0) 
    .map((change: any) => ({
      label: `第${change[0]}行，${String(change[3])}`,
      value: change,
      disabled: !environment.supportedSolverTypes.has(change[5]),
    }));

    // 更新选项列表（包含选中行号和原始建议选项）
    this.updateSuggestionOptions();
    // 设置编辑器内容
    const diffModel = editor.getModel();

    if (diffModel && diffModel.original && diffModel.modified) {
      diffModel.original.setValue(response.file);
      diffModel.modified.setValue(response.file);
    } else {
      console.error('❌ diff模型未正确初始化，无法设置内容');
    }
    this.decorateEditor(editor, response.changes);

    // 确保选择监听器已设置
    if (this.editorRef) {
      this.setupSelectionListener(this.editorRef);
    }
  }

  /**
   * 处理 original 文件响应
   */
  processOriginalFileResponse(editor: monaco.editor.IStandaloneDiffEditor, response: any) {
    // 恢复查询
    this.init();
    // original 文件没有修改建议，所以建议选项为空
    this.originalSuggestionOptions = [];

    // 更新选项列表（包含选中行号）
    this.updateSuggestionOptions();
    const fileContent = response.file_content || '';
    const diffModel = editor.getModel();
    if (diffModel && diffModel.original && diffModel.modified) {
      diffModel.original.setValue(fileContent);
      diffModel.modified.setValue(fileContent);
    } else {
      console.error('❌ diff模型未正确初始化，无法设置内容');
    }
    this.loading = false;
  }

  /**
   * Agent模式下，AI查询完成后刷新diff页面
   * 左侧显示origin文件，右侧显示change文件
   */
  refreshDiffAfterAgentQuery() {
    if (!this.editorRef) {
      console.error('❌ 编辑器引用未初始化，无法刷新diff');
      return;
    }

    // 构建请求体
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
    };

    if (this.dependence_id) {
      body.dependence_id = this.dependence_id;
      // 依赖任务使用 getTaskDependenceFileChange
      this.codeMigApi.getTaskDependenceFileChange(body).subscribe({
        next: (response: any) => {
          this.updateDiffEditorAfterAgentQuery(response);
        },
        error: (errorResponse: any) => {
          console.error('❌ 刷新diff页面失败 (依赖任务):', errorResponse);
        },
      });
    } else {
      // 普通任务使用 getTaskFileChange
      this.codeMigApi.getTaskFileChange(body).subscribe({
        next: (response: any) => {
          this.updateDiffEditorAfterAgentQuery(response);
        },
        error: (errorResponse: any) => {
          console.error('❌ 刷新diff页面失败:', errorResponse);
        },
      });
    }
  }

  /**
   * 更新diff编辑器内容（agent模式查询完成后）
   * 参考 processOriginalFileResponse 的实现方式
   */
  updateDiffEditorAfterAgentQuery(response: any) {
    if (!this.editorRef) {
      console.error('❌ 编辑器引用未初始化');
      return;
    }

    const diffModel = this.editorRef.getModel();
    if (!diffModel || !diffModel.original || !diffModel.modified) {
      console.error('❌ diff模型未正确初始化，无法设置内容');
      return;
    }

    // 获取原始文件和修改后的文件内容
    const originalFile = response.original_file || '';
    const modifiedFile = response.file || '';
    // 设置左侧（original）和右侧（modified）文件内容
    diffModel.original.setValue(originalFile);
    diffModel.modified.setValue(modifiedFile);

    // 如果有变更建议，更新装饰和建议选项列表
    if (response.changes && Array.isArray(response.changes)) {
      this.originalSuggestionOptions = response.changes
        .filter((change: any) => change[6] == 0)
        .map((change: any) => ({
          label: `第${change[0]}行，${String(change[3])}`,
          value: change,
          disabled: !environment.supportedSolverTypes.has(change[5]),
        }));
      this.updateSuggestionOptions();
      this.decorateEditor(this.editorRef, response.changes);
    }

    // 强制刷新编辑器布局
    this.editorRef.layout();

    // 延迟刷新确保显示正确
    setTimeout(() => {
      if (this.editorRef) {
        this.editorRef.layout();
      }
    }, 100);
  }

  updateDecorations(
    model: any,
    decorations: any[],
    startLineNumber: any,
    endLineNumber: any,
    append_or_replace: any,
    change_diff: any
  ) {
    const lineLength = model.getLineLength(endLineNumber);
    const diff = this.escapeMarkdownHeaders(change_diff);
    const markdownContent = {
      value: `**💡 建议**${this.createSuggestion(append_or_replace)}: ${diff}`,
    };
    decorations.push({
      range: new monaco.Range(
        startLineNumber,
        1,
        endLineNumber,
        lineLength + 1
      ),
      options: {
        beforeContentClassName: 'my-icon',
        inlineClassName: 'underline-suggestion',
        hoverMessage: markdownContent,
        overviewRuler: {
          color: '#FFA500', // 橙色
          position: monaco.editor.OverviewRulerLane.Full,
        },
      },
    });
    decorations.push({
      range: new monaco.Range(
        startLineNumber,
        1,
        endLineNumber,
        lineLength + 1
      ),
      options: {
        isWholeLine: true,
        className: 'line-modified',
      },
    });
  }

  updateDecorationsStartLine(model: any, decorations: any[], change: any) {
    this.updateDecorations(
      model,
      decorations,
      change[0],
      change[0],
      change[2],
      change[3]
    );
  }

  updateDecorationsEndLine(model: any, decorations: any[], change: any) {
    this.updateDecorations(
      model,
      decorations,
      change[1],
      change[1],
      change[2],
      change[3]
    );
  }

  updateDecorationsLine(model: any, decorations: any[], change: any) {
    this.updateDecorations(
      model,
      decorations,
      change[0],
      change[1],
      change[2],
      change[3]
    );
  }

  decorateEditor(editor: monaco.editor.IStandaloneDiffEditor, changes: any) {
    const model: any = editor.getModel()?.modified;
    let decorations: any[] = [];
    for (const change of changes) {
      const suggestion_type = change[5];
      const ignored = change[6];
      if (ignored) {
        // 跳过忽略的建议
        continue;
      }

      switch (suggestion_type) {
        case SolverType.MACROS:
          this.updateDecorationsStartLine(model, decorations, change);
          this.updateDecorationsEndLine(model, decorations, change);
          break;
        case SolverType.ASM_FILE:
          this.updateDecorationsStartLine(model, decorations, change);
          break;
        default:
          this.updateDecorationsLine(model, decorations, change);
      }
    }
    if (this.decorationsCollection) {
      this.decorationsCollection.clear();
    }
    this.decorationsCollection =
      editor.createDecorationsCollection(decorations);
  }

  createSuggestion(append_or_replace: any) {
    switch (append_or_replace) {
      case 0:
        return '添加';
      case 1:
        return '替换';
      case 2:
        return '';
      default:
        return '未知操作';
    }
  }

  startResize(event: MouseEvent) {
    this.isResizing = true;
    document.addEventListener('mousemove', this.resize);
    document.addEventListener('mouseup', this.stopResize);
    event.preventDefault();
  }

  resize = (e: MouseEvent) => {
    if (!this.isResizing) return;

    const container = document.querySelector('.editor-container')!.getBoundingClientRect();
    const totalWidth = container.width;
    const mouseX = e.clientX - container.left;

    // 计算新比例（保持最小宽度限制）
    const leftPercent = Math.max(30, Math.min(70, (mouseX / totalWidth) * 100));
    this.leftPanelFlex = Math.round(leftPercent);
    this.rightPanelFlex = 100 - this.leftPanelFlex;
  }

  stopResize = () => {
    this.isResizing = false;
    document.removeEventListener('mousemove', this.resize);
    document.removeEventListener('mouseup', this.stopResize);
  }

  // 组件销毁时移除监听
  ngOnDestroy() {
    document.removeEventListener('mousemove', this.resize);
    document.removeEventListener('mouseup', this.stopResize);

    // 清理选择监听器
    if (this.selectionDisposable) {
      this.selectionDisposable.dispose();
      this.selectionDisposable = null;
    }
  }

  refreshFileTree() {
    this.codemigFileSidebarService.freshFileTree();
  }
}
