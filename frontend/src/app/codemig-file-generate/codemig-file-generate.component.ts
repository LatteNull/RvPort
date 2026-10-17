import { Component, ChangeDetectorRef, ViewChild, ElementRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Router } from '@angular/router';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.js';
import { PlxMessage, PlxModal } from 'paletx';
import { LogoutService } from '../services/logout.service'
import { CodeMigApi } from '../api/codemig-api.service'
import { Clipboard } from '@angular/cdk/clipboard';
import { CodemigFileSidebarService } from '../services/codemig-file-sidebar.service';
import { AgentManagementApi, ApiKeyItem, ModelOption  } from '../api/agent-management-api.service';
import { TreeNode } from 'paletx';
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
  selector: 'app-codemig-file-generate',
  templateUrl: './codemig-file-generate.component.html',
  styleUrls: ['./codemig-file-generate.component.css', '../../assets/markdown/markdown.css'],
  standalone: false,
})
export class CodemigFileGenerateComponent {
  user_name: any;
  task_id!: number;
  dir_id!: number;
  file_id!: number;
  dependence_id!: number;
  source_file_id!: number;
  editorRef!: monaco.editor.IStandaloneDiffEditor;
  originalModel: any = { value: '' };
  modifiedModel: any = { value: '' };
  modelOptions: ModelOption[] = [];
  apikeyList: ApiKeyItem[] = [];
  selectedModel: string = ''; // 选中的模型
  lastSavedContent: string = ''; // 保存最近存储的文件内容
  selectedApiformat: string = '';
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
    originalEditable: false,
    enableSplitViewResizing: true,
    renderSideBySide: false,
  };

  // 新增AI查询相关内容
  aiMode: string = 'agent'
  isGenerating: boolean = false; // 新增：标记是否正在生成中

  // 点赞/点踩选中状态，再次点击取消选中
  isLiked = false;
  isDisliked = false;
  isCleared = false;
  abortController: AbortController | null = null;
  currentRequestId = 0;
  currentRequestUUID : string = '';
  // suggestion 经 getter/setter 拦截：写入时剥离裸 s/strike/del 标签，
  // 根治未闭合 <s> 吞兄弟节点导致的"后面全部内容带删除线"（见文件头部注释）。
  // init、生成、reopen 恢复、流式追加等全部赋值路径对 getter/setter 透明。
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
  showAIPanel = false;

  leftPanelFlex = 6;
  rightPanelFlex = 4;
  isResizing = false;

  dir_icon: any = '📂  ';
  file_icon: any = '📄  ';
  treeNodes: TreeNode[] = [];
  selectTreeNodes: any[] = [];
  @ViewChild('treeModal') treeModal!: any;
  modalInstance: any;

  constructor(
    private codeMigApi: CodeMigApi,
    private agentApi: AgentManagementApi,
    private route: ActivatedRoute,
    private router: Router,
    private plxMessage: PlxMessage,
    private cdr: ChangeDetectorRef,
    private logoutService: LogoutService,
    private clipboard: Clipboard,
    private codemigFileSidebarService: CodemigFileSidebarService,
    private plxModal: PlxModal,
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  init(){
    this.showAIPanel = false
    this.suggestion = ``
  }

  onEditorInit(editor: monaco.editor.IStandaloneDiffEditor) {
    this.editorRef = editor;
    this.route.queryParams.subscribe((params) => {
        this.task_id = Number(params['task_id']);
        this.dir_id = Number(params['dir_id']);
        this.file_id = Number(params['file_id']);
        this.dependence_id = Number(params["dependence_id"]);
        this.source_file_id = Number(params["source_file_id"]);
        this.init()
        // 检查文件是否存在
        this.checkFileExists();
        this.genetate_getApikeyList();
      });
  }

  async genetate_getApikeyList(){
    this.apikeyList = await this.agentApi.getSavedKeyByModel();
    // 获取API Key列表
    const data = this.apikeyList  || [];
    this.modelOptions = this.agentApi.extractUniqueModels(
      data, this.user_name, localStorage.getItem('userRole') === 'admin');
    this.selectedModel = this.agentApi.selectedModel;
    this.selectedApiformat = this.agentApi.selectedApiformat;
  }

  /**
    选择模型改变时触发
  */
  onModelChange(model: string): void {
    this.selectedModel = model;
    // 根据 model 从 modelOptions 中找到对应的 api_format
    const selectedOption = this.modelOptions.find(opt => opt.value === model);
    this.selectedApiformat = selectedOption?.api_format || '';
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

  transformNode(nodeData: any, taskId: any, dirId: any, fileId: any, parentPath: string = ''): any {
    const isDirectory = nodeData.type === 'dir';
    // 拼接完整路径
    const fullPath = parentPath === ''
        ? nodeData.name
        : (parentPath.endsWith('/') ? parentPath : parentPath + '/') + nodeData.name;

    const newNode: any = {
      task_id: taskId,
      dir_id: dirId,
      file_id: fileId,
      label: (isDirectory ? this.dir_icon : this.file_icon) + nodeData.name,
      data: fullPath,
      isLeaf: !isDirectory,
      expanded: true,
      children: []
    };

    // 递归处理子节点
    if (isDirectory && nodeData.children && Array.isArray(nodeData.children)) {
      newNode.children = nodeData.children.map((child: any) => {
        return this.transformNode(child, taskId, dirId, fileId, fullPath);
      });
    }
    return newNode;
  }

  getTreeNodes(data: any[]) {
    return data.map((item: any, index: number) => {
      const rawData = item[3];
      const isDirectory = item[4] === 1;

      // 如果索引3是对象且是目录
      if (isDirectory && typeof rawData === 'object') {
        // 调用上面的递归函数处理可能的嵌套
        return this.transformNode(rawData, item[0], item[1], item[2], '');
      } else {
        // 如果是普通文件（字符串）
        const filePath = typeof rawData === 'string' ? rawData : rawData.name;
        return {
          task_id: item[0],
          dir_id: item[1],
          file_id: item[2],
          label: this.file_icon + filePath,
          data: filePath,
          isLeaf: true,
          children: []
        };
      }
    });
  }


  // 生成按钮点击事件 - 暂时留空
  showModal() {
    if (this.dependence_id){
      this.plxMessage.show("warning", {
        title: "依赖包生成文件暂未支持",
        isLightweight: true
      })
      return;
    }
    if (this.selectedModel == ''){
      this.plxMessage.show("warning", {
        title: "请选择模型",
        isLightweight: true
      })
      return;
    }
    if (this.treeNodes.length === 0){
      let id = this.file_id;
      if (this.source_file_id){
        id = this.source_file_id;
      }
      const body = { 'user_name': this.user_name, 'file_id': id, 'task_id': this.task_id, 'dir_id': this.dir_id };
      this.codeMigApi.getTaskExistingArch(body).subscribe({
        next: (response: any) => {
          if (response.code === 0){
            this.treeNodes = this.getTreeNodes(response.data);
          }
        },
      });
    }
    this.modalInstance = this.plxModal.open(this.treeModal, { size: 'sm' })
  }

  onTreeSelectionChange(event: any) {
    // event 就是当前所有被选中的节点数组
    this.selectTreeNodes = event;
  }

  generateFile(){
    if (this.selectTreeNodes.length === 0){
      this.plxMessage.show("warning", {
        title: "请选择参考文件",
        isLightweight: true
      })
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
    this.currentRequestUUID = this.agentApi.getRandomUUID();
    this.abortController = new AbortController();
    let id = this.file_id;
    if (this.source_file_id){
      id = this.source_file_id;
    }
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: id,
      request_uuid: this.currentRequestUUID,
      model: this.selectedModel,
      api_format: this.selectedApiformat,
      reference_arch_paths: this.selectTreeNodes.map((node: any) => node.data),
    };
    const diffModel = this.editorRef.getModel();
    if (diffModel && diffModel.original && diffModel.modified) {
      diffModel.original.setValue("文件生成中...");
      diffModel.modified.setValue("文件生成中...");
    } else {
      console.error('❌ diff模型未正确初始化，无法设置内容');
    }
    this.modalInstance.close()
    this.isLiked = false;
    this.isDisliked = false;
    const url = this.codeMigApi.getTaskFileGenerateUrl()
    this.queryAI(url, body, requestId)
  }

  // 检查文件是否存在
  checkFileExists() {
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
    };

    if (this.dependence_id) {
      body.dependence_id = this.dependence_id;
    }

    this.codeMigApi.checkFileExists(body).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          if (response.file_exists) {
            // 文件存在，显示文件内容
            const fileContent = response.file_content || '';
            // 保存最近存储的内容，用于生成文件时的原始版本
            this.lastSavedContent = fileContent;
            const diffModel = this.editorRef.getModel();
            if (diffModel && diffModel.original && diffModel.modified) {
              diffModel.original.setValue(fileContent);
              diffModel.modified.setValue(fileContent);
            } else {
              console.error('❌ diff模型未正确初始化，无法设置内容');
            }
          } else {
            // 文件不存在，显示默认提示
            const defaultText = "点击生成按钮使用AI Agent生成文件";
            this.lastSavedContent = '';
            const diffModel = this.editorRef.getModel();
            if (diffModel && diffModel.original && diffModel.modified) {
              diffModel.original.setValue(defaultText);
              diffModel.modified.setValue(defaultText);
            } else {
              console.error('❌ diff模型未正确初始化，无法设置内容');
            }
          }
        } else {
          console.error('Error checking file exists: ', response.msg);
          const defaultText = "点击生成按钮使用AI Agent生成文件";
          this.lastSavedContent = '';
          const diffModel = this.editorRef.getModel();
          if (diffModel && diffModel.original && diffModel.modified) {
            diffModel.original.setValue(defaultText);
            diffModel.modified.setValue(defaultText);
          } else {
            console.error('❌ diff模型未正确初始化，无法设置内容');
          }
        }
      },
      error: (errorResponse: any) => {
        console.error('Error checking file exists: ', errorResponse);
        const defaultText = "点击生成按钮使用AI Agent生成文件";
        this.lastSavedContent = '';
        const diffModel = this.editorRef.getModel();
        if (diffModel && diffModel.original && diffModel.modified) {
          diffModel.original.setValue(defaultText);
          diffModel.modified.setValue(defaultText);
        } else {
          console.error('❌ diff模型未正确初始化，无法设置内容');
        }
      },
    });
  }

  // 保存文件按钮点击事件
  saveFile() {
    const diffModel = this.editorRef.getModel();
    const content = diffModel && diffModel.modified ? diffModel.modified.getValue() : '';
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      content: content,
    };

    if (this.dependence_id) {
      body.dependence_id = this.dependence_id;
    }
  
    this.codeMigApi.saveFileContent(body).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          this.plxMessage.success('文件保存成功', '');
          // 保存成功后，更新 lastSavedContent
          this.lastSavedContent = content;
          // 更新 original 为新保存的内容
          const diffModel = this.editorRef.getModel();
          if (diffModel && diffModel.original) {
            diffModel.original.setValue(content);
          }

          if (!this.source_file_id){
            // 没有source_file_id，表示尚未生成文件； 
            // 是在缺失文件状态下直接保存，需要刷新文件树；
            this.freshFileTree();
          }
        } 
        // else {
        //   this.plxMessage.error('文件保存失败: ' + response.msg, '');
        // }
      },
      error: (errorResponse: any) => {
        console.error('Error saving file: ', errorResponse);
        this.plxMessage.error('文件保存失败', '');
      },
    });
  }

  // 保存并回退文件
  saveAndRollback() {
    const diffModel = this.editorRef.getModel();
    const content = diffModel && diffModel.modified ? diffModel.modified.getValue() : '';
    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: this.file_id,
      content: content,
    };

    if (this.dependence_id) {
      body.dependence_id = this.dependence_id;
    }

    // 先保存，保存成功后再回退
    this.codeMigApi.saveFileContent(body).pipe(
      switchMap((saveResponse: any) => {
        if (saveResponse.code === 0) {
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
        } 
        return of({ code: -1, msg: '当前内容保存失败' });
      })
    ).subscribe({
      next: (rollbackResponse: any) => {
        if (rollbackResponse.code === 0) {
          this.plxMessage.success('文件回退成功', '');
          // 回退成功后重新加载文件内容
          this.checkFileExists();
        }
      },
      error: (errorResponse: any) => {
        // console.error('Error rollback file: ', errorResponse);
        this.plxMessage.error('文件回退失败', '');
      },
    });
  }

  // 返回按钮点击事件
  goBack() {
    // 跳转回到任务页面
    if (this.dependence_id) {
      this.router.navigate(['/codemig/dependence'], {
        queryParams: { task_id: this.task_id, dependence_id: this.dependence_id },
      });
    } else {
      this.router.navigate(['/codemig/task'], {
        queryParams: { task_id: this.task_id },
      });
    }
  }
  freshFileTree() {
    this.codemigFileSidebarService.freshFileTree();
  }

  toggleAIPanel() {
    this.showAIPanel = !this.showAIPanel;
    if (this.showAIPanel && !this.isCleared && !this.isGenerating) {
      this.loadAiSuggestionOnReopen();
    }
  }

  /** 显示 AI 面板时从后端拉取已保存的 AI 建议 */
  loadAiSuggestionOnReopen() {
    let id = this.file_id;
    if (this.source_file_id){
      id = this.source_file_id;
    }
    const body = {
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: id,
    };
    this.agentApi.reopenAiSuggestion(body).subscribe({
      next: (res: any) => {
        if (res?.code === 0 && res?.data != null) {
          this.suggestion = res.data;
          this.getAiScore();
        }
      },
      error: () => {},
    });
  }

  /** 获取AI建议的评分状态 */
  getAiScore() {
    let id = this.file_id;
    if (this.source_file_id){
      id = this.source_file_id;
    }
    const body = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: id,
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

  async queryAI(url: string, payload: any, requestId: any){
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
                }else if (jsonData.status === 2) {
                  let body: any = {
                    user_name: this.user_name,
                    task_id: this.task_id,
                    dir_id: this.dir_id,
                    file_id: this.file_id,
                  };
                  this.codeMigApi.checkFileExists(body).subscribe({
                    next: (response: any) => {
                      if (response.code === 0) {
                        const hasContent = response.file_exists && response.file_content;
                        const diffModel = this.editorRef.getModel();
                        if (hasContent && diffModel && diffModel.original && diffModel.modified) {
                          this.plxMessage.show("success", {
                            title: "文件生成成功",
                            isLightweight: true
                          });
                          // 将最近存储的内容设置到 original，新生成的内容设置到 modified
                          diffModel.original.setValue(this.lastSavedContent);
                          diffModel.modified.setValue(response.file_content);
                          // 更新 lastSavedContent 为最新内容
                          this.lastSavedContent = response.file_content;
                        } else if (!hasContent && diffModel && diffModel.original && diffModel.modified) {
                          this.plxMessage.show("success", {
                            title: "目录级别文件生成成功，请点击目录文件查看",
                            isLightweight: true
                          });
                          const defaultText = "目录级别文件生成成功，请点击目录文件查看";
                          diffModel.original.setValue(defaultText);
                          diffModel.modified.setValue(defaultText);
                        }
                      }
                    }
                  });
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
        if (this.aiMode === 'agent') {
          this.freshFileTree();
        }
        this.abortController = null;
      }
    }
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
    this.isGenerating = false;
    //取消后不显示内容
    const diffModel = this.editorRef.getModel();
    if (diffModel && diffModel.original && diffModel.modified) {
      diffModel.original.setValue("");
      diffModel.modified.setValue("");
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
    let id = this.file_id;
    if (this.source_file_id){
      id = this.source_file_id;
    }
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: id,
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
    let id = this.file_id;
    if (this.source_file_id){
      id = this.source_file_id;
    }
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_id: id,
      score: 0, // 点踩 (0-4)
    };
    this.agentApi.setAiScore(body).subscribe({
      next: (response: any) => {
        console.log(response.msg);
        this.plxMessage.success("点踩成功", "")
        this.getAiScore();
      },
    });
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
}
