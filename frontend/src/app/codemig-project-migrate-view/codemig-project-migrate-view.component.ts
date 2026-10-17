import { Component, ChangeDetectorRef, OnInit, ViewChild, ElementRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Router } from '@angular/router';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.js';
import { PlxMessage, PlxModal } from 'paletx';
import { Clipboard } from '@angular/cdk/clipboard';
import { Subscription } from 'rxjs';
import { LogoutService } from '../services/logout.service'
import { CodeMigApi } from '../api/codemig-api.service'
import { ApiKeyItem, ModelOption, AgentManagementApi } from '../api/agent-management-api.service'
import { SolverType } from '../environment/solver-type'
import { ProjectMigrateStateService } from '../services/project-migrate-state.service';
import { CodemigFileSidebarService } from '../services/codemig-file-sidebar.service';

// v4.x.0-RUN-FLOW：运行流程节点模型
//   - 节点状态：idle 未开始 / ready 就绪 / running 运行中 / success 完成 / error 失败
//   - 节点 ID 对应 2 个 skill：migrate / ut_test
//   - ★ 串行门禁：②③ 需上游 success 才 runnable（predecessorOf / gateBlockReason /
//     refreshRunnability 三件套 + runFlowNode / resumeNode 运行时二次校验）
//   - 旧的 'blocked'（"等待前序节点完成"）已废除：没有节点需要该状态
export type FlowNodeStatus =
  | 'idle'
  | 'ready'
  | 'running'
  | 'success'
  | 'error'
  | 'interrupted';

export type FlowNodeId =
  | 'migrate'
  | 'ut_test'

export interface FlowNode {
  id: FlowNodeId;
  index: string;             // '1' | '2' | '3'
  label: string;              // '代码生成' | '功能验证' | '性能优化'
  description: string;        // 来自 skill description
  status: FlowNodeStatus;
  collapsed: boolean;
  running: boolean;
  runnable: boolean;          // 前置条件是否满足
  items: any[];               // 节点任务清单
  errorMessage?: string;
  // ★ v4.x.0-RESUME：是否含可恢复 qwen 会话（由 refreshResumableStatus 写入）
  hasResumableSession?: boolean;
}

// 流式输出中的 think 边界标签（pi 协议 <think/>/</think/> 与历史 <think>/</think>，
// 含流开头的引导 </think>）。不再据此做思考/正文分流——流式期间无法保证标签
// 序列完整（后端多协议变体），分流一旦失配内容会整体卡进思考折叠区且刷新后
// 又消失。改为与刷新后 reopen 恢复行为一致：剥掉标签本身，思考与正文一律
// 按普通文本进建议面板。
const THINK_TAG_VARIANTS = ['<think/>', '</think/>', '<think>', '</think>'] as const;

// AI/Agent 流式输出可能携带裸的 <s>/<strike>/<del> 原始 HTML 标签（如回显
// HTML/JSP 源码）。marked 透传 + Angular 消毒器白名单放行后，未闭合的 <s> 在
// innerHTML 片段解析时会吞掉其后所有兄弟节点，渲染成"后面全部内容带删除线"。
// 在数据层直接剥离这三个纯样式标签（不触碰 details/summary/div 等结构标签）。
// 注：统一剥除包括代码围栏内的字样（不做围栏感知，换取零回溯的单遍扫描）。
const STRIKE_TAGS = ['s', 'strike', 'del'] as const;

const STRIKE_TAG_PATTERNS: ReadonlyArray<{ open: RegExp; close: RegExp }> = STRIKE_TAGS.map(
  (tag) => ({
    // 开标签：`<s>`、`<s attr>`；负向前瞻排除 `</s>` 与 `<span>` 等更长标签名
    open: new RegExp(`<${tag}(?![a-zA-Z0-9_-])[^>]*>`, 'g'),
    close: new RegExp(`</${tag}\\s*>`, 'g'),
  }),
);

// 匹配 ``` 围栏行（含前导空白）；块内围栏据此识别
const FENCE_LINE_RE = /^(\s*)`{3,}/;

/**
 * <details> 折叠块内的 ``` 围栏行统一加 4 空格缩进。
 *
 * 背景：模型在思考折叠块内输出的裸 ``` 围栏（模型不知道自己正在 HTML 块里写
 * markdown）经 marked 按 CommonMark 解析，一个未闭合围栏会把块后所有内容吞进
 * 一个巨型代码块——其后全部 <details>/</details> 被转义成纯文本，表现为
 * "思考和正文全包在一个思考块里"，同时折叠块元素消失导致展开态回放失效。
 *
 * 后端已在流式（换行缓冲）与入库出口做过同样清洗，这里是前端最后一道兜底：
 * ① 兼容历史入库数据（清洗上线前的记录）；② 兜住任何后端遗漏路径。
 * 缩进 ≥4 的 ``` 不再是围栏语法（渲染为缩进代码块），失配从根上消除。
 * 块外正文围栏原样保留，代码高亮不受影响。
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
  selector: 'app-codemig-project-migrate-view',
  templateUrl: './codemig-project-migrate-view.component.html',
  styleUrls: ['./codemig-project-migrate-view.component.css', '../../assets/markdown/markdown.css'],
  standalone: false,
})
export class CodemigProjectMigrateViewComponent implements OnInit {
  user_name: any;
  task_id!: number;
  dir_id!: number;

  showAIPanel = false;
  isGenerating: boolean = false;
  isCleared = false;

  // ─── 超长 AI 建议的渲染保护 ───
  // 后端恢复（reopen_project_ai）或异常中断入库的 Agent 全量过程日志可能达数 MB，
  // 一次性交给 markdown 渲染会长时间阻塞主线程（刷新即卡死的根因之一）。
  // 策略：_suggestion 始终保留完整数据（复制/评分等逻辑不受影响），
  // suggestion getter 返回 clamp 后的渲染文本；超出上限时先截断展示并提示
  // "展开完整内容"，由用户显式点击再全量渲染。
  static readonly SUGGESTION_RENDER_LIMIT = 200_000; // 渲染上限（约 200KB）
  suggestionRenderClipped = false;
  suggestionRenderExpanded = false;

  private _suggestion: string = '';

  // ── 流式渲染时 <details> 展开状态保持 ──
  // ngx-markdown 每次 [data] 变化都整块替换 innerHTML，<details> 的展开态存在
  // DOM 上（不在 markdown 源串里），流式期间每 ~200ms 一次的重渲染会把它销毁
  // 重建为缩略态——表现为"点击展开闪一下又缩回"。修复：赋值前快照当前所有
  // 已展开 <details> 的锚点（summary 文本 + 同名出现次序），渲染完成后按锚点回放。
  @ViewChild('suggestionMarkdown') suggestionMarkdownRef?: ElementRef<HTMLDivElement>;
  /** 最近一次渲染前快照的已展开 details 锚点集合 */
  private openDetailsAnchors: string[] = [];

  get suggestion(): string {
    if (!this.suggestionRenderClipped || this.suggestionRenderExpanded) {
      return this._suggestion;
    }
    const limit = CodemigProjectMigrateViewComponent.SUGGESTION_RENDER_LIMIT;
    const omitted = this._suggestion.length - limit;
    return (
      this._suggestion.slice(0, limit) +
      `\n\n…（内容过长已截断，省略 ${omitted} 字符；完整长度 ${this._suggestion.length} 字符）`
    );
  }

  set suggestion(value: string) {
    // 重渲染前快照当前已展开的 <details>（用户点击产生的 open 状态只存在于
    // DOM 上，innerHTML 整块替换后即丢失），渲染完成后在 onSuggestionRenderReady
    // 里按锚点回放。
    this.snapshotOpenDetails();
    // 历史版本后端在每个 input_json_delta 上都下发 "<div>"，导致库中存量的
    // 过程日志包含成千上万个未闭合 <div>（markdown 渲染生成深层嵌套 DOM）。
    // 新数据已修复，这里对恢复/追加的数据做兜底清洗。
    // 围栏清洗同理：折叠块内裸 ``` 会让 marked 吞掉块后内容（详见
    // sanitizeFencesInDetails 注释），后端已洗，此处兜底历史数据与遗漏路径。
    const cleaned = typeof value === 'string'
      ? sanitizeFencesInDetails(
          this.stripStrikeTags(this.cleanSuggestionForRender(value)))
      : value;
    this._suggestion = cleaned;
    this.suggestionRenderClipped =
      cleaned.length > CodemigProjectMigrateViewComponent.SUGGESTION_RENDER_LIMIT;
    if (!this.suggestionRenderClipped) {
      this.suggestionRenderExpanded = false;
    }
  }

  /** 收集当前 DOM 中所有已展开 <details> 的锚点（summary 文本 + 同名出现次序），用于重渲染后回放展开态 */
  private snapshotOpenDetails(): void {
    const host = this.suggestionMarkdownRef?.nativeElement;
    if (!host) return;
    const list = host.querySelectorAll<HTMLDetailsElement>('details');
    if (list.length === 0) { this.openDetailsAnchors = []; return; }
    // 仅按 summary 文本匹配（不用全局序号）：流式期间每 200ms 整块重渲染一次，
    // 新增折叠块会让全局序号整体后移，序号锚点必然失配——表现为"手动展开的
    // 块在下一帧又缩回"。同名 summary（多条思考过程/多轮工具调用）用出现
    // 次序区分，顺序稳定。
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

  /**
   * 清洗 markdown 渲染前的建议文本：
   * - 移除独立成行的 "<div>" 噪声行（历史 input_json_delta 累积的未闭合标签）。
   * 仅按行精确匹配，不会误伤正文中的 HTML 片段。
   */
  private cleanSuggestionForRender(text: string): string {
    if (!text || !text.includes('<div>')) return text;
    return text
      .split('\n')
      .filter(line => line.trim() !== '<div>')
      .join('\n');
  }

  /**
   * 剥离裸的 s/strike/del 标签（开+闭），根治未闭合 <s> 吞兄弟节点导致的
   * "后面全部内容带删除线"。无标签时返回原引用，避免流式热路径上每 200ms
   * 全量重赋值产生多余字符串分配。
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

  /** 用户显式点击"展开完整内容"：全量渲染（可能较慢，仅在用户要求时发生） */
  expandSuggestionRender(): void {
    this.snapshotOpenDetails(); // 不走 setter，但 getter 返回值变化同样触发整块重渲染
    this.suggestionRenderExpanded = true;
    this.cdr.markForCheck();
  }

  isLiked = false;
  isDisliked = false;

  abortController: AbortController | null = null;
  currentRequestUUID: string = '';

  // ─── 会话保活心跳（SESSION-KEEPALIVE） ───
  // 背景：流式迁移响应（is_streamed）与任务列表轮询（auto_refesh_url）都不会
  // 刷新后端会话空闲计时（bp.py update_session_exp_time）。长任务（如 qemu
  // 功能验证跑数小时）期间用户没有任何普通请求，会话到期后收尾请求全部 401，
  // 前端弹"身份验证失效"强制登出——迁移实际成功却表现得像失败。
  // 方案：任务运行期间（isGenerating=true）每 10 分钟发一个轻量 GET
  // /codemig/version（非流式、不在 auto_refesh_url 黑名单）续期会话；
  // 任务结束/取消/组件销毁即停，不影响"挂机登出"的设计初衷。
  private sessionKeepaliveTimer: any = null;
  private static readonly SESSION_KEEPALIVE_INTERVAL_MS = 10 * 60 * 1000;

  /** 启动会话保活心跳（幂等：已在跑则不重置计时） */
  private _startSessionKeepalive(): void {
    if (this.sessionKeepaliveTimer) return;
    this.sessionKeepaliveTimer = setInterval(() => {
      // 心跳失败不打扰用户：会话若已过期（401），收尾请求自会走登出流程；
      // 瞬时网络抖动重试下一轮即可。
      this.http.get<any>('/action/plugin/codemig/version').subscribe({
        error: (err) => console.warn('[keepalive] 会话心跳失败（下轮重试）', err?.status),
      });
    }, CodemigProjectMigrateViewComponent.SESSION_KEEPALIVE_INTERVAL_MS);
  }

  /** 停止会话保活心跳（幂等） */
  private _stopSessionKeepalive(): void {
    if (this.sessionKeepaliveTimer) {
      clearInterval(this.sessionKeepaliveTimer);
      this.sessionKeepaliveTimer = null;
    }
  }

  selectedModel: string = '';
  selectedApiformat: string = '';
  apikeyList: ApiKeyItem[] = [];
  modelOptions: ModelOption[] = [];
  showModelSelect = true;

  // ★ v4.x.0-RUN-FLOW：当前正在运行的流程节点（由 runMigrateNode / _streamSkillStage 设置）
  //   - queryAI / _consumeAgentStream 完成时，根据本字段更新对应节点的 status（running / success / error）
  //   - 这样 ①代码生成 (调 check→queryAI) 与 ②③ (调 _streamSkillStage→_consumeAgentStream)
  //     共用同一套状态机，徽章 + 顶部 X/3 完成 计数才能正确刷新
  activeRunNode: FlowNode | null = null;

  leftPanelFlex = 5;
  rightPanelFlex = 4;

  // ─── 迁移历史（reflog 驱动，供下拉框回退与 patch 选择） ───
  selectedHistoryHash = '';           // 历史下拉框选中值（空=不选，走默认行为）
  historyList: Array<{
    hash: string;
    short_hash: string;
    label: string;
    time: string;
    message: string;
    is_current: boolean;
  }> = [];
  loadingHistory = false;

  // ─── 增量 Patch 弹窗（起点+终点） ───
  showPatchDialog = false;
  patchFromHash = '';
  patchToHash = '';
  exportingPatch = false;

  // 下拉框 options（必须是稳定引用，否则 plx-select 每次变更检测会重置面板导致选不中）
  historyOptions: Array<{ value: string; label: string }> = [];
  patchToOptions: Array<{ value: string; label: string }> = [];

  // ─── 文件列表 ───
  fileList: Array<{
    file_id: number;
    file_name: string;
    file_path: string;
    file_source?: 'changed' | 'missing' | 'generated';  // 文件来源标识（missing=缺失文件红色，generated=迁移新增文件绿色）
    num_changed_lines: number;
    solver_description?: string;
    expanded: boolean;  // 新增：是否展开显示建议详情
    aiSuggestions?: Array<{  // 新增：AI生成的建议
      start_line: number;
      end_line: number;
      type: string;
      reason: string;
      new_code?: string;
    }>;
    manualSelections?: Array<{  // 新增：用户手动选中的范围
      start_line: number;
      end_line: number;
    }>;
    totalSuggestions: number;  // 新增：总建议数（AI + 手动）
    // 关键修复（阶段 13.x-AI-SUGGESTIONS-LOAD-1）：标记 AI 建议是否已经加载过
    // 避免用户加了 manualSelection 后展开下拉框时 totalSuggestions > 0 导致 loadFileSuggestions 被跳过
    _aiSuggestionsLoaded?: boolean;
  }> = [];
  selectedFileId: number | null = null;
  loadingFileList = false;

  // ★ v4.x.0-RUN-FLOW：2 个流程节点（对应 2 个 skill 阶段）
  //   ① 代码生成（migrate）：复用现有 fileList，无前置
  //   ② 功能验证（ut_test）：串行门禁——需 ① success（refreshRunnability 解锁）
  // runnable 初值：① true；② false（等 restoreFlowStatusFromHistory /
  // onNodeSuccess 按上游实际状态解锁）。运行时另有 runFlowNode 入口二次校验兜底。
  flowNodes: FlowNode[] = [
    {
      id: 'migrate',
      index: '1',
      label: '代码生成',
      description: '将原本是x86/arm架构的工程或者代码，扫描分析，然后迁移到riscv架构平台',
      status: 'ready',
      collapsed: false,
      running: false,
      runnable: true,
      items: [],
    },
    {
      id: 'ut_test',
      index: '2',
      label: '功能验证',
      description: '为x86/arm和riscv汇编文件生成全面的C语言单元测试，包含main.c文件和Makefile',
      status: 'ready',
      collapsed: true,
      running: false,
      runnable: false,
      items: [],
    },
  ];

  // ★ 已完成节点数（派生 getter，模板里直接用）
  get completedNodeCount(): number {
    return this.flowNodes.filter(n => n.status === 'success').length;
  }

  // ★ v4.1.8：删除 AI 建议时弹窗确认所需状态（与单文件视图 codemig-file-change-view.component.ts:95-96 一致）
  @ViewChild('content') public content: any;
  deleteSuggestionOption: any = null;
  deleteSuggestionModal: any = null;

  // ─── 新增：手动选中的行范围累加 ───
  // 注意：使用 Map<file_id, selections[]> 结构，支持任意 file_id（不一定在 fileList 中）
  manualMigrateItemsMap: Map<number, Array<{ start_line: number; end_line: number }>> = new Map();

  // 缓存每个 file_id 最近一次加载的 response（用于拿到 file_path/file_name 以便自动加入 fileList）
  lastLoadedFileMeta: { [fileId: number]: any } = {};

  // 缓存每个 file_id 最近一次后端返回的 AI 建议 changes（删除 AI 建议时合并重画）
  lastAiChangesByFileId: { [fileId: number]: any[] } = {};

  // 缓存用户从外部传入并自动加入 fileList 的文件项（防止 loadFileList 时被覆盖丢失）
  extraFileListItems: Map<number, any> = new Map();

  // 标记是否已经从 Service 恢复过状态（防止 queryParams 多次触发时重复恢复）
  private _stateRestored: boolean = false;

  // ─── 新增：选中状态和装饰 ───
  selectedLineNumbers: { startLine: number; endLine: number; lineCount: number } | null = null;
  decorationsCollection!: monaco.editor.IEditorDecorationsCollection;
  private aiActionWidget: monaco.editor.IContentWidget | null = null;

  // 临时高亮（revealLine 用）：独立 collection + 定时器，避免污染主 decorationsCollection
  private flashDecorationsCollection: monaco.editor.IEditorDecorationsCollection | null = null;
  private flashHighlightTimer: any = null;

  // ─── Monaco Diff Editor ───
  editorRef!: monaco.editor.IStandaloneDiffEditor;
  originalModel: any = { value: '' };
  modifiedModel: any = { value: '' };
  editorOptions = {
    theme: 'vs',
    language: 'cpp',
    readOnly: false,
    automaticLayout: true,
    fixedOverflowWidgets: true,
    originalEditable: false,
    enableSplitViewResizing: true,
    renderSideBySide: false,
  };

fileContentDirty: { [fileId: number]: boolean } = {};
  fileContentSaved: { [fileId: number]: string } = {};
  savingProjectChange: boolean = false;

  constructor(
    private http: HttpClient,
    private codeMigApi: CodeMigApi,
    private agentApi: AgentManagementApi,
    private route: ActivatedRoute,
    private router: Router,
    private plxMessage: PlxMessage,
    private modalService: PlxModal,
    private clipboard: Clipboard,
    private cdr: ChangeDetectorRef,
    private logoutService: LogoutService,
    private stateService: ProjectMigrateStateService,
    private fileSidebarService: CodemigFileSidebarService,
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  ngOnInit() {
    this.fileChange_getApikeyList();
    this.showModelSelect = true;
    this.route.queryParams.subscribe((params) => {
      const newTaskId = Number(params['task_id']);
      const newDirId = Number(params['dir_id']);
      const newFileId = Number(params['file_id']);

      // 检测task_id或dir_id是否变化
      const taskChanged = this.task_id !== newTaskId || this.dir_id !== newDirId;

      this.task_id = newTaskId;
      this.dir_id = newDirId;

      // 关键：组件刚创建时（首次 ngOnInit）从 Service + DB 双层恢复状态
      // 因为 migrate_project 路由有 data: { reuse: false }，每次 router.navigate
      // 都会销毁并重建组件，需要从 Service 中恢复用户的手动选中，
      // 再用 DB 中持久化的 selections 覆盖 Service（Service 与 DB 不一致时以 DB 为准）。
      const isFirstInit = !this._stateRestored;
      if (isFirstInit && newTaskId && newDirId) {
        this.manualMigrateItemsMap = this.stateService.loadManualSelections(newTaskId, newDirId);
        this.lastAiChangesByFileId = this.stateService.loadAiChanges(newTaskId, newDirId);
        this.lastLoadedFileMeta = this.stateService.loadFileMeta(newTaskId, newDirId);
        this._stateRestored = true;
        console.info('[一键迁移] 从 Service 恢复状态', {
          taskId: newTaskId,
          dirId: newDirId,
          fileCount: this.manualMigrateItemsMap.size,
          aiChangesCount: Object.keys(this.lastAiChangesByFileId).length,
        });

        // ★ 关键修复 1：从后端 DB 加载手动选中并 in-place 合并到现有 Map，
        //   而不是 `this.manualMigrateItemsMap = map`（整体替换会破坏 fileList 中的数组引用）。
        // ★ 关键修复 2：把后续 loadFileList / flush 推迟到 list 接口返回后再执行，
        //   避免 fileList 在 map 为空时被重置为 `manualSelections: []`，导致 DB 数据丢失。
        this.codeMigApi.listManualSuggestionsByDir({
          user_name: this.user_name,
          dir_id: newDirId,
        }).subscribe({
          next: (res: any) => {
            if (res?.code === 0 && Array.isArray(res.selections)) {
              const dbMap = new Map<number, Array<{ start_line: number; end_line: number; file_path?: string }>>();
              for (const s of res.selections) {
                if (!dbMap.has(s.file_id)) dbMap.set(s.file_id, []);
                dbMap.get(s.file_id)!.push({
                  start_line: Number(s.start_line),
                  end_line: Number(s.end_line),
                  file_path: s.file_path || undefined,
                });
              }
              // in-place merge：以 DB 为准（刷新场景下 DB 是最新），合并到现有 Map
              this.mergeManualSelectionsFromDb(dbMap);
              console.info('[一键迁移] 从后端 DB 加载手动选中（in-place merge 完成）', {
                taskId: newTaskId,
                dirId: newDirId,
                fileCount: dbMap.size,
                total: res.selections.length,
              });
            }
          },
          error: (err) => {
            console.warn('[一键迁移] 从后端加载手动选中失败（已忽略）', err);
          },
        });
      }

      // 如果task_id或dir_id变化，重新加载文件列表
      if (taskChanged || !this.task_id) {
        // task/dir 整体切换：把当前 manual_selection 落库（避免切目录时丢数据）
        // 设计：flush 仅在内存数据"有内容"时才写空数组清空，避免初次进入时 Map 为空导致 DB 被误清空。
        this.flushManualSelectionsToBackend();
        this.loadFileList();
        this.loadProjectAiSuggestion();
        this.loadProjectHistory();
        // ★ 功能验证产物：刷新页面后也要能看到 test/ 下的测试文件
        this.loadUtTestFiles();
        // 如果有file_id参数，等待文件列表加载完成（loadFileList是异步的）
        // 组件刚重建时 editorRef / saved 还没就绪，必须推迟到 loadFileList 完成后
        // 再做 dirty 检查（确认切文件前的弹窗）。
        if (newFileId) {
          setTimeout(async () => {
            const ok = await this.confirmAndSwitchFile(newFileId);
            if (ok) {
              this.switchToFile(newFileId);
            } else if (this.selectedFileId != null && this.selectedFileId !== newFileId) {
              // 保存失败 / 用户在弹窗中选取消：URL 已经变了但实际没切换，回滚 URL
              this.router.navigate([], {
                relativeTo: this.route,
                queryParams: { file_id: this.selectedFileId },
                queryParamsHandling: 'merge',
                replaceUrl: true,
              });
            }
          }, 200);
        }
      } else if (newFileId && newFileId !== this.selectedFileId) {
        // 同一 task/dir 但 file_id 变化：先 flush 再切（确保选中段落落库），
        // 然后走统一的 confirmAndSwitchFile 处理 dirty 弹窗
        this.flushManualSelectionsToBackend();
        this.confirmAndSwitchFile(newFileId).then((ok) => {
          if (ok) {
            this.switchToFile(newFileId);
          } else if (this.selectedFileId != null) {
            // 保存失败 / 用户在弹窗中选取消：URL 已经变了但实际没切换，回滚 URL
            this.router.navigate([], {
              relativeTo: this.route,
              queryParams: { file_id: this.selectedFileId },
              queryParamsHandling: 'merge',
              replaceUrl: true,
            });
          }
        });
      }

      // ★ v4.x.0-RESUME：探测一键迁移三阶段是否各自存在可恢复的 qwen 会话。
      //   任何 newDirId 有值时都触发（首次进入页面 / 切换 dir 都覆盖）。
      if (newDirId) {
        this._scheduleRefreshResumable(newDirId);
      }
    });

    // ★ 文件树点击通道：只切换中间的 diff 展示，不联动 AI 面板——
    //   文件树是全工程导航树（含未参与迁移的 original 文件），用户点树
    //   通常只想看代码；面板联动仅限 ①②③ 阶段区域内的条目/标题栏点击。
    //   因此不走 onFileClick（它带 syncAiPanelToStage 阶段联动）。
    //   dirty 弹窗 / isGenerating 守卫等与 onFileClick 保持一致：
    //     - AI 生成中(isGenerating)时早返回 + warning，不切文件
    //     - dirty 文件会弹"保存/放弃"窗
    //     - 不动 router、不重建组件 → SSE/Docker 不会被打断
    this.migrateNavigateSub = this.fileSidebarService.migrateNavigate$.subscribe(({ file_id }) => {
      if (file_id == null) return;
      const fid = Number(file_id);
      if (this.isGenerating) {
        this.plxMessage.warning('AI 正在生成迁移建议，请稍候...', '');
        return;
      }
      // 同文件点击不重复加载
      if (this.selectedFileId === fid && this.editorRef) {
        return;
      }
      this.confirmAndSwitchFile(fid).then((ok) => {
        if (ok) {
          this.switchToFile(fid);
        }
      });
    });
  }

  // ─── 刷新后恢复最近一次迁移的 AI 建议 ───
  // v4.x：三阶段（①迁移 ②功能验证 ③性能优化）的 Agent 输出都持久化在
  // codemig_task_ai（file_id=0，stage 区分）。刷新页面后默认展示"最近一次"
  // （不传 stage，兼容旧行为）；用户点击流程节点首击加载对应阶段（见
  // toggleFlowNode 的两段式点击语义）。
  /** 当前 AI 面板绑定到的节点 id：null=最近一次（页面加载恢复态） */
  aiStageFilter: string | null = null;

  loadProjectAiSuggestion(stage: string | null = null) {
    if (!this.dir_id) return;
    const body: any = { 'user_name': this.user_name, 'dir_id': this.dir_id };
    if (stage) body.stage = stage;
    this.codeMigApi.reopenProjectAi(body).subscribe({
      next: (res: any) => {
        if (res?.code === 0 && res.data) {
          this.suggestion = res.data;
          this.showAIPanel = true;
          this.cdr.markForCheck();
        }
      },
      error: () => {},
    });
  }

  /** 流程节点点击 → 加载该阶段最近一次输出（toggleFlowNode 首次点击调用）
   *  生成中不抢占流式内容。
   *  无论该阶段有没有历史输出，都把节点标记为"已选中"——保证下一次
   *  点击进入折叠切换（而不是永远停在"首次加载"分支）。
   *  注意：aiStageFilter 存 node.id（'migrate'/'ut_test'），
   *  仅在发请求时映射成后端 stage（migrate → project_migrate）。 */
  private loadStageOutputForNode(nodeId: string) {
    if (this.isGenerating) {
      this.plxMessage.warning('AI 正在生成，请稍候...', '');
      return;
    }
    // 先标记选中：本次点击的"加载"语义已经消费掉了
    this.aiStageFilter = nodeId;
    const stage = nodeId === 'migrate' ? 'project_migrate' : nodeId;
    this.codeMigApi.reopenProjectAi({
      'user_name': this.user_name,
      'dir_id': this.dir_id,
      'stage': stage,
    }).subscribe({
      next: (res: any) => {
        if (res?.code === 0 && res.data) {
          this.suggestion = res.data;
          this.showAIPanel = true;
          this.cdr.markForCheck();
        } else {
          // 该阶段暂无历史输出：面板保持原内容，仅提示
          this.plxMessage.info('该阶段暂无历史输出', '');
          this.cdr.markForCheck();
        }
      },
      error: () => {
        this.plxMessage.warning('加载阶段输出失败', '');
      },
    });
  }

  /** ★ 阶段区域联动：点击某阶段区域内的文件条目时，AI 面板同步切换到
   *  该阶段最近一次输出（与标题栏 toggleFlowNode 首击同一通道）。
   *  已绑定同阶段则跳过（幂等，避免重复请求）；生成中不抢占流式内容。 */
  private syncAiPanelToStage(stageId: FlowNodeId) {
    if (this.isGenerating) return;
    if (this.aiStageFilter === stageId) return;
    this.loadStageOutputForNode(stageId);
  }

  // ─── 文件列表加载（并行请求 changed 和 missing 文件） ───
  private fileListLoadDebounceTimer: any = null;
  
  loadFileList() {
    if (!this.task_id) return;
    this.loadingFileList = true;
    
    const changedBody = { 
      'user_name': this.user_name, 
      'task_id': this.task_id 
    };
    const missingBody = { 
      'user_name': this.user_name, 
      'task_id': this.task_id 
    };
    
    // 取消之前的防抖定时器
    if (this.fileListLoadDebounceTimer) {
      clearTimeout(this.fileListLoadDebounceTimer);
    }
    
    // 并行请求 changed 文件和 missing 文件
    Promise.all([
      this.codeMigApi.getTaskFiles(changedBody).toPromise(),
      this.codeMigApi.getProjectMigrateMissingFiles(missingBody).toPromise()
    ]).then(([changedResponse, missingResponse]: [any, any]) => {
      this.loadingFileList = false;
      
      const fileList: any[] = [];
      
      // 处理 changed files
      if (changedResponse.code == 0) {
        const my_data = changedResponse.data;
        const files = my_data.files || [];
        files.forEach((f: any) => {
          if (f[6] > 0) {  // num_changed_lines > 0
            fileList.push({
              file_id: f[3],
              file_name: f[4],
              file_path: f[5],
              file_source: 'changed',
              num_changed_lines: f[6],
              solver_description: '',
              expanded: false,
              aiSuggestions: [],
              manualSelections: [],
              // 关键修复（阶段 X-AI-COUNT-INIT-1）：
              // 用后端返回的 num_changed_lines（实际语义 = AI 建议数）作为 totalSuggestions 初值，
              // 让页面首次打开时徽章就直接显示真实数字，无需先点开下三角。
              totalSuggestions: f[6]
            });
          }
        });
      }

      // 处理 missing files（缺失文件，红色显示）+ generated files（迁移新增文件，绿色显示）
      // 后端 /task/project_migrate_missing_files 一次返回两类清单（code=0）
      if (missingResponse.code == 0) {
        const missingFiles = missingResponse.data?.missing || [];
        missingFiles.forEach((f: any) => {
          fileList.push({
            file_id: f.file_id,
            file_name: f.file_name,
            file_path: f.file_path,
            file_source: 'missing',
            num_changed_lines: 0,
            solver_description: '缺失文件',
            expanded: false,
            aiSuggestions: [],
            manualSelections: [],
            totalSuggestions: 0
          });
        });
        const generatedFiles = missingResponse.data?.generated || [];
        generatedFiles.forEach((f: any) => {
          fileList.push({
            file_id: f.file_id,
            file_name: f.file_name,
            file_path: f.file_path,
            file_source: 'generated',
            num_changed_lines: 0,
            solver_description: '迁移新增文件',
            expanded: false,
            aiSuggestions: [],
            manualSelections: [],
            totalSuggestions: 0
          });
        });
      }
      
      // 关键修复：合并外部传入的文件（extraFileListItems），不被后端数据覆盖
      // 防止 loadFileList 后 ensureFileInList 加入的文件项丢失
      const backendIds = new Set(fileList.map(f => f.file_id));
      for (const [extraId, extraItem] of this.extraFileListItems) {
        if (!backendIds.has(extraId)) {
          fileList.push(extraItem);
        }
        // 注：backend 也包含 file_id 的情况下，不需要从 extraItem 合并 manualSelections
        // 因为 manualMigrateItemsMap 是权威存储，下面会用 Map 重新同步
      }

      // 关键修复：用 manualMigrateItemsMap 覆盖 fileList 中所有 manualSelections
      // 一键迁移是整个工程的整体迁移，所有文件的选中状态都必须从权威存储 Map 恢复
      // 这样无论之前 fileList 是否包含 manualSelections，都以 Map 为准
      for (const item of fileList) {
        const mapSelections = this.manualMigrateItemsMap.get(item.file_id);
        if (mapSelections && mapSelections.length > 0) {
          // 直接共享 Map 中的数组引用（保证后续修改双向同步）
          item.manualSelections = mapSelections;
        } else {
          // Map 中没有，确保是空数组（而不是 undefined）
          item.manualSelections = item.manualSelections || [];
        }
        // 关键修复（阶段 X-AI-COUNT-INIT-1）：
        // 与 addSelectedToSuggestions 保持一致 —— 未展开时 aiSuggestions 仍为空数组，
        // 用 num_changed_lines（loadFileList push 时已写入）兜底，避免冲掉 AI 初值。
        const aiCount = Math.max(
          item.aiSuggestions?.length || 0,
          item.num_changed_lines || 0
        );
        item.totalSuggestions = aiCount + item.manualSelections.length;
      }

      this.fileList = fileList;
      
      // 默认选中第一个文件（只有在没有指定file_id时才选中第一个）
      if (this.fileList.length > 0 && !this.selectedFileId) {
        this.selectedFileId = this.fileList[0].file_id;
        // 使用防抖延迟加载diff，避免频繁触发
        this.fileListLoadDebounceTimer = setTimeout(() => {
          this.loadFileDiff(this.fileList[0].file_id);
        }, 300);
      }
      
      // 使用 markForCheck 替代 detectChanges，让 Angular 在合适的时机统一处理
      this.cdr.markForCheck();
    }).catch(err => {
      this.loadingFileList = false;
      console.error('加载文件列表失败:', err);
      this.cdr.markForCheck();
    });
  }

  /**
   * v4.x：统一的切文件前置检查入口。
   * 由 onFileClick（迁移列表点击）和 queryParams 订阅（文件树点击）共同调用。
   * 检查当前文件是否 dirty，弹窗确认"保存/放弃"，返回是否继续切换。
   * - 返回 true：调用方应继续执行 switchToFile(targetFid)
   * - 返回 false：调用方应中止切换（保存失败或用户在弹窗中选取消的 URL 回滚场景单独处理）
   */
  private async confirmAndSwitchFile(targetFid: number): Promise<boolean> {
    // 没当前选中 / 同文件：不弹窗，直接允许
    if (this.selectedFileId == null || this.selectedFileId === targetFid) {
      return true;
    }
    if (!this.fileContentDirty[this.selectedFileId]) {
      return true;
    }
    // 计算真正的 dirty（saved 已就绪 且 与 modified 不一致）
    const current = this.editorRef?.getModel()?.modified?.getValue() ?? '';
    const saved = this.fileContentSaved[this.selectedFileId];
    const dirtyContent = saved != null && current !== saved;
    if (!dirtyContent) {
      return true;
    }

    // 真的脏：弹窗
    const wantSave = window.confirm(
      '当前文件有未保存的修改。\n\n' +
      '点「确定」= 保存后再切换\n' +
      '点「取消」= 放弃修改后切换'
    );
    const previousFid = this.selectedFileId!;
    if (wantSave) {
      // 保存并切换：保存成功才允许继续，否则返回 false
      return new Promise<boolean>((resolve) => {
        // 保存期间用户可能又切到别的文件，做个兜底：保存回调里再校验一次
        this.codeMigApi.saveProjectFileChange({
          user_name: this.user_name,
          dir_id: this.dir_id,
          file_id: previousFid,
          file_path: this.lastLoadedFileMeta[previousFid]?.file_path || '',
          content: current,
        }).subscribe({
          next: (res: any) => {
            if (this.selectedFileId !== previousFid) {
              // 用户在保存期间又切走了，本次保存结果不再用于切换决策
              resolve(false);
              this.cdr.markForCheck();
              return;
            }
            if (res?.code === 0) {
              this.fileContentSaved[previousFid] = current;
              this.fileContentDirty[previousFid] = false;
              this.plxMessage.success('已保存', '');
              this.loadProjectHistory();
              this.cdr.markForCheck();
              resolve(true);
            } else {
              this.plxMessage.error('保存失败，未切换文件', '');
              this.cdr.markForCheck();
              resolve(false);
            }
          },
          error: (err: any) => {
            this.plxMessage.error('保存失败：' + (err?.message || err), '');
            this.cdr.markForCheck();
            resolve(false);
          },
        });
      });
    }

    // 放弃修改：清 dirty + 把右侧重置成 saved 文本
    const savedText = saved ?? '';
    const editor = this.editorRef;
    if (editor) {
      editor.getModel()?.modified?.setValue(savedText);
    }
    this.fileContentDirty[previousFid] = false;
    return true;
  }

  // ─── 点击文件：加载该文件的 diff（复用 getTaskFileChange） ───
  onFileClick(fileId: number) {
    // 只在 AI 真正生成中禁止切换（loadingFileList 期间允许点击，
    // 因为可能是切换任务后第一次加载完成，此时点别的文件能正常响应）
    if (this.isGenerating) {
      this.plxMessage.warning('AI 正在生成迁移建议，请稍候...', '');
      return;
    }
    // ★ 阶段联动：①区域条目点击 → 面板切到①阶段最近输出。
    //   ②③ 条目点击（onStageFileClick）自带所属阶段联动并绕开本方法；
    //   文件树点击通道不联动（导航用途，不干扰正在阅读的 AI 建议）。
    this.syncAiPanelToStage('migrate');
    // 关键：同文件点击不要重复加载
    if (this.selectedFileId === fileId && this.editorRef) {
      return;
    }
    this.confirmAndSwitchFile(fileId).then((ok) => {
      if (ok) {
        this.switchToFile(fileId);
      }
    });
  }

  // 切换文件时取消正在进行的 diff 加载请求，防止竞态条件
  private pendingFileDiffSub: any = null;

  // 文件树点击通道订阅（用于 ngOnDestroy 解绑）
  private migrateNavigateSub: Subscription | null = null;

  loadFileDiff(fileId: number) {
    if (!this.dir_id || !fileId) return;
    // 取消上一次未完成的请求，避免竞态
    if (this.pendingFileDiffSub && typeof this.pendingFileDiffSub.unsubscribe === 'function') {
      this.pendingFileDiffSub.unsubscribe();
      this.pendingFileDiffSub = null;
    }
    const body = {
      'user_name': this.user_name,
      'task_id': this.task_id,
      'dir_id': this.dir_id,
      'file_id': fileId,
    };
    this.pendingFileDiffSub = this.codeMigApi.getTaskFileChange(body).subscribe({
      next: (response: any) => {
        // 关键：响应到达时再次校验 selectedFileId 是否还是本次请求的 fileId
        // 如果用户已经切换到其他文件，丢弃这次响应
        if (this.selectedFileId !== fileId) {
          console.info('[一键迁移] 忽略过期的 diff 响应', { requested: fileId, current: this.selectedFileId });
          return;
        }
        if (response.code == 0) {
          // 缓存最近一次响应，以便 addSelectedToSuggestions 知道 file_path/file_name
          this.lastLoadedFileMeta[fileId] = response;
          this.updateDiffEditor(response);
        }
        this.pendingFileDiffSub = null;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        console.error('加载文件 diff 失败:', err);
        this.pendingFileDiffSub = null;
        this.cdr.markForCheck();
      },
    });
  }

  // ─── 更新 Diff Editor 内容（参照单文件组件 updateDiffEditorAfterAgentQuery） ───
  private editorLayoutDebounceTimer: any = null;
  
  updateDiffEditor(response: any) {
    if (!this.editorRef) {
      // 编辑器尚未初始化，缓存内容待 onEditorInit 后填充
      this.originalModel = { value: response.original_file || '' };
      this.modifiedModel = { value: response.file || '' };
      return;
    }
    const diffModel = this.editorRef.getModel();
    if (!diffModel || !diffModel.original || !diffModel.modified) {
      console.error('diff 模型未正确初始化');
      return;
    }
    const originalFile = response.original_file || '';
    const modifiedFile = response.file || '';

    // 切换文件后重新初始化装饰器集合和选中监听
    const modifiedEditor = this.editorRef.getModifiedEditor();
    // 只在首次创建装饰器集合（避免切换文件时丢失 collection 引用）
    if (!this.decorationsCollection) {
      this.decorationsCollection = modifiedEditor.createDecorationsCollection();
    } else {
      // 切换文件时清空旧的高亮，避免"幽灵装饰器"
      this.decorationsCollection.clear();
    }
    this.setupSelectionListener();

    // 缓存后端返回的 AI 建议 changes（删除 AI 建议时合并重画需要用到）
    if (response.changes && Array.isArray(response.changes)) {
      this.lastAiChangesByFileId[this.selectedFileId!] = response.changes;
    } else {
      this.lastAiChangesByFileId[this.selectedFileId!] = [];
    }

    this.fileContentSaved[this.selectedFileId!] = modifiedFile;
    this.fileContentDirty[this.selectedFileId!] = false;

    diffModel.original.setValue(originalFile);
    diffModel.modified.setValue(modifiedFile);

    // 方案 A：去掉三层 fallback + sourceText 锚点机制，
    // 直接用一次性 decorateEditor 把 changes 按行号钉死，
    // 用户敲字时高亮不动（与单文件视图 codemig-file-change-view 行为对齐）。
    // 关键修复（高亮恢复）：合并 AI changes + manual selections 一起渲染，
    // 否则切文件/刷新后 manual 高亮会丢失（看似"消失"，再加一条又"复活"）。
    setTimeout(() => {
      this.renderDecorationsForFile(this.selectedFileId);
    }, 0);

    // 使用防抖避免重复 layout
    if (this.editorLayoutDebounceTimer) {
      clearTimeout(this.editorLayoutDebounceTimer);
    }
    this.editorLayoutDebounceTimer = setTimeout(() => {
      if (this.editorRef) {
        this.editorRef.layout();
        this.editorLayoutDebounceTimer = null;
      }
    }, 150);
  }

  // ─── 编辑器高亮装饰方法（参照单文件组件） ───
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

  /**
   * 关键修复（高亮恢复）：统一渲染 AI changes + manual selections。
   *
   * 背景：原有 updateDiffEditor / onEditorInit 在 setTimeout 里只调 decorateEditor(response.changes)，
   *       不会把 manualMigrateItemsMap[fileId] 中的手动选中画出来，所以：
   *         - 切文件 / 刷新后 manual 高亮"消失"
   *         - 用户在同一文件再点一次"添加到 AI 建议"，原 manual 又"复活"
   *       （真相是数据一直在 Map 中，只是漏画了）
   *
   * 本方法作为切文件 / 编辑器重建时的统一重画入口，把 AI 与 manual 一次性画上：
   *   - AI：橙色 #FFA500（沿用 decorateEditor → updateDecorations 的样式）
   *   - manual：绿色 #52c41a（与 refreshFileDecorations 一致）
   */
  private renderDecorationsForFile(fileId: number | null | undefined): void {
    if (fileId == null) return;
    if (!this.editorRef) return;
    const modifiedEditor = this.editorRef.getModifiedEditor();
    const model: any = modifiedEditor.getModel();
    if (!model) return;

    const totalLines = model.getLineCount();
    const allDecorations: any[] = [];

    // 1) AI 建议装饰器（橙色）：复用 decorateEditor 的逻辑
    const aiChanges = this.lastAiChangesByFileId[fileId] || [];
    for (const change of aiChanges) {
      const suggestion_type = change[5];
      const ignored = change[6];
      if (ignored) continue;
      switch (suggestion_type) {
        case SolverType.MACROS:
          this.appendChangeDecoration(model, allDecorations, change[0], change[1], change[2], change[3], '#FFA500');
          break;
        case SolverType.ASM_FILE:
          this.appendChangeDecoration(model, allDecorations, change[0], change[0], change[2], change[3], '#FFA500');
          break;
        default:
          this.appendChangeDecoration(model, allDecorations, change[0], change[1], change[2], change[3], '#FFA500');
      }
    }

    // 2) manual 装饰器（绿色），与 refreshFileDecorations 行为一致
    const manualSelections = this.manualMigrateItemsMap.get(fileId) || [];
    for (const m of manualSelections) {
      const safeStartLine = m.start_line;
      const safeEndLine = m.end_line;
      if (
        !safeStartLine || !safeEndLine ||
        safeStartLine > totalLines || safeEndLine > totalLines ||
        safeStartLine < 1 || safeEndLine < 1 ||
        safeStartLine > safeEndLine
      ) {
        // 行号越界（如代码被删后行号偏移），跳过；行号重绑定将在第 2 步修复
        continue;
      }
      const lineLength = model.getLineLength(safeEndLine);
      // 顶部：💡 图标 + 绿色（与 AI 橙色区分）
      allDecorations.push({
        range: new monaco.Range(safeStartLine, 1, safeEndLine, lineLength + 1),
        options: {
          beforeContentClassName: 'my-icon',
          inlineClassName: 'underline-suggestion',
          hoverMessage: {
            value: '**💡 手动选中**: 请转化为适配riscv架构的代码并高亮',
          },
          overviewRuler: {
            color: '#52c41a',
            position: monaco.editor.OverviewRulerLane.Full,
          },
        },
      });
      // 底部：整行高亮
      allDecorations.push({
        range: new monaco.Range(safeStartLine, 1, safeEndLine, lineLength + 1),
        options: {
          isWholeLine: true,
          className: 'line-modified',
        },
      });
    }

    if (this.decorationsCollection) {
      this.decorationsCollection.clear();
    }
    this.decorationsCollection =
      modifiedEditor.createDecorationsCollection(allDecorations);
  }

  /**
   * v4.2：把后端保存响应里的 line_mapping 同步到前端内存。
   * - manual（is_manual=1）：在 manualMigrateItemsMap 中按 (start_line, end_line) 匹配；
   *                          kept/shifted 替换行号；invalid 从 Map 中删除该项。
   * - AI（is_manual=0）：在 lastAiChangesByFileId 数组中按 change_id 匹配；
   *                      kept/shifted 替换元组前两列；invalid 过滤掉。
   * 入参 mapping 项形如：
   *   { change_id, is_manual, old_start_line, old_end_line,
   *     new_start_line, new_end_line, status }
   */
  private applyLineMappingForFile(fid: number, mapping: any[]): void {
    if (fid == null || !Array.isArray(mapping) || mapping.length === 0) return;

    // 1) 处理 manual
    const manualArr = this.manualMigrateItemsMap.get(fid) || [];
    const manualMapping = mapping.filter((m: any) => m.is_manual === 1);
    if (manualArr.length > 0 && manualMapping.length > 0) {
      const kept: Array<{ start_line: number; end_line: number }> = [];
      for (const m of manualArr) {
        const hit = manualMapping.find(
          (mm: any) =>
            mm.old_start_line === m.start_line && mm.old_end_line === m.end_line
        );
        if (!hit) {
          kept.push(m);
          continue;
        }
        if (hit.status === 'invalid') continue; // invalid → 删除
        // kept / shifted → 替换
        kept.push({
          start_line: hit.new_start_line,
          end_line: hit.new_end_line,
        });
      }
      this.manualMigrateItemsMap.set(fid, kept);
    }

    // 2) 处理 AI（8 元组 [start, end, append_or_replace, suggestion, change_id, type, ignored, is_manual]）
    const aiArr = (this.lastAiChangesByFileId[fid] || []) as any[];
    const aiMapping = mapping.filter((m: any) => m.is_manual === 0);
    if (aiArr.length > 0 && aiMapping.length > 0) {
      const kept: any[] = [];
      for (const t of aiArr) {
        const changeId = t[4];
        const hit = aiMapping.find((mm: any) => mm.change_id === changeId);
        if (!hit) {
          kept.push(t);
          continue;
        }
        if (hit.status === 'invalid') continue; // invalid → 过滤掉
        // kept / shifted → 替换 [0] start, [1] end
        const newTuple = t.slice();
        newTuple[0] = hit.new_start_line;
        newTuple[1] = hit.new_end_line;
        kept.push(newTuple);
      }
      this.lastAiChangesByFileId[fid] = kept;
    }
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

  /**
   * 将 SolverType 类型码映射为简短中文标签，用于建议列表的类型徽标。
   * 与单文件视图 environment.supportedSolverTypes 的类型集合保持一致。
   */
  getSolverTypeLabel(type: any): string {
    switch (type) {
      case SolverType.MAKEFILE:
        return 'Makefile';
      case SolverType.INTRINSICS:
        return 'Intrinsic';
      case SolverType.BUILTIN:
        return '内建函数';
      case SolverType.MACROS:
        return '宏';
      case SolverType.INCODE_ASM:
        return '内联汇编';
      case SolverType.ASM_FILE:
        return '汇编文件';
      case SolverType.JAVA_SOURCE_CODE:
        return 'Java源码';
      case SolverType.PYTHON_SOURCE_CODE:
        return 'Python源码';
      case SolverType.GO_SOURCE_CODE:
        return 'Go源码';
      case SolverType.SHELL_SOURRCE_CODE:
        return 'Shell源码';
      case SolverType.BUILD_SCRIPT:
        return '构建脚本';
      case SolverType.GO_RELEASER_TML:
        return 'GoReleaser';
      case SolverType.RUST_SOURCE_CODE:
        return 'Rust源码';
      case SolverType.RUST_TOML_CODE:
        return 'Rust配置';
      default:
        return 'AI建议';
    }
  }

  escapeMarkdownHeaders(text: string): string {
    return text.replace(/^(#+\s)/gm, (match) => {
      return match.replace(/#/g, '\\#');
    });
  }

  onEditorInit(editor: monaco.editor.IStandaloneDiffEditor) {
    this.editorRef = editor;

    // 获取右侧（Modified）编辑器实例
    const modifiedEditor = editor.getModifiedEditor();

    // 初始化装饰器集合
    this.decorationsCollection = modifiedEditor.createDecorationsCollection();

    // 设置选中监听（启用悬浮按钮）
    this.setupSelectionListener();

    // 右键菜单：当右键落在某段 manual_selection 区间内时，弹出"删除本手动选中的代码"
    this.setupManualSelectionContextMenu(modifiedEditor);

    // 方案 A：保留最小化的 onDidChangeModelContent 监听 —— **仅**判断 dirty 标志，
    // 不做任何装饰器重画（让高亮钉死行号不动），同时让 HTML 端"保存修改/放弃修改"按钮可点。
    // 不再调 addAiAnchors / renderDecorationsFromAnchors / computeLineMapping。
    //
    // 关键：监听器内对比 `model.getValue()` 与 `fileContentSaved[fid]`。
    // - 相等 → 程序化 setValue（加载文件 / 放弃修改还原），不设 dirty。
    // - 不等 → 用户真实输入，设 dirty，让"保存修改/放弃修改"按钮可点。
    modifiedEditor.onDidChangeModelContent(() => {
      if (this.selectedFileId == null) return;
      const saved = this.fileContentSaved[this.selectedFileId] ?? '';
      const current = modifiedEditor.getModel()?.getValue() ?? '';
      if (current === saved) return;
      this.fileContentDirty[this.selectedFileId] = true;
      this.cdr.markForCheck();
    });

    // 如果切换前已请求过文件内容，这里补填
    if (this.originalModel.value || this.modifiedModel.value) {
      const diffModel = editor.getModel();
      if (diffModel && diffModel.original && diffModel.modified) {
        const modifiedFile = this.modifiedModel.value || '';
        const originalFile = this.originalModel.value || '';
        if (this.selectedFileId != null) {
          this.fileContentSaved[this.selectedFileId] = modifiedFile;
          this.fileContentDirty[this.selectedFileId] = false;
        }
        diffModel.original.setValue(originalFile);
        diffModel.modified.setValue(modifiedFile);
        if (this.selectedFileId != null) {
          // 方案 A：去掉 addAiAnchors + renderDecorationsFromAnchors，直接一次性 decorateEditor
          // 关键修复（高亮恢复）：合并 manual selections 一起渲染，避免编辑器重建时 manual 丢失。
          setTimeout(() => {
            this.renderDecorationsForFile(this.selectedFileId);
          }, 0);
        }
        // 清缓存
        this.originalModel = { value: '' };
        this.modifiedModel = { value: '' };
      }
    }
  }

  // ─── v4.1：保存当前文件修改 ────────────────────────
  saveProjectFileChanges(): void {
    const fid = this.selectedFileId;
    if (fid == null || !this.editorRef) return;
    if (!this.fileContentDirty[fid]) {
      this.plxMessage.info('当前文件无未保存修改', '');
      return;
    }
    const modifiedEditor = this.editorRef.getModifiedEditor();
    const model = modifiedEditor.getModel();
    if (!model) return;
    const content = model.getValue();
    const meta = this.lastLoadedFileMeta[fid];
    const filePath = meta?.file_path || meta?.path || '';
    if (!filePath) {
      this.plxMessage.warning('无法获取文件路径，无法保存', '');
      return;
    }
    this.savingProjectChange = true;
    this.codeMigApi.saveProjectFileChange({
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: fid,
      file_path: filePath,
      content,
    }).subscribe({
      next: (res: any) => {
        this.savingProjectChange = false;
        if (res?.code === 0) {
          this.fileContentSaved[fid] = content;
          this.fileContentDirty[fid] = false;
          // v4.2：保存成功后用响应里的 line_mapping 同步前端内存 + 重画装饰器
          if (Array.isArray(res.line_mapping) && res.line_mapping.length > 0) {
            this.applyLineMappingForFile(fid, res.line_mapping);
          }
          this.renderDecorationsForFile(fid);
          this.plxMessage.success('修改已保存', '');
          this.loadProjectHistory();
        } else {
          this.plxMessage.error('保存失败：' + (res?.message || '未知错误'), '');
        }
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.savingProjectChange = false;
        this.plxMessage.error('保存失败：' + (err?.message || err), '');
        this.cdr.markForCheck();
      },
    });
  }

  // ─── v4.1：放弃当前文件修改 ────────────────────────
  discardProjectFileChanges(): void {
    const fid = this.selectedFileId;
    if (fid == null || !this.editorRef) return;
    if (!this.fileContentDirty[fid]) {
      this.plxMessage.info('当前文件无未保存修改', '');
      return;
    }
    const saved = this.fileContentSaved[fid];
    if (saved == null) return;
    const modifiedEditor = this.editorRef.getModifiedEditor();
    modifiedEditor.getModel()?.setValue(saved);
    this.fileContentDirty[fid] = false;
    this.plxMessage.success('已放弃本次修改', '');
    this.cdr.markForCheck();
  }

  // ─── v4.1：实际切文件（从 onFileClick 抽出） ────────────────────────
  private switchToFile(fid: number) {
    if (this.selectedFileId === fid && this.editorRef) return;
    this.selectedFileId = fid;
    this.loadFileDiff(fid);
  }

  // ─── v4.1：判断时间戳是否为今天 ────────────────────────
  private _isToday(isoTime: string): boolean {
    if (!isoTime) return false;
    const d = new Date(isoTime);
    if (isNaN(d.getTime())) return false;
    const now = new Date();
    return d.getFullYear() === now.getFullYear()
      && d.getMonth() === now.getMonth()
      && d.getDate() === now.getDate();
  }

  async fileChange_getApikeyList() {
    this.apikeyList = await this.agentApi.getSavedKeyByModel();
    const data = this.apikeyList || [];
    this.modelOptions = this.agentApi.extractUniqueModels(
      data, this.user_name, localStorage.getItem('userRole') === 'admin');
    this.selectedModel = this.agentApi.selectedModel;
    this.selectedApiformat = this.agentApi.selectedApiformat;
  }

  onModelChange(model: string): void {
    this.selectedModel = model;
    const selectedOption = this.modelOptions.find(opt => opt.value === model);
    this.selectedApiformat = selectedOption?.api_format || '';
  }

  // 历史下拉框 options：把后端 historyList 转成 plx-select 所需的 {value,label} 格式
  // 新格式：[前缀] HH:MM (short_hash) · 当前?  —— prefix 在前，时间其次
  private rebuildHistoryOptions() {
    const fmt = (h: any) => {
      const prefix = h.prefix || h.label || '提交点';
      const shortHash = h.short_hash || (h.hash || '').slice(0, 8);
      // time 形如 "2026-07-22 10:30:45"，取 HH:MM
      const timeStr = h.time || '';
      const hhmm = timeStr.length >= 16 ? timeStr.substring(11, 16) : timeStr;
      return `${prefix} ${hhmm} (${shortHash})${h.is_current ? ' · 当前' : ''}`;
    };
    this.historyOptions = this.historyList.map(h => ({
      value: h.hash,
      label: fmt(h),
    }));
    const opts: Array<{ value: string; label: string }> = [
      { value: '', label: '当前 HEAD（最新状态）' },
    ];
    this.historyList.forEach(h => {
      opts.push({
        value: h.hash,
        label: fmt(h),
      });
    });
    this.patchToOptions = opts;
  }

  /**
   * ★ 阶段状态持久化恢复：从 git marker 历史（reflog）推断三阶段各自最终状态。
   *
   * 背景：node.status 只存在组件内存，刷新页面组件重建后全部回退 'ready'，
   * 用户已完成的阶段显示"就绪"。而完成事实在仓库 marker commit 里有完整留痕：
   *   开始：reason=user-click-run-{stage} / user-click-resume-{stage}（前端 _preBoundaryCommit）
   *   结束：reason=stage-end-success / stage-end-error / stage-end-cancel
   *         （src=codemig-boundary 前端收尾 + src=codemig-agent 后端 finally，两条冗余）
   *
   * 推断规则（按提交时间正序扫描）：
   *   - click-run/resume marker "打开"某阶段的运行
   *   - 紧随的第一条 stage-end-*（或异常路径的 intermediate-error）"关闭"它并记录结局
   *   - 同一结局的另一条冗余 marker（另一 src 写的）此时无运行可配，自然忽略
   * 最终映射：success→已完成 / error→失败 / cancel→已中断（刷新杀容器、点停止、
   *   断流都属于 cancel；Agent 容器虽被清理，但命名卷里的 pi 会话仍在，
   *   「继续运行」按钮可接力）/ 未关闭（刷新时正在跑→cancel 由后端 finally 补）
   *   / 从未运行→就绪
   *
   * 注意：
   *   - running 中的节点跳过，不覆盖实时状态
   *   - 单文件迁移等其它流程的 commit（user-save 等）不带 click-run marker，不参与配对
   */
  private restoreFlowStatusFromHistory() {
    // historyList 是 reflog 时间倒序（新→旧），reverse 得到时间正序
    const chrono = [...this.historyList].reverse();
    const stageOf = (reason: string): FlowNodeId | null => {
      const m = /^(?:user-click-run|user-click-resume)-(migrate|ut_test)$/.exec(reason);
      return m ? (m[1] as FlowNodeId) : null;
    };
    const outcomeOf = (reason: string): 'success' | 'error' | 'cancel' | null => {
      if (reason === 'stage-end-success') return 'success';
      if (reason === 'stage-end-error') return 'error';
      if (reason === 'stage-end-cancel') return 'cancel';
      // 阶段启动后端异常（流未建立就失败）也会留 intermediate-error commit，前端同样弹"失败"
      if (reason === 'intermediate-error') return 'error';
      return null;
    };
    const lastOutcome: Partial<Record<FlowNodeId, 'success' | 'error' | 'cancel'>> = {};
    let open: FlowNodeId | null = null;
    for (const h of chrono) {
      const m = /reason:([A-Za-z0-9_-]+)/.exec(h.message || '');
      if (!m) continue;
      const reason = m[1];
      const stage = stageOf(reason);
      if (stage) {
        open = stage;
        continue;
      }
      const outcome = outcomeOf(reason);
      if (outcome && open) {
        lastOutcome[open] = outcome;
        open = null;
      }
    }
    for (const node of this.flowNodes) {
      if (node.running) continue; // 不覆盖正在运行节点的实时状态
      const outcome = lastOutcome[node.id];
      node.status = outcome === 'success' ? 'success'
        : outcome === 'error' ? 'error'
        : outcome === 'cancel' ? 'interrupted'
        : 'ready';
      if (node.status !== 'error') {
        node.errorMessage = undefined;
      }
    }
    // ★ 串行门禁：恢复出的上游状态联动下游 runnable（①success → ②解锁）
    this.refreshRunnability();
    this.cdr.markForCheck();
  }

  get modelSelectPlaceholder(): string {
    return this.modelOptions.length === 0
      ? '暂无可用模型，请先配置 API Key'
      : '请选择模型';
  }

  goToApiKeyManagement(): void {
    this.router.navigate(['/settings/agentmanagement']);
  }

  toggleAIPanel() {
    this.showAIPanel = !this.showAIPanel;
  }

  // ★ v4.x.0-RUN-FLOW：流程节点控制 ─────────────────────────

  /** ★ v4.x：节点点击语义（两段式）：
   *  1. 首次点击（该节点未选中）→ AI 面板切换到该阶段最近一次的完整输出；
   *  2. 再次点击（该节点已选中）→ 原有的展开/缩略切换。
   *  这样点一次即可在三个阶段的历史输出间浏览，不用去 AI 面板找切换器。 */
  toggleFlowNode(node: FlowNode) {
    if (this.aiStageFilter !== node.id) {
      // 首次点击：加载该阶段最近输出（含 AI 面板自动展开）
      this.loadStageOutputForNode(node.id);
      return;
    }
    node.collapsed = !node.collapsed;
    this.cdr.markForCheck();
  }

  /** ★ 串行门禁：上游阶段节点（①→null，②→①） */
  private predecessorOf(nodeId: FlowNodeId): FlowNode | null {
    if (nodeId === 'ut_test') return this.flowNodes.find(n => n.id === 'migrate') || null;
    return null;
  }

  /** 门禁校验：上游未成功 → 返回阻断提示文案；通过 → null */
  gateBlockReason(node: FlowNode): string | null {
    const pred = this.predecessorOf(node.id);
    if (!pred) return null;
    if (pred.status !== 'success') {
      return `需先完成「${pred.label}」阶段（当前：${this.statusLabel(pred)}）`;
    }
    return null;
  }

  /** 按钮悬浮提示：带门禁原因（未解锁时说明为什么点不了） */
  runTitle(node: FlowNode): string {
    const gate = this.gateBlockReason(node);
    const label = this.runButtonLabel(node);
    return gate ? `${label}（${gate}）` : label;
  }

  /** ★ v4.x：运行按钮文案（按节点历史状态区分）：
   *  - 未跑过（ready/idle）→「运行X」
   *  - 跑过且失败        →「重新运行X」
   *  - 跑过且成功        →「重新运行X」（重跑需确认，见 confirmRerunIfNeeded）
   *  - 已中断            →「重新运行X」（想接着跑请用「继续运行X」） */
  runButtonLabel(node: FlowNode): string {
    const prefix = node.status === 'error' || node.status === 'success' || node.status === 'interrupted'
      ? '重新运行'
      : '运行';
    return `${prefix}${node.label}`;
  }

  /** ★ v4.x：继续按钮文案（与运行按钮同风格） */
  resumeButtonLabel(node: FlowNode): string {
    return `继续运行${node.label}`;
  }

  /** ★ v4.x：已成功的阶段重跑前确认（防误点重跑浪费 Agent 资源）。
   *  返回 true = 允许继续执行（弹窗确认或无需弹窗）。 */
  private confirmRerunIfNeeded(node: FlowNode): boolean {
    if (node.status !== 'success') return true;
    return window.confirm(
      `「${node.label}」阶段已成功完成。\n` +
      `重新运行将重新执行该阶段 Agent（耗时且消耗模型额度），\n` +
      `且会覆盖命名卷中保存的上一轮会话。确定重新运行吗？`
    );
  }

  /** 上游状态变化后刷新下游 runnable（所有 status 变更点统一调用） */
  private refreshRunnability() {
    for (const node of this.flowNodes) {
      node.runnable = this.gateBlockReason(node) === null;
    }
    this.cdr.markForCheck();
  }

  /** 状态徽章文本：结合 runnable 派生，避免"按钮置灰却显示就绪"的矛盾。
   *  - 上游未完成（!runnable 且非运行/终态）→「未解锁」（等上游阶段完成）
   *  - 其余按 status 映射（未开始/就绪/运行中/完成/失败/已中断） */
  statusLabel(node: FlowNode): string {
    const map: Record<FlowNodeStatus, string> = {
      idle: '未开始',
      ready: '就绪',
      running: '运行中',
      success: '完成',
      error: '失败',
      interrupted: '已中断',
    };
    if (node.status === 'ready' && !node.runnable) {
      return '未解锁';
    }
    return map[node.status] || node.status;
  }

  /** 状态徽章样式类：未解锁节点用灰色（与 idle 同色系），不显示误导性的蓝色"就绪" */
  statusClass(node: FlowNode): string {
    if (node.status === 'ready' && !node.runnable) {
      return 'status-locked';
    }
    return 'status-' + node.status;
  }

  /** 节点计数：迁移阶段显示 fileList 长度，其他阶段显示 items.length */
  getNodeItemCount(node: FlowNode): number {
    if (node.id === 'migrate') {
      return this.fileList.length;
    }
    return node.items.length;
  }

  /**
   * 节点运行入口：分发到 2 个 stage run 方法
   *   - ① 代码生成（migrate）→ 复用现有 check()（即一键迁移生成 AI 建议）
   *   - ② 功能验证（ut_test）→ POST /advise/skill/ut_test（注入 ut_test skill 后跑 Agent）
   * ★ 串行门禁：② 必须上游 success 才能运行（按钮 disabled + 此处运行时二次校验双保险，
   *   防 runnable 与真实状态短暂失步时误点穿透）。
   */
  runFlowNode(node: FlowNode) {
    if (node.running) {
      return;
    }
    // ★ 串行门禁运行时校验：比 disabled 更可靠（disabled 状态可能滞后一次变更检测）
    const gate = this.gateBlockReason(node);
    if (gate) {
      this.plxMessage.warning(gate, '');
      return;
    }
    // ★ 前置校验：migrate 节点必须先选模型，否则 check() 会因 !selectedModel 早返回，
    //   queryAI 不会被调用，finally 不跑，node.running 永远卡在 true，按钮永久置灰。
    //   ut_test 由后端校验模型选择，_streamSkillStage 的 then/catch
    //   会正常还原 node.running，不存在卡死风险，无需前端校验。
    if (node.id === 'migrate' && !this.selectedModel) {
      this.plxMessage.warning('请选择模型', '');
      return;
    }
    // ★ v4.x：已成功的阶段重跑前确认（用户取消则不产生 boundary commit，
    //   不污染 list_project_history）
    if (!this.confirmRerunIfNeeded(node)) {
      return;
    }
    // ★ v3.2：校验全部通过后才产生前边界 commit（捕获用户意图，无论后端是否正常产生
    //   agent-finish commit，前端都已经留下"用户点击过"的锚点）。
    //   注意：必须放在上面的前置校验之后 —— 否则未选模型的误点也会往用户仓库写入
    //   user-click-run-migrate 标记提交，污染 list_project_history，且回退迁移
    //   可能锚定到这些虚假标记点。
    this._preBoundaryCommit(node.id);
    switch (node.id) {
      case 'migrate':
        this.runMigrateNode(node);
        break;
      case 'ut_test':
        this.runUtTestNode(node);
        break;
    }
  }

  /**
   * ① 代码生成：复用现有 check()，迁移完成回调里联动下游节点
   * 进入时把 node 设为 activeRunNode，让 queryAI() 的 finally 块能更新节点 status。
   *
   * 校验已上移到 runFlowNode 入口（migrate 节点需先选模型，否则 check() 早返回导致按钮卡死）。
   */
  private runMigrateNode(node: FlowNode) {
    node.running = true;
    node.status = 'running';
    node.errorMessage = undefined;
    this.activeRunNode = node;
    this.cdr.markForCheck();

    // 复用现有 check() 触发迁移；后续接入时可在 check() 完成后回调 onNodeSuccess('migrate')
    this.check();
  }

  /**
   * ② 功能验证：注入 ut_test skill，拉一个项目 Agent 跑可对比单元测试 + qemu 回归
   * 调用 _streamSkillStage()：把响应流喂给 AI 侧面板，结束时回调 onDone 标记节点状态。
   */
  private runUtTestNode(node: FlowNode) {
    this._streamSkillStage(
      node,
      '功能验证',
      this.codeMigApi.runUtTestUrl(),
    );
  }

  // ====================================================================
  // ★ v4.x.0-RESUME：一键迁移中断恢复
  //   - refreshResumableStatus(dir_id)：调后端探测三阶段是否有可恢复 qwen 会话。
  //     把结果写入每个 FlowNode 的 hasResumableSession，
  //     模板据此显示或隐藏"继续"按钮。
  //   - resumeNode(node)：用户点击"继续"按钮时调，复用既有 queryAI 流式
  //     消费逻辑（activeRunNode + migrateResumeUrl）启动 `qwen --continue`。
  //   - 这两个方法都遵循硬约束"不动 queryAI / _consumeAgentStream / cancelRequest"，
  //     仅在尾部追加新分支。
  // ====================================================================
  private refreshResumableStatus(dirId: number) {
    if (!this.user_name || !dirId) {
      return;
    }
    this.codeMigApi.migrateResumableStatus({
      user_name: this.user_name,
      dir_id: dirId,
    }).subscribe({
      next: (res: any) => {
        if (res?.code !== 0 || !res.stages) {
          this._resumableProbeInFlight = false;
          return;
        }
        for (const node of this.flowNodes) {
          const stageKey = node.id === 'migrate' ? 'projectmigrate' : 'uttest';
          const s = res.stages[stageKey];
          node.hasResumableSession = !!(s && s.available);
        }
        this.cdr.markForCheck();
        this._resumableProbeInFlight = false;
      },
      error: (err: any) => {
        console.warn('[一键迁移] 探测可恢复会话失败（已忽略）', err);
        this._resumableProbeInFlight = false;
      },
    });
  }

  // ★ v4.x.0-RESUME：探测调度（带 debounce + in-flight 防抖）。
  //   多个失败点（取消 / 流错误 / 网络异常 / 兜底 catch）短时间内可能
  //   多次触发，统一收敛到一次后端请求，避免风暴。
  //   - AbortError（用户取消）也允许触发：取消后卷里 session 仍在，按钮应出现。
  private _resumableProbeInFlight = false;
  private _resumableProbeTimer: any = null;
  private _scheduleRefreshResumable(dirId: number, delayMs: number = 200): void {
    if (!dirId || !this.user_name) return;
    if (this._resumableProbeTimer) {
      clearTimeout(this._resumableProbeTimer);
    }
    this._resumableProbeTimer = setTimeout(() => {
      this._resumableProbeTimer = null;
      if (this._resumableProbeInFlight) return;
      this._resumableProbeInFlight = true;
      this.refreshResumableStatus(dirId);
    }, delayMs);
  }

  public resumeNode(node: FlowNode) {
    if (!node.hasResumableSession || node.running) {
      return;
    }
    // ★ v4.x：已成功的阶段不再续跑（会话已闭环；正常路径探针也不会再报 available）
    if (node.status === 'success') {
      this.plxMessage.info(`「${node.label}」阶段已完成，无需继续`, '');
      return;
    }
    // ★ 串行门禁：续跑与运行同权，未解锁阶段同样禁止「继续」
    const gate = this.gateBlockReason(node);
    if (gate) {
      this.plxMessage.warning(gate, '');
      return;
    }
    // ★ v3.2：续行前先产生前边界 commit（reason=user-click-resume-{stage}）。
    //   v3.2 铁律 4：续行不清理工作区，由前后端双侧 commit 锚定用户意图。
    this._preResumeBoundaryCommit(node.id);
    // 生成新的 requestUUID（旧容器已被 docker --rm 清掉，但命名卷保留）
    const requestUUID = this._generateUuid();
    this.currentRequestUUID = requestUUID;
    this.activeRunNode = node;

    // 进入运行态：徽章变"运行中"，按钮置灰
    node.running = true;
    node.status = 'running';
    node.errorMessage = undefined;
    this.cdr.markForCheck();

    // 复用 _streamSkillStage 流式消费逻辑（与"运行 ②/③"完全相同）：
    // 唯一的区别是 URL 变成 migrateResumeUrl 且 body 多带一个 stage。
    // 字段名 agent_model / api_format 必须与 query_project_migrate / _build_skill_runner
    // 的 parameters.get(...) 读取键一致，否则后端拿不到 API Key。
    this._streamSkillStage(
      node,
      `继续 ${node.label}`,
      this.codeMigApi.migrateResumeUrl(),
      {
        user_name: this.user_name,
        task_id: this.task_id,
        dir_id: this.dir_id,
        agent_model: this.selectedModel,
        api_format: this.selectedApiformat || 'openai',
        request_uuid: requestUUID,
        stage: node.id === 'migrate' ? 'project_migrate' : 'ut_test',
      },
    );
  }

  private _generateUuid(): string {
    // 轻量 UUID v4；不依赖外部库
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * ★ v3.2：前边界 commit — 用户点击"运行"瞬间触发。
   * fire-and-forget，不阻塞前端流程；后端 finally 块仍会兜底 agent-finish commit。
   * src=codemig-boundary 触发后端 force_commit_marker 用 git add -u（不"神秘保存"草稿）。
   */
  private _preBoundaryCommit(stage: 'migrate' | 'ut_test'): void {
    const reason = `user-click-run-${stage}`;
    this.codeMigApi.migrateBoundaryCommit({
      user_name: this.user_name,
      dir_id: this.dir_id,
      reason,
      src: 'codemig-boundary',
      stage: 'marker',
      type: 'marker',
    }).subscribe({
      next: (res: any) => {
        console.info(`[boundary] pre-boundary committed: ${reason}, sha=${res?.sha}`);
      },
      error: (e: any) => {
        console.error(`[boundary] pre-boundary commit failed: ${reason}`, e);
      },
    });
  }

  /**
   * ★ v3.2：续行前边界 commit — 用户点击"继续"瞬间触发。
   * 与 _preBoundaryCommit 共用后端 boundary_commit 路由，
   * 但 reason 不同便于 UI 区分"运行"vs"继续"。
   */
  private _preResumeBoundaryCommit(stage: 'migrate' | 'ut_test'): void {
    const reason = `user-click-resume-${stage}`;
    this.codeMigApi.migrateBoundaryCommit({
      user_name: this.user_name,
      dir_id: this.dir_id,
      reason,
      src: 'codemig-boundary',
      stage: 'marker',
      type: 'marker',
    }).subscribe({
      next: (res: any) => {
        console.info(`[boundary] resume-boundary committed: ${reason}, sha=${res?.sha}`);
      },
      error: (e: any) => {
        console.error(`[boundary] resume-boundary commit failed: ${reason}`, e);
      },
    });
  }

  /**
   * ★ v3.2：后边界 commit — 阶段收尾时触发（成功 / 失败 / 取消）。
   * 失败也必须 commit，保证用户在 git log 看到完整链路。
   */
  private _postBoundaryCommit(stage: 'migrate' | 'ut_test',
                              outcome: 'success' | 'error' | 'cancel'): void {
    const reason = `stage-end-${outcome}`;
    try {
      this.codeMigApi.migrateBoundaryCommit({
        user_name: this.user_name,
        dir_id: this.dir_id,
        reason,
        src: 'codemig-boundary',
        stage: 'marker',
        type: 'marker',
      }).subscribe({
        next: (res: any) => {
          console.info(`[boundary] post-boundary committed: ${reason}, sha=${res?.sha}`);
        },
        error: (e: any) => {
          // ★ v3.2 兜底：post 是 best-effort，HTTP 错误只 console 警告，不阻塞主流程
          console.warn(`[boundary] post-boundary commit failed (best-effort): ${reason}`, e);
        },
      });
    } catch (e) {
      // subscribe() 本身抛错（极少见，如 Observable 创建阶段）也不影响主流程
      console.warn(`[boundary] post-boundary commit threw (best-effort): ${reason}`, e);
    }
  }

  /**
   * 通用阶段技能执行入口：
   *   - 通过 queryAI 风格的流式 fetch 拉取 Agent 输出
   *   - 复用侧面板流式渲染
   *   - 进入时 node.running=true / status='running'，徽章显示「运行中」，按钮置灰
   *   - Agent 完成（DONE 且未报错）→ status='success'，徽章显示「已完成」，顶部 X/3 完成 +1
   *   - Agent 异常 → status='error'，徽章显示「失败」，顶部 X/3 完成不变
   */
  private _streamSkillStage(
    node: FlowNode,
    label: string,
    url: string,
    bodyOverride: any | null = null,
  ) {
    // ★ 进入运行态：徽章 → 运行中、按钮置灰、触发顶部计数器刷新
    node.running = true;
    node.status = 'running';
    node.errorMessage = undefined;
    this.activeRunNode = node;
    // ★ v4.x：流式输出绑定到该阶段——运行期间点击本节点走"折叠切换"而非重载，
    //   AI 面板展示的就是本阶段的实时输出
    this.aiStageFilter = node.id;
    this.cdr.markForCheck();

    // 统一 UUID：caller 通过 bodyOverride.request_uuid 显式传入时（"继续"按钮场景），
    // 复用 caller 的 UUID，避免 body 里的 request_uuid 与 currentRequestUUID 不一致
    // 导致 cancel_agent 删错 Docker 容器（"继续"按钮场景下，docker rm 会删到不存在的容器）。
    const requestUUID = bodyOverride?.request_uuid ?? this.agentApi.getRandomUUID();
    // 临时清空 currentRequestUUID 再调 cancelRequest：
    //   避免 cancel_agent 用本任务的新 UUID 去后端取消（容器尚未启动 → 后端 No such container
    //   → 200 → cancel_agent:2082 回调把 currentRequestUUID 清空 → stopWithConfirm 守卫误判）。
    //   此时 cancel_agent 跳过（不发无用请求），但 abortController.abort() 仍能打断旧 SSE 流；
    //   后端 GeneratorExit 处理（query_ai_handler.py:195）保证上一个任务的 Docker 容器被清理。
    this.currentRequestUUID = '';
    this.cancelRequest();
    this.currentRequestUUID = requestUUID;
    this.isGenerating = true;
    // 新一轮流式开始：恢复"跟随最新输出"，与上翻暂停配合
    this.streamFollowEnabled = true;
    this.isCleared = false;
    this.showAIPanel = true;
    this.abortController = new AbortController();
    // 会话保活：流式响应不续期后端会话，任务运行期间靠心跳防止 401 登出
    this._startSessionKeepalive();

    // ★ v4.x.0-RESUME：bodyOverride 不为空时（继续按钮调用）整体替换默认 payload。
    //   默认 null 时走原路径（行为完全不变）。
    const payload: any = bodyOverride ?? {
      user_name: this.user_name,
      dir_id: this.dir_id,
      task_id: this.task_id,
      request_uuid: requestUUID,
      agent_model: this.selectedModel || undefined,
      api_format: this.selectedApiformat || undefined,
    };

    this._consumeAgentStream(url, payload, requestUUID).then((result: { ok: boolean; msg?: string }) => {
      this.isGenerating = false;
      this._stopSessionKeepalive();
      this.abortController = null;
      node.running = false;
      if (result.ok) {
        node.status = 'success';
        node.errorMessage = undefined;
        this.plxMessage.success(`${label}完成`, '');
        this.onNodeSuccess(node.id);
      } else {
        node.status = 'error';
        node.errorMessage = result.msg || '未知错误';
        this.plxMessage.error(`${label}失败`, node.errorMessage);
        // ★ 串行门禁：失败不解锁下游，但刷新 runnable 保持一致（上游 error → 下游仍锁）
        this.refreshRunnability();
      }
      // ★ v3.2：阶段收尾时产生后边界 commit
      //   success / error 两条路径都 commit（互为冗余防丢）
      //   后端 finally 块也会兜底 stage-end-success / stage-end-error；
      //   cancel 由 stopWithConfirm 单独触发（不走这条路径）。
      this._postBoundaryCommit(
        node.id,
        result.ok ? 'success' : 'error'
      );
      // 阶段结束后刷新文件列表 + 当前 diff
      this.loadFileList();
      // ★ 功能验证收尾：test/ 下已有新生成的测试产物，刷新 ② 节点 items
      //   （直接扫文件系统，不依赖 DB 入库时序）
      this.loadUtTestFiles();
      if (this.selectedFileId) {
        this.loadFileDiff(this.selectedFileId);
      }
      this.cdr.markForCheck();
    }).catch((err: any) => {
      this.isGenerating = false;
      this._stopSessionKeepalive();
      this.abortController = null;
      node.running = false;
      node.status = 'error';
      const errMsg = err?.message || '网络错误';
      node.errorMessage = errMsg;
      this.plxMessage.error(`${label}失败`, errMsg);
      // ★ 串行门禁：异常路径同样刷新 runnable（不解锁，仅保持状态一致）
      this.refreshRunnability();
      // ★ v3.2：catch 路径也必须 commit，捕获所有未预期的网络异常
      this._postBoundaryCommit(node.id, 'error');
      // ★ v4.x.0-RESUME：兜底探测，按钮立刻出现
      if (this.dir_id) this._scheduleRefreshResumable(this.dir_id);
      this.cdr.markForCheck();
    });
  }

  /**
   * 流式文本追加（queryAI 与 _consumeAgentStream 共用，保证多条链路显示一致）。
   * 剥离 chunk 中的 think 边界标签（4 种变体见 THINK_TAG_VARIANTS）后，内容
   * 不分流地追加到 buf.suggestion——与刷新后 reopen 恢复行为一致，思考与正文
   * 都是普通文本，全部进建议面板。
   */
  private _appendStreamText(chunk: string, buf: { suggestion: string }): void {
    buf.suggestion += this._stripThinkTags(chunk);
  }

  /**
   * 剥离 think 边界标签本身。无标签时返回原引用，避免流式热路径上的多余分配。
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

  /**
   * 流式 Agent 响应消费：与 queryAI 行为完全一致，但允许传入动态 url，
   * 用于代码生成 / 功能验证 / 性能优化 三个按钮共用。
   * 返回 { ok, msg }：ok=true 表示成功结束（非异常 status），ok=false 表示流中检测到错误。
   */
  private async _consumeAgentStream(url: string, payload: any, _requestUUID: string) {
    let agentStreamErrorReported = false;
    let detectedErrorMsg = '';
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
      if (response.status === 401) {
        this.plxMessage.error("身份验证失效、请重新登录", "");
        this.logoutService.logout();
        return { ok: false, msg: '身份验证失效' };
      }
      if (!response.ok) throw new Error(`请求失败: ${response.status}`);
      if (response.body != null) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value);
          let lineEndIndex;
          while ((lineEndIndex = buffer.indexOf('\n')) >= 0) {
            const line = buffer.substring(0, lineEndIndex).trim();
            buffer = buffer.substring(lineEndIndex + 1);
            if (line) {
              try {
                const jsonData = JSON.parse(line);
                if (jsonData.status === 3) {
                  // AGENT_KEY_INFO
                  try {
                    const keyInfo = JSON.parse(jsonData.value || '{}');
                    const prefix = keyInfo.key_prefix ? `（Key: ${keyInfo.key_prefix}...）` : '';
                    this.plxMessage.info(`正在使用模型：${keyInfo.model || ''} ${prefix}`, "");
                  } catch { /* ignore */ }
                } else if (jsonData.status === 1) {
                  // RECEIVING_RESULT：剥 think 标签后整体进 suggestion（与 queryAI 共用）
                  if (typeof jsonData.value === 'string') {
                    this._appendStreamText(jsonData.value, this.aiStreamBuffer);
                  }
                  const now = Date.now();
                  if (!this.aiStreamDebounceTimer && now - this.lastRenderTime > 200) {
                    this.aiStreamDebounceTimer = setTimeout(() => {
                      this.suggestion = this.aiStreamBuffer.suggestion;
                      this.aiStreamDebounceTimer = null;
                      this.lastRenderTime = Date.now();
                      this.cdr.markForCheck();
                    }, 200);
                  }
                } else if (jsonData.status === 0) {
                  // DONE
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
                    agentStreamErrorReported = true;
                    detectedErrorMsg = resultOk === false && hasResult === true
                      ? 'AI 生成未正常完成（服务返回失败或已取消）'
                      : `AI Agent 异常结束（has_result=${String(hasResult)}, returncode=${String(returnCode)}）`;
                  }
                } else if (jsonData.status === -1 || jsonData.status === -2 || jsonData.status === -3) {
                  agentStreamErrorReported = true;
                  detectedErrorMsg = (jsonData.value ?? '').toString() || 'AI 生成失败';
                }
              } catch (e) {
                console.error('解析JSON失败:', e);
              }
            }
          }
        }
      }
      // 流结束：flush 防抖
      if (this.aiStreamDebounceTimer) {
        clearTimeout(this.aiStreamDebounceTimer);
        this.aiStreamDebounceTimer = null;
      }
      this.suggestion = this.aiStreamBuffer.suggestion;
      this.aiStreamBuffer = { suggestion: '' };
      this.cdr.markForCheck();
      // ★ v4.x.0-RESUME：流错误结束后探测，按钮立刻出现
      if (this.dir_id) this._scheduleRefreshResumable(this.dir_id);
      return { ok: !agentStreamErrorReported, msg: detectedErrorMsg };
    } catch (error: any) {
      // ★ v4.x.0-RESUME：含 AbortError（用户取消）也探测。
      //   取消后卷里 session 仍在，按钮应出现，用户可继续。
      if (error.name === 'AbortError') {
        if (this.dir_id) this._scheduleRefreshResumable(this.dir_id);
        return { ok: false, msg: '已取消' };
      }
      if (this.dir_id) this._scheduleRefreshResumable(this.dir_id);
      throw error;
    }
  }

  /**
   * 节点完成回调：★ 串行门禁解锁钩子
   *   上游 success → 刷新 runnable，下游按钮从置灰变为可点。
   *   error / cancel 不解锁（下游保持锁定直到上游真正成功）。
   */
  private onNodeSuccess(nodeId: FlowNodeId) {
    this.refreshRunnability();
    // 解锁提示：下游从锁定变可点时给用户一个明确信号
    const downstream = nodeId === 'migrate' ? 'ut_test' : null;
    if (downstream) {
      const next = this.flowNodes.find(n => n.id === downstream);
      if (next && next.runnable) {
        this.plxMessage.success(`「${this.flowNodes.find(n => n.id === nodeId)?.label}」完成，可运行下一阶段`, '');
      }
    }
    this.cdr.markForCheck();
  }

  goBack() {
    this.router.navigate(['/codemig/task'], {
      queryParams: { task_id: this.task_id },
    });
  }

  exportPatch() {
    // 打开增量 patch 弹窗：默认起点=历史下拉框选中项，终点=当前 HEAD
    this.patchFromHash = this.selectedHistoryHash || '';
    // patchToHash 留空表示当前 HEAD（与后端约定一致）
    this.patchToHash = '';
    this.showPatchDialog = true;
  }

  // 弹窗关闭
  closePatchDialog() {
    this.showPatchDialog = false;
  }

  /** 后端出错时返回 JSON blob（HTTP 200 + application/json），正常时为
      text/plain 补丁流。返回 true 表示已按错误处理完毕，调用方直接 return。 */
  private handlePatchBlobError(blob: any): boolean {
    if (blob && blob.type && blob.type.includes('application/json')) {
      blob.text().then((text: string) => {
        try {
          const err = JSON.parse(text);
          this.plxMessage.error('导出失败', err.msg || '');
        } catch {
          this.plxMessage.error('导出失败', '');
        }
      });
      return true;
    }
    return false;
  }

  // 弹窗确认：执行增量 patch 导出
  confirmExportPatch() {
    if (!this.patchFromHash) {
      this.plxMessage.warning('请选择补丁起点', '');
      return;
    }
    // 起点终点相同
    if (this.patchToHash && this.patchFromHash === this.patchToHash) {
      this.plxMessage.warning('起点与终点相同，无需导出', '');
      return;
    }
    // 起点晚于终点防呆。仅当终点显式选择时校验：终点为空 = HEAD，
    // 而 reflog 遗弃提交（时间晚于 HEAD）作为起点是合法场景，不能拦。
    if (this.patchToHash) {
      const fromTime = this.historyList.find(h => h.hash === this.patchFromHash)?.time || '';
      const toTime = this.historyList.find(h => h.hash === this.patchToHash)?.time || '';
      if (fromTime && toTime && fromTime > toTime) {
        this.plxMessage.warning('起点版本晚于终点版本，将得到撤销式补丁，请确认选择', '');
        return;
      }
    }
    this.exportingPatch = true;
    const body: any = {
      'user_name': this.user_name,
      'dir_id': this.dir_id,
      'from_hash': this.patchFromHash,
    };
    if (this.patchToHash) {
      body['to_hash'] = this.patchToHash;
    }
    this.codeMigApi.generateProjectPatch(body, {
      responseType: 'blob',
      observe: 'response',
    }).subscribe({
      next: (response: any) => {
        this.exportingPatch = false;
        // 后端出错时返回 JSON，正常时返回 blob
        if (this.handlePatchBlobError(response.body)) {
          return;
        }
        let filename = 'incremental.patch';
        const content_disposition = response.headers.get('Content-Disposition');
        if (content_disposition) {
          const match = content_disposition.match(/filename\*=UTF-8''(.+)/i);
          if (match && match.length >= 2 && match[1]) {
            filename = decodeURIComponent(match[1]);
          }
        }
        const url = window.URL.createObjectURL(response.body);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        this.showPatchDialog = false;
        this.plxMessage.success('补丁已导出', '');
      },
      error: (err: any) => {
        this.exportingPatch = false;
        this.plxMessage.error('导出失败', '');
        console.error('export patch error:', err);
      },
    });
  }

  // 切换全量 patch 导出（不选起点时，导出初始→HEAD 全量补丁）
  exportFullPatch() {
    this.exportingPatch = true;
    const body = { 'user_name': this.user_name, 'task_id': this.task_id };
    this.codeMigApi.exportPatchDownload(body, {
      responseType: 'blob',
      observe: 'response',
    }).subscribe({
      next: (response: any) => {
        this.exportingPatch = false;
        // 后端出错时返回 JSON，正常时返回补丁流
        if (this.handlePatchBlobError(response.body)) {
          return;
        }
        let filename = 'default.patch';
        const content_disposition = response.headers.get('Content-Disposition');
        if (content_disposition) {
          const match = content_disposition.match(/filename\*=UTF-8''(.+)/i);
          if (match && match.length >= 2 && match[1]) {
            filename = decodeURIComponent(match[1]);
          }
        }
        const url = window.URL.createObjectURL(response.body);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        this.showPatchDialog = false;
      },
      error: (err: any) => {
        this.exportingPatch = false;
        this.plxMessage.error('导出失败', '');
        console.error('export full patch error:', err);
      },
    });
  }

  rollbackProject() {
    if (this.selectedHistoryHash) {
      // 定向回退：跳转到指定历史点（基于 reflog，可逆）
      const confirmed = window.confirm('将回退到选中的历史版本，工作区文件会被重置，是否继续？\n（可通过历史下拉框重新选择更晚的版本跳回）');
      if (!confirmed) return;
      const body = {
        'user_name': this.user_name,
        'dir_id': this.dir_id,
        'target_hash': this.selectedHistoryHash,
      };
      this.codeMigApi.rollbackProjectMigrate(body).subscribe((res: any) => {
        if (res.code === 0) {
          this.plxMessage.success('回退成功', res.msg || '');
          this.selectedHistoryHash = '';
          this.loadProjectHistory();
          this.loadFileList();
          if (this.selectedFileId) {
            this.loadFileDiff(this.selectedFileId);
          }
          this.cdr.markForCheck();
        } else {
          this.plxMessage.error('回退失败', res.msg || '');
        }
      });
    } else {
      // 默认回退：回到最近一次迁移前
      const confirmed = window.confirm('将丢弃最近一次一键迁移的所有改动，回退到迁移前状态，是否继续？');
      if (!confirmed) return;
      const body = { 'user_name': this.user_name, 'dir_id': this.dir_id };
      this.codeMigApi.rollbackProjectMigrate(body).subscribe((res: any) => {
        if (res.code === 0) {
          this.plxMessage.success('回退成功', res.msg || '');
          this.suggestion = '';
          this.showAIPanel = false;
          this.loadProjectHistory();
          this.loadFileList();
          if (this.selectedFileId) {
            this.loadFileDiff(this.selectedFileId);
          }
          this.cdr.markForCheck();
        } else {
          this.plxMessage.error('回退失败', res.msg || '');
        }
      });
    }
  }

  // 加载迁移历史（reflog 驱动），用于历史下拉框和 patch 弹窗
  // ─── ② 功能验证（ut_test）：测试产物清单加载 ────────────────────
  // 背景：uttest skill 在 <repo>/test/<目标文件名>/ 下生成 main.c / Makefile /
  //   run.sh / coverage.txt / expected.out / actual.out 等产物，后端
  //   /task/ut_test_files 按目录扫描分组返回。此前前端 ② 节点只渲染静态
  //   占位文案（items 从未填充），功能验证跑完也看不到测试文件。
  // 触发时机：
  //   1. 页面加载（loadFileList 所在的任务切换分支，与 loadProjectHistory 同批）
  //   2. ② 功能验证阶段收尾（_streamSkillStage then 回调，紧随 loadFileList）
  loadingUtTestFiles = false;

  loadUtTestFiles() {
    if (!this.dir_id) return;
    this.loadingUtTestFiles = true;
    this.codeMigApi.getUtTestFiles({
      user_name: this.user_name,
      dir_id: this.dir_id,
    }).subscribe({
      next: (res: any) => {
        this.loadingUtTestFiles = false;
        const node = this.flowNodes.find(n => n.id === 'ut_test');
        if (!node) return;
        if (res?.code === 0 && Array.isArray(res.data?.targets)) {
          // 展开为逐文件条目（每个测试产物文件一行，点击可在 diff 编辑器打开）：
          // 通过 file_id 关联 fileList（generated 文件已在库中）；
          // 未入 fileList 的（极少）仍展示文件名，只是不可点击。
          const items: any[] = [];
          for (const t of res.data.targets) {
            for (const f of (t.files || [])) {
              items.push({
                target_name: t.target_name,
                rel_path: t.rel_path,
                name: f.name,
                path: f.path,
                file_id: f.file_id ?? null,
                size: f.size,
                has_coverage: t.has_coverage,
                diff_passed: t.diff_passed,
              });
            }
          }
          node.items = items;
          // 有产物时自动展开节点，让用户立刻看到生成的测试文件
          if (items.length > 0) {
            node.collapsed = false;
          }
        }
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.loadingUtTestFiles = false;
        console.warn('[功能验证] 加载测试文件清单失败（已忽略）', err);
        this.cdr.markForCheck();
      },
    });
  }

  /**
   * ② 阶段产物条目 → diff 编辑器 + AI 面板阶段联动：
   * 优先用后端返回的 file_id（DB 已入库的 generated 文件）直接打开；
   * 为空时再按 path 在 fileList 里找；都没有则只提示（DB 尚未入库或
   * 文件不在列表中的极小窗口）。
   * stageId：条目所属阶段（ut_test），用于把 AI 面板
   * 切换到对应阶段的最近一次输出。
   */
  onStageFileClick(item: any, stageId: FlowNodeId) {
    if (this.isGenerating) {
      this.plxMessage.warning('AI 正在生成，请稍候...', '');
      return;
    }
    // ★ 阶段联动：无论 file_id 是否命中，AI 面板先切到该阶段最近输出
    this.syncAiPanelToStage(stageId);
    let fileId: number | null = item.file_id ?? null;
    if (!fileId) {
      const entry = this.fileList.find((f: any) => f.file_path === item.path);
      fileId = entry?.file_id ?? null;
    }
    if (fileId) {
      // 直接走切换逻辑（onFileClick 会把面板联动回 migrate，这里绕开它）
      this.confirmAndSwitchFile(fileId).then((ok) => {
        if (ok) {
          this.switchToFile(fileId);
        }
      });
      return;
    }
    this.plxMessage.info(
      `文件：${item.rel_path}/${item.name}（尚未入库，稍后刷新可见）`, '');
  }

  /** 测试文件大小人性化显示 */
  utTestFileSize(size: number): string {
    if (size == null) return '';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  loadProjectHistory() {
    if (!this.dir_id) return;
    this.loadingHistory = true;
    const body = { 'user_name': this.user_name, 'dir_id': this.dir_id };
    this.codeMigApi.listProjectHistory(body).subscribe({
      next: (res: any) => {
        this.loadingHistory = false;
        if (res?.code === 0 && Array.isArray(res.data)) {
          this.historyList = res.data;
        } else {
          this.historyList = [];
        }
        this.rebuildHistoryOptions();
        // ★ 刷新后恢复三阶段徽章状态（从 marker commit 配对推断，详见方法注释）
        this.restoreFlowStatusFromHistory();
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingHistory = false;
        this.historyList = [];
        this.rebuildHistoryOptions();
        this.cdr.markForCheck();
      },
    });
  }

  check() {
    if (!this.selectedModel) {
      this.plxMessage.warning("请选择模型", "");
      return;
    }
    this.cancelRequest();
    this.suggestion = '';
    this.showAIPanel = true;
    this.isGenerating = true;
    // 新一轮流式开始：恢复"跟随最新输出"，与上翻暂停配合
    this.streamFollowEnabled = true;
    this.isCleared = false;
    this.currentRequestUUID = this.agentApi.getRandomUUID();
    this.abortController = new AbortController();
    // 会话保活：流式响应不续期后端会话，任务运行期间靠心跳防止 401 登出
    this._startSessionKeepalive();

    // ────── 阶段 13.x-MANUAL-ITEMS-TO-JSON：手动选中 → manual_items ──────
    // 把 manualMigrateItemsMap（用户在前端 diff 视图选中的所有代码段）序列化成
    // 后端期望的 manual_items 数组塞进 body，让 AI 在 scan_result.json 里能看到这些段并处理。
    // file_path 三层兜底解析：
    //   1) fileList 中的项（主数据源）
    //   2) extraFileListItems 缓存（用户在 diff 里手动加入但不在 fileList 中的文件）
    //   3) lastLoadedFileMeta 缓存（最近一次 diff 响应里拿到的 file_path）
    // 解析不到的直接跳过，避免污染 AI 输入。
    const manualItems: Array<{
      file_id: number;
      file_path: string;
      start_line: number;
      end_line: number;
    }> = [];
    for (const [fid, arr] of this.manualMigrateItemsMap) {
      if (!arr || arr.length === 0) continue;
      const fromFileList = this.fileList.find(f => f.file_id === fid);
      const fromExtra = this.extraFileListItems.get(fid);
      const fromMeta = this.lastLoadedFileMeta[fid] || {};
      const filePath: string =
        (fromFileList && fromFileList.file_path) ||
        (fromExtra && fromExtra.file_path) ||
        (fromMeta && fromMeta.file_path) ||
        '';
      for (const sel of arr) {
        if (!sel || sel.start_line == null || sel.end_line == null) continue;
        if (!filePath) continue;  // 跳过 file_path 无法解析的条目
        manualItems.push({
          file_id: fid,
          file_path: filePath,
          start_line: sel.start_line,
          end_line: sel.end_line,
        });
      }
    }
    console.info('[一键迁移] manual_items 序列化完成', {
      taskId: this.task_id,
      dirId: this.dir_id,
      count: manualItems.length,
      files: new Set(manualItems.map(m => m.file_id)).size,
    });

    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      agent_model: this.selectedModel,
      api_format: this.selectedApiformat,
      request_uuid: this.currentRequestUUID,
      manual_items: manualItems,
    };
    this.queryAI(body);
  }

  // AI 流式响应的防抖定时器（延长到 200ms 以减少渲染频率）
  private aiStreamDebounceTimer: any = null;
  private aiStreamBuffer = { suggestion: '' };
  private lastRenderTime = 0;

  // ★ v4.x.0-RUN-FLOW：queryAI 流程中的流式错误标记 + 检测到的错误消息
  // 用于 queryAI 的 finally 块判定 activeRunNode 走 success 还是 error
  private queryAiStreamError: string | null = null;

  async queryAI(payload: any) {
    const url = this.codeMigApi.migrateProjectUrl();
    this.queryAiStreamError = null;
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

      if (response.status === 401) {
        this.plxMessage.error("身份验证失效、请重新登录", "");
        this.logoutService.logout();
        return;
      }
      if (!response.ok) throw new Error('请求失败');
      if (response.body != null) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let agentStreamErrorReported = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value);
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
                  // 剥 think 标签后整体进 suggestion（与 _consumeAgentStream 共用）
                  if (typeof jsonData.value === 'string') {
                    this._appendStreamText(jsonData.value, this.aiStreamBuffer);
                  }
                  // 使用防抖 + 时间戳限制，确保至少间隔 200ms 才更新 UI
                  const now = Date.now();
                  if (!this.aiStreamDebounceTimer && now - this.lastRenderTime > 200) {
                    this.aiStreamDebounceTimer = setTimeout(() => {
                      this.suggestion = this.aiStreamBuffer.suggestion;
                      this.aiStreamDebounceTimer = null;
                      this.lastRenderTime = Date.now();
                      this.cdr.markForCheck();
                    }, 200);
                  }
                } else if (jsonData.status === 0) {
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
                    this.queryAiStreamError = msg;
                    this.plxMessage.error(msg, "");
                    this.aiStreamBuffer.suggestion += `\n\n[ERROR] ${msg}\n`;
                    this.suggestion = this.aiStreamBuffer.suggestion;
                    this.cdr.markForCheck();
                  }
                } else if (jsonData.status === -1 || jsonData.status === -2 || jsonData.status === -3) {
                  agentStreamErrorReported = true;
                  const errText = (jsonData.value ?? '').toString() || 'AI 生成失败';
                  this.queryAiStreamError = errText;
                  this.plxMessage.error("AI 生成失败", errText);
                  this.cdr.markForCheck();
                }
              } catch (e) {
                console.error('解析JSON失败:', e);
              }
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        // ★ 用户主动停止（stopWithConfirm → cancelRequest → abort）：不能静默吞掉。
        //   queryAiStreamError 保持 null 的话，finally 会把 migrate 节点误判为
        //   success——弹"完成"提示并解锁阶段②，但实际什么都没生成。
        this.queryAiStreamError = '已取消';
      } else {
        this.queryAiStreamError = error?.message || '网络错误';
        this.plxMessage.error("请求错误", "");
      }
      console.error('请求错误:', error);
    } finally {
      // 清除防抖定时器
      if (this.aiStreamDebounceTimer) {
        clearTimeout(this.aiStreamDebounceTimer);
        this.aiStreamDebounceTimer = null;
      }
      // 确保最终状态更新
      this.suggestion = this.aiStreamBuffer.suggestion;
      this.aiStreamBuffer = { suggestion: '' };

      this.isGenerating = false;
      this.isCleared = false;
      this.abortController = null;
      // 会话保活：queryAI 结束（成功/取消/异常都走 finally），心跳随之停止
      this._stopSessionKeepalive();

      // ★ v4.x.0-RUN-FLOW：把 ①代码生成 的节点状态推进到 success / error
      //   - 无错误 → status='success'，徽章「已完成」，顶部 X/3 完成 +1
      //   - 有错误 → status='error'，徽章「失败」，顶部 X/3 完成 不变
      //   - 走 check()（人工重跑 / 老路径）的场景下 activeRunNode 为 null，安全跳过
      const migrateNode = this.activeRunNode && this.activeRunNode.id === 'migrate'
        ? this.activeRunNode
        : null;
      if (migrateNode && migrateNode.running) {
        if (this.queryAiStreamError) {
          migrateNode.status = 'error';
          migrateNode.errorMessage = this.queryAiStreamError;
          // ★ 串行门禁：失败不解锁 ②，刷新 runnable 保持一致
          this.refreshRunnability();
        } else {
          migrateNode.status = 'success';
          migrateNode.errorMessage = undefined;
          this.onNodeSuccess('migrate');
        }
        migrateNode.running = false;
        this.activeRunNode = null;
      }

      // 迁移完成后：刷新文件列表 + 重新加载当前文件 diff
      this.loadFileList();
      if (this.selectedFileId) {
        this.loadFileDiff(this.selectedFileId);
      }
      this.cdr.markForCheck();
    }
  }

  async cancel_agent() {
    const payload: any = {
      dir_id: this.dir_id,
      request_uuid: this.currentRequestUUID,
    };
    try {
      const url = this.codeMigApi.cancelAISuggestionUrl();
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
        this.currentRequestUUID = '';
      }
    } catch (error) {
      console.error('取消时出错:', error);
      this.plxMessage.warning("取消失败", "");
    }
  }

  /**
   * "停止生成"按钮的入口包装：弹窗确认后调 cancelRequest()。
   * 弹窗只能挂在"用户主动点停止"这一个入口上；cancelRequest() / cancel_agent()
   * 必须保持纯净，因为它们会被 _streamSkillStage（运行 ②/③ + 继续按钮）、
   * check()（重新生成）、ngOnDestroy（组件销毁）等场景复用，那些场景下
   * 不应该弹窗（属于内部清理）。
   */
  async stopWithConfirm() {
    // 没在生成中时不弹窗（避免空弹窗骚扰）
    if (!this.currentRequestUUID) {
      return;
    }
    const confirmed = window.confirm(
      '确定要停止当前生成吗？\n' +
      '停止后会立即清理正在运行的 Docker 容器并丢弃当前生成结果，无法恢复。'
    );
    if (!confirmed) {
      return;
    }
    // ★ v3.2：取消前先产生后边界 commit（reason=stage-end-cancel），
    //   即使后端 GeneratorExit 误判 interrupted，前端 cancel 也会留下 commit。
    if (this.activeRunNode) {
      this._postBoundaryCommit(this.activeRunNode.id, 'cancel');
    }
    this.cancelRequest();
  }

  cancelRequest() {
    if (this.currentRequestUUID) {
      this.cancel_agent();
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  copyContent() {
    // 复制完整内容（_suggestion），而非 clamp 后的渲染文本
    this.clipboard.copy(this._suggestion);
    this.plxMessage.success("复制成功", "");
  }

  clearContent() {
    this.suggestion = '';
    this.isLiked = false;
    this.isDisliked = false;
    this.isCleared = true;
    this.plxMessage.success("清除成功", "");
  }

  startResize(event: MouseEvent) {
    event.preventDefault();
    const container = document.querySelector('.editor-container') as HTMLElement;
    if (!container) return;
    // 文件列表固定占 240px，可拖拽区域是剩余宽度在 diff 和 AI 面板之间分配
    const filePanel = container.querySelector('.file-list-panel') as HTMLElement;
    const filePanelWidth = filePanel ? filePanel.getBoundingClientRect().width : 240;
    const draggableWidth = container.getBoundingClientRect().width - filePanelWidth;
    const onMouseMove = (e: MouseEvent) => {
      const mouseX = e.clientX - container.getBoundingClientRect().left - filePanelWidth;
      const leftPercent = Math.max(20, Math.min(80, (mouseX / draggableWidth) * 100));
      this.leftPanelFlex = Math.round(leftPercent);
      this.rightPanelFlex = 100 - this.leftPanelFlex;
    };
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  // ─── 新增：核心交互方法 ───
  
  // 保存监听器 disposable，用于清理
  private selectionListenerDisposable: monaco.IDisposable | null = null;
  
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
   * 设置选中监听（启用悬浮按钮）
   */
  setupSelectionListener(): void {
    // 确保编辑器已初始化
    if (!this.editorRef) {
      console.warn('编辑器未初始化，无法设置选中监听');
      return;
    }
    
    // 先清理旧的监听器
    if (this.selectionListenerDisposable) {
      this.selectionListenerDisposable.dispose();
      this.selectionListenerDisposable = null;
    }
    
    const modifiedEditor = this.editorRef.getModifiedEditor();
    
    // 保存新的监听器 disposable
    this.selectionListenerDisposable = modifiedEditor.onDidChangeCursorSelection((e) => {
      try {
        const selection = e.selection;
        if (selection && this.isRealSelection(selection)) {
          // 有真正的选中内容时显示悬浮按钮
          const position = new monaco.Position(
            selection.endLineNumber,
            selection.endColumn
          );
          this.createAiWidget(position);
        } else {
          // 无选中内容时移除悬浮按钮
          this.removeAiWidget();
        }
      } catch (err) {
        // 防止 selection 回调异常导致按钮"看起来没反应"
        console.warn('[一键迁移] 选中监听回调异常（已忽略）', err);
      }
    });
  }

  /**
   * 右键菜单：当右键落在某段 manual_selection 区间内时，弹出"删除本手动选中的代码 (Lx-Ly)"
   * 使用纯 DOM 实现，避免依赖 Monaco 内部 ContextMenuService。
   */
  private manualSelectionContextMenuDisposable: monaco.IDisposable | null = null;
  private manualSelectionContextMenuEl: HTMLElement | null = null;
  private manualSelectionContextMenuOutsideClickHandler: ((ev: MouseEvent) => void) | null = null;

  setupManualSelectionContextMenu(modifiedEditor: monaco.editor.IStandaloneCodeEditor): void {
    if (!modifiedEditor) return;

    // 清理旧的监听器与菜单元素
    if (this.manualSelectionContextMenuDisposable) {
      this.manualSelectionContextMenuDisposable.dispose();
      this.manualSelectionContextMenuDisposable = null;
    }
    this._removeManualSelectionContextMenu();

    this.manualSelectionContextMenuDisposable = modifiedEditor.onContextMenu((e) => {
      const lineNumber = e.target?.position?.lineNumber;
      if (!lineNumber) return;
      const fileId = this.selectedFileId;
      if (!fileId) return;
      const arr = this.manualMigrateItemsMap.get(fileId);
      if (!arr || arr.length === 0) return;

      // 查找落点行所在的手动选中段
      const hit = arr.find(s => lineNumber >= s.start_line && lineNumber <= s.end_line);
      if (!hit) return;

      // 阻止 Monaco 默认的右键菜单
      if (e.event && typeof e.event.preventDefault === 'function') {
        e.event.preventDefault();
      }
      if (e.event && typeof e.event.stopPropagation === 'function') {
        e.event.stopPropagation();
      }

      const nativeEvent = e.event as any;
      const clientX = nativeEvent?.clientX ?? 100;
      const clientY = nativeEvent?.clientY ?? 100;
      this._showManualSelectionContextMenu(clientX, clientY, fileId, hit.start_line, hit.end_line);
    });
  }

  private _showManualSelectionContextMenu(clientX: number, clientY: number,
                                          fileId: number, start: number, end: number): void {
    this._removeManualSelectionContextMenu();

    const menu = document.createElement('div');
    menu.className = 'project-migrate-manual-context-menu';
    Object.assign(menu.style, {
      position: 'fixed',
      // 默认紧贴点击位置（不偏移），等挂载后再视口边界修正
      left: clientX + 'px',
      top: clientY + 'px',
      zIndex: '99999',
      minWidth: '180px',
      padding: '4px 0',
      background: '#ffffff',
      border: '1px solid #d9d9d9',
      borderRadius: '4px',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
      fontSize: '13px',
      color: '#333',
      cursor: 'pointer',
      userSelect: 'none',
    } as CSSStyleDeclaration);

    const item = document.createElement('div');
    item.textContent = `删除本手动选中的代码 (L${start}-L${end})`;
    Object.assign(item.style, {
      padding: '6px 12px',
      whiteSpace: 'nowrap',
    } as CSSStyleDeclaration);
    item.addEventListener('mouseenter', () => {
      item.style.background = '#e6f7ff';
    });
    item.addEventListener('mouseleave', () => {
      item.style.background = 'transparent';
    });
    item.addEventListener('click', (ev) => {
      ev.stopPropagation();
      this._removeManualSelectionContextMenu();
      this.removeManualSelectionByRange(fileId, start, end);
    });
    menu.appendChild(item);

    // 关键：先 append 再读 offset 修正位置，避免菜单超出视口右/下边界导致"看起来很远"。
    document.body.appendChild(menu);

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const menuWidth = menu.offsetWidth || 180;
    const menuHeight = menu.offsetHeight || 36;
    // 横向：默认从点击处向左展开；超出右边界则改贴右边
    if (clientX + menuWidth > vw - 4) {
      menu.style.left = Math.max(4, vw - menuWidth - 4) + 'px';
    }
    // 纵向：默认在点击点正下方；超出下边界则上移到点击点上方
    if (clientY + menuHeight > vh - 4) {
      menu.style.top = Math.max(4, clientY - menuHeight) + 'px';
    }

    this.manualSelectionContextMenuEl = menu;

    // 点击页面其它位置或按 Esc 自动关闭
    this.manualSelectionContextMenuOutsideClickHandler = (ev: MouseEvent) => {
      if (!this.manualSelectionContextMenuEl) return;
      if (this.manualSelectionContextMenuEl.contains(ev.target as Node)) return;
      this._removeManualSelectionContextMenu();
    };
    // mousedown 阶段拦截比 click 更稳（避免与 Monaco 的右键处理再次冲突）
    setTimeout(() => {
      document.addEventListener('mousedown', this.manualSelectionContextMenuOutsideClickHandler!, true);
      document.addEventListener('keydown', this._onContextMenuEsc, true);
    }, 0);
  }

  private _onContextMenuEsc = (ev: KeyboardEvent): void => {
    if (ev.key === 'Escape') this._removeManualSelectionContextMenu();
  };

  private _removeManualSelectionContextMenu(): void {
    if (this.manualSelectionContextMenuEl && this.manualSelectionContextMenuEl.parentNode) {
      this.manualSelectionContextMenuEl.parentNode.removeChild(this.manualSelectionContextMenuEl);
    }
    this.manualSelectionContextMenuEl = null;
    if (this.manualSelectionContextMenuOutsideClickHandler) {
      document.removeEventListener('mousedown', this.manualSelectionContextMenuOutsideClickHandler, true);
      this.manualSelectionContextMenuOutsideClickHandler = null;
    }
    document.removeEventListener('keydown', this._onContextMenuEsc, true);
  }

  /**
   * 按 (file_id, start_line, end_line) 精确删除一个手动选中段，并刷新装饰器与 fileList 计数。
   * 设计：与 addSelectedToSuggestions 一样，in-place 修改 Map 中数组，保留与 fileList 的引用关系。
   * 不立即 flush（等下次切文件/组件销毁再统一落库）。
   */
  removeManualSelectionByRange(fileId: number, start: number, end: number): void {
    const arr = this.manualMigrateItemsMap.get(fileId);
    if (!arr) return;
    const idx = arr.findIndex(s => s.start_line === start && s.end_line === end);
    if (idx < 0) return;
    arr.splice(idx, 1);
    if (arr.length === 0) this.manualMigrateItemsMap.delete(fileId);

    // 方案 A：去掉 removeManualAnchor + renderDecorationsFromAnchors，
    // 改用 renderDecorationsForFile 统一重新渲染（AI 橙色 + manual 绿色）
    if (this.selectedFileId === fileId) {
      this.renderDecorationsForFile(fileId);
    }
    this.cdr.markForCheck();
    this.plxMessage.success(`已删除手动选中 L${start}-L${end}`, '');
    console.info('[一键迁移] 手动选中已删除', { fileId, start, end });

    // 关键修复：删除单条时调专用 delete 接口，精准从 DB 删一行。
    // 不能再调 flushManualSelectionsToBackend()，因为删除最后一条后 Map 会被清空，
    // flush 的"避免误清空 DB"拦截逻辑会把这次删除跳过，导致刷新后又出现。
    this.codeMigApi.deleteManualSuggestion({
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: fileId,
      start_line: start,
      end_line: end,
    }).subscribe({
      next: (res: any) => console.info('[一键迁移] manual_selection 右键单条已删除', {
        fileId, start, end, res,
      }),
      error: (err) => console.warn('[一键迁移] manual_selection 右键单条删除失败（已忽略）', err),
    });
  }
  
  /**
   * 创建悬浮 Widget（参照单文件组件的样式）
   */
  createAiWidget(position: monaco.Position): void {
    try {
      // 先移除旧的 widget（如果存在）
      this.removeAiWidget();

      // 确保编辑器已初始化
      if (!this.editorRef) {
        console.warn('编辑器未初始化，无法创建悬浮按钮');
        return;
      }

      const that = this; // 保存 this 指向

      this.aiActionWidget = {
        allowEditorOverflow: true, // 允许溢出编辑器边界
        getId: () => 'ai.suggestion.floating.widget',
        getDomNode: () => {
          const domNode = document.createElement('div');

          // 使用内联样式，与单文件组件一致
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
            whiteSpace: 'nowrap'
          });

          domNode.innerHTML = '<span>✨</span> 将选中代码添加到AI生成建议中';

          // 悬停效果
          domNode.onmouseenter = () => domNode.style.backgroundColor = '#0256b9';
          domNode.onmouseleave = () => domNode.style.backgroundColor = '#0366d6';

          // 点击事件
          domNode.onclick = (e) => {
            e.stopPropagation(); // 防止点击导致选区消失
            that.addSelectedToSuggestions();
            that.removeAiWidget(); // 点击后隐藏按钮
          };

          return domNode;
        },
        getPosition: () => ({
          position: position,
          preference: [
            monaco.editor.ContentWidgetPositionPreference.ABOVE,
            monaco.editor.ContentWidgetPositionPreference.BELOW
          ]
        })
      };

      const modifiedEditor = this.editorRef.getModifiedEditor();
      modifiedEditor.addContentWidget(this.aiActionWidget);
    } catch (err) {
      console.warn('[一键迁移] 创建悬浮按钮失败（已忽略）', err);
    }
  }
  
  /**
   * 移除悬浮 Widget
   */
  removeAiWidget(): void {
    if (!this.editorRef) {
      return;
    }
    if (this.aiActionWidget) {
      const modifiedEditor = this.editorRef.getModifiedEditor();
      modifiedEditor.removeContentWidget(this.aiActionWidget);
      this.aiActionWidget = null;
    }
  }
  
  /**
   * 确保 file_id 在 fileList 中存在。
   * - 如果已存在，返回原对象
   * - 如果不存在，从 lastLoadedFileMeta 拿 file_name/file_path 自动插入到 fileList 顶部
   *
   * 注意：后端 query_changes_for_file 响应里只有 original_file/file/changes，
   *       不会直接返回 file_path/file_name。但 loadFileDiff 的上游会确保这些字段
   *       在某些情况下通过别的字段暴露（file_name/file_path/relative_path 等）。
   *       如果都拿不到，则使用 file_id 作为占位符。
   */
  ensureFileInList(fileId: number): any {
    const existing = this.fileList.find(f => f.file_id === fileId);
    if (existing) {
      // 关键修复：无论文件是否已在 fileList 中，都同步到 extraFileListItems
      // 确保用户的 manualSelections 在 loadFileList 重新拉取时永远被保留
      this.extraFileListItems.set(fileId, existing);

      // 关键：让现有项的 manualSelections 引用 Map 中的数组（如果 Map 已有数据）
      const mapSelections = this.manualMigrateItemsMap.get(fileId);
      if (mapSelections) {
        existing.manualSelections = mapSelections;
        existing.totalSuggestions =
          (existing.aiSuggestions?.length || 0) + mapSelections.length;
      }
      return existing;
    }

    const meta = this.lastLoadedFileMeta[fileId] || {};
    const filePath =
      meta.file_path ||
      meta.file_name ||
      meta.relative_path ||
      meta.path ||
      `file_${fileId}`;
    const fileName = filePath.split(/[/\\]/).pop() || `file_${fileId}`;

    // 关键：如果 Map 中已经有该 file_id 的手动选中，直接共享引用
    const mapSelections = this.manualMigrateItemsMap.get(fileId) || [];

    const newItem: any = {
      file_id: fileId,
      file_name: fileName,
      file_path: filePath,
      file_source: 'missing', // 未知来源，统一标记为 missing（外部传入）
      num_changed_lines: 0,
      aiSuggestions: [],
      manualSelections: mapSelections, // 直接共享 Map 中的数组引用
      totalSuggestions: mapSelections.length,
      expanded: false,
    };

    // 关键：保存到 extraFileListItems，loadFileList 重新拉取时会保留这些外部文件
    this.extraFileListItems.set(fileId, newItem);

    this.fileList.unshift(newItem);
    console.info(
      '[一键迁移] 自动将外部文件加入待迁移列表',
      { fileId, filePath, fileName }
    );
    return newItem;
  }

  /**
   * 将选中的代码累加到迁移清单
   *
   * 一键迁移是整个工程的整体迁移，所有文件的选中状态必须跨文件保留：
   *   - manualMigrateItemsMap（Map<file_id, selections[]>）是权威存储
   *   - fileList 中的 manualSelections 必须共享同一个数组引用，避免双轨制数据丢失
   *   - 任何时候 fileList 中的项都从 Map 同步，UI 永远显示最新状态
   */
  addSelectedToSuggestions(): void {
    const selection = this.editorRef.getModifiedEditor().getSelection();
    if (!selection || selection.isEmpty()) {
      this.plxMessage.warning('请先选中需要迁移的代码段', '');
      return;
    }

    const modifiedStart = selection.startLineNumber;
    const modifiedEnd = selection.endLineNumber;
    const fileId = this.selectedFileId;

    if (!fileId) {
      this.plxMessage.warning('当前未选中任何文件', '');
      return;
    }

    // 方案 A：去掉 computeLineMapping 反查，manual 直接用 modified 行号
    // （用户敲字不再重画，原始行号语义不再必要）
    const startLine = modifiedStart;
    const endLine = modifiedEnd;
    const lineCount = endLine - startLine + 1;

    // 关键修复：从 Map 中取出当前文件的选中列表（不存在则新建）
    // 这是唯一权威存储，所有 fileList 项必须共享这个引用
    let selections = this.manualMigrateItemsMap.get(fileId);
    if (!selections) {
      selections = [];
      this.manualMigrateItemsMap.set(fileId, selections);
    }

    // 去重（基于原始行号）
    const exists = selections.some(m =>
      m.start_line === startLine && m.end_line === endLine
    );
    if (exists) {
      this.plxMessage.warning(`第 ${startLine}-${endLine} 行已在手动选中清单中`, '');
      return;
    }

    const newSelection = { start_line: startLine, end_line: endLine };
    selections.push(newSelection);

    // 关键修复：确保 fileList 中对应项的 manualSelections 共享 Map 中的数组引用
    // 这样无论何时 fileList 被重建，只要重新指向 Map 引用，数据就不会丢
    let currentFile = this.fileList.find(f => f.file_id === fileId);
    if (!currentFile) {
      currentFile = this.ensureFileInList(fileId);
    }
    if (currentFile) {
      // 共享同一个数组引用 - 避免双轨制数据不一致
      currentFile.manualSelections = selections;
      // 关键修复（阶段 X-AI-COUNT-INIT-1）：
      // 未展开下三角时 aiSuggestions 仍为空数组，但 num_changed_lines 已有真实 AI 建议数；
      // 这里取二者较大值作为 AI 数，避免徽章少算 AI 数。
      // 展开后 loadFileSuggestions 会用 aiSuggestions.length 覆盖 totalSuggestions，无需担心。
      const aiCount = Math.max(
        currentFile.aiSuggestions?.length || 0,
        currentFile.num_changed_lines || 0
      );
      currentFile.totalSuggestions = aiCount + selections.length;
    } else {
      console.info(
        '[一键迁移] 当前文件不在待迁移列表中，按 file_id 记录手动选中',
        { fileId, startLine, endLine }
      );
    }

    // 触发 UI 更新
    this.cdr.markForCheck();

    // 方案 A：去掉 addManualAnchor，刷新装饰器改用 renderDecorationsForFile
    // 统一渲染入口：AI 橙色 + manual 绿色，行号钉死
    if (this.selectedFileId === fileId) {
      this.renderDecorationsForFile(fileId);
    }

    // 关键修复（v4.0）：用户点击"添加到 AI 建议"时立即入库，避免刷新后丢失。
    // v4.0 后端 insert_manual 接口不再需要 task_id 和 file_path 字段。
    this.codeMigApi.insertManualSuggestion({
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: fileId,
      start_line: startLine,
      end_line: endLine,
      suggestion: '请转化为适配riscv架构的代码',
      append_or_replace: 2,
    }).subscribe({
      next: (res: any) => console.info('[一键迁移] manual_selection 单条已入库', {
        fileId, start: startLine, end: endLine, res,
      }),
      error: (err) => console.warn('[一键迁移] manual_selection 单条入库失败（已忽略）', err),
    });

    this.plxMessage.success(
      `已添加 ${lineCount} 行代码到迁移清单`,
      ''
    );
  }

  
  
  /**
   * 刷新当前文件的装饰器（统一管理 AI 建议 + 手动选中）
   *
   * 设计要点（阶段9重构）：
   *   - 放弃双轨制：AI 建议装饰器和手动选中装饰器现在统一在 decorationsCollection 中管理
   *   - 装饰器来源有两部分：
   *       1) AI 建议：从 lastAiChangesByFileId[fileId] 取（decorateEditor 调用时缓存）
   *       2) 手动选中：从 manualMigrateItemsMap[fileId] 取
   *   - 切文件 / 添加 / 删除任何一项都触发整体重画
   *   - 这样与单文件组件的 decorateEditor 行为一致（也是单 collection）
   */

  refreshFileDecorations() {
    if (!this.editorRef) return;

    const editor = this.editorRef as monaco.editor.IStandaloneDiffEditor;
    const modifiedEditor = editor.getModifiedEditor();
    const model: any = modifiedEditor.getModel();
    if (!model) return;

    const fileId = this.selectedFileId;
    if (!fileId) return;

    const totalLines = model.getLineCount();
    const allDecorations: any[] = [];

    // 1) 收集 AI 建议装饰器
    const aiChanges = this.lastAiChangesByFileId[fileId] || [];
    for (const change of aiChanges) {
      const suggestion_type = change[5];
      const ignored = change[6];
      if (ignored) continue;
      // 复用 decorateEditor 的 switch 逻辑
      switch (suggestion_type) {
        case SolverType.MACROS:
          this.appendChangeDecoration(model, allDecorations, change[0], change[1], change[2], change[3], '#FFA500');
          break;
        case SolverType.ASM_FILE:
          this.appendChangeDecoration(model, allDecorations, change[0], change[0], change[2], change[3], '#FFA500');
          break;
        default:
          this.appendChangeDecoration(model, allDecorations, change[0], change[1], change[2], change[3], '#FFA500');
      }
    }

    // 2) 收集手动选中装饰器
    const manualSelections = this.manualMigrateItemsMap.get(fileId) || [];
    manualSelections.forEach((m: any) => {
      // 防御：跳过超出当前模型范围的行号
      if (
        !m.start_line || !m.end_line ||
        m.start_line > totalLines ||
        m.end_line > totalLines ||
        m.start_line < 1 || m.end_line < 1 ||
        m.start_line > m.end_line
      ) {
        return;
      }
      const safeStartLine = m.start_line;
      const safeEndLine = m.end_line;
      const lineLength = model.getLineLength(safeEndLine);
      // 顶部：💡 图标 + 绿色（与 AI 橙色区分）
      allDecorations.push({
        range: new monaco.Range(
          safeStartLine,
          1,
          safeEndLine,
          lineLength + 1
        ),
        options: {
          beforeContentClassName: 'my-icon',
          inlineClassName: 'underline-suggestion',
          hoverMessage: {
            value: '**💡 手动选中**: 请转化为适配riscv架构的代码并高亮'
          },
          overviewRuler: {
            color: '#52c41a', // 绿色：与 AI 建议的橙色区分
            position: monaco.editor.OverviewRulerLane.Full,
          },
        },
      });
      // 底部：整行高亮
      allDecorations.push({
        range: new monaco.Range(
          safeStartLine,
          1,
          safeEndLine,
          lineLength + 1
        ),
        options: {
          isWholeLine: true,
          className: 'line-modified',
        },
      });
    });

    // 3) 重新创建 collection（先 clear 旧 collection，再创建新的）
    if (this.decorationsCollection) {
      this.decorationsCollection.clear();
    }
    // 关键：使用 modifiedEditor.createDecorationsCollection 创建（与 onEditorInit 中一致），
    // 保证装饰器在正确的编辑器上注册，切换文件后不会丢失
    this.decorationsCollection = modifiedEditor.createDecorationsCollection(allDecorations);
  }

  /**
   * 辅助方法：添加一个 AI 建议装饰器到 decorations 数组
   * 与 updateDecorations 的逻辑保持一致（橙色 underline）
   */
  private appendChangeDecoration(
    model: any,
    decorations: any[],
    startLine: number,
    endLine: number,
    append_or_replace: any,
    change_diff: any,
    overviewColor: string
  ) {
    const totalLines = model.getLineCount();
    if (
      !startLine || !endLine ||
      startLine > totalLines || endLine > totalLines ||
      startLine < 1 || endLine < 1 ||
      startLine > endLine
    ) {
      return;
    }
    const lineLength = model.getLineLength(endLine);
    const diff = this.escapeMarkdownHeaders(change_diff);
    const markdownContent = {
      value: `**💡 建议**${this.createSuggestion(append_or_replace)}: ${diff}`,
    };
    decorations.push({
      range: new monaco.Range(startLine, 1, endLine, lineLength + 1),
      options: {
        beforeContentClassName: 'my-icon',
        inlineClassName: 'underline-suggestion',
        hoverMessage: markdownContent,
        overviewRuler: {
          color: overviewColor,
          position: monaco.editor.OverviewRulerLane.Full,
        },
      },
    });
    decorations.push({
      range: new monaco.Range(startLine, 1, endLine, lineLength + 1),
      options: {
        isWholeLine: true,
        className: 'line-modified',
      },
    });
  }

  /**
   * 高亮显示指定行
   *
   * 关键修复（阶段 X-FLASH-HIGHLIGHT-1）：
   *   原实现用 `this.decorationsCollection.set([decoration])` 全量替换主 collection，
   *   然后 `setTimeout(() => this.decorationsCollection.clear(), 2000)` 把整个 collection
   *   清空 —— 导致 AI 建议与手动选中的所有装饰一并丢失。
   *   现在改用独立的临时 collection 装 flash 高亮，2 秒后只清这一个临时 collection，
   *   主 `decorationsCollection`（AI 建议 + 手动选中的统一管理）保持不变。
   */
  revealLine(lineNumber: number) {
    if (!this.editorRef) return;
    const modifiedEditor = this.editorRef.getModifiedEditor();
    modifiedEditor.revealLineInCenter(lineNumber);

    // 清理上一次临时高亮（避免连续点击叠加 + 闪烁）
    if (this.flashHighlightTimer) {
      clearTimeout(this.flashHighlightTimer);
      this.flashHighlightTimer = null;
    }
    if (this.flashDecorationsCollection) {
      this.flashDecorationsCollection.clear();
      this.flashDecorationsCollection = null;
    }

    // 用独立 collection 装 flash 高亮，不动主 decorationsCollection
    const decoration: monaco.editor.IModelDeltaDecoration = {
      range: new monaco.Range(lineNumber, 1, lineNumber, 1),
      options: {
        isWholeLine: true,
        className: 'highlight-line',
      },
    };
    this.flashDecorationsCollection =
      modifiedEditor.createDecorationsCollection([decoration]);

    this.flashHighlightTimer = setTimeout(() => {
      if (this.flashDecorationsCollection) {
        this.flashDecorationsCollection.clear();
        this.flashDecorationsCollection = null;
      }
      this.flashHighlightTimer = null;
    }, 2000);
  }
  
  /**
   * 展开/收起文件建议列表
   *
   * 关键修复（阶段 13.x-AI-SUGGESTIONS-LOAD-1）：
   *   原判断 `fileItem.totalSuggestions === 0` 会把"先加 manualSelection 后展开"
   *   场景误判为"无需加载 AI 建议"，导致 AI 建议始终为空、UI 显示"暂无 AI 建议"。
   *   现在用独立的 `_aiSuggestionsLoaded` 标志决定是否调 `loadFileSuggestions`，
   *   与 manualSelections 数量完全解耦。
   */
  toggleFileExpand(fileItem: any, event: MouseEvent) {
    event.stopPropagation();
    fileItem.expanded = !fileItem.expanded;

    if (fileItem.expanded && !fileItem._aiSuggestionsLoaded) {
      this.loadFileSuggestions(fileItem);
    }
  }
  
  /**
   * 加载文件的 AI 建议
   *
   * 关键修复（阶段 13.x-AI-SUGGESTIONS-LOAD-1）：
   *   设置 `_aiSuggestionsLoaded = true`，让 `toggleFileExpand` 不再重复请求。
   *   即使后端返回空 changes 也设 true —— "暂无 AI 建议"就是当前真实状态，
   *   不应该每点一次下拉框就发一次请求。
   *
   *   同时在请求发出前先置 `_aiSuggestionsLoaded = true`，避免用户在响应未
   *   返回前连续点击下拉框时重复发请求。
   */
  loadFileSuggestions(fileItem: any) {
    // 请求发出前先置标志，防抖消重
    fileItem._aiSuggestionsLoaded = true;

    const body = {
      'user_name': this.user_name,
      'task_id': this.task_id,
      'dir_id': this.dir_id,
      'file_id': fileItem.file_id,
    };

    this.codeMigApi.getTaskFileChange(body).subscribe({
      next: (response: any) => {
        if (response.code == 0) {
          const changes = response.changes || [];
          fileItem.aiSuggestions = changes.map((change: any) => ({
            start_line: change[0],
            end_line: change[1],
            // change 列序：[起始行, 结束行, 添加/替换, 建议正文, change_id, 类型码]
            // type 必须取 change[5]（类型码，对应 SolverType），取 change[3] 会把整段建议正文渲染进类型徽标
            type: this.getSolverTypeLabel(change[5]),
            reason: change[3],
            new_code: change.new_code,
            change_id: change[4]   // ★ v4.1.8：保留 change_id，removeSuggestion 调后端 updateSuggestionIgnored 需要
          }));
          fileItem.totalSuggestions =
            (fileItem.aiSuggestions?.length || 0) +
            (fileItem.manualSelections?.length || 0);
        }
      },
      error: (err: any) => {
        // 请求失败时回退标志位，允许下次重新尝试
        fileItem._aiSuggestionsLoaded = false;
        console.error('加载文件建议失败:', err);
      }
    });
  }
  
  /**
   * 删除 AI 建议 —— 步骤 ①：打开二次确认弹窗
   * v4.1.8：之前直接 filter 不调后端，切换到单文件视图时该建议又会出现（DB 没改）。
   * 现在拆成 removeOption 风格（仅打开弹窗）+ confirmDeleteSuggestion 风格（点确认后调后端），
   * 与单文件视图 codemig-file-change-view.component.ts:954 removeOption 一致。
   */
  removeSuggestion(fileItem: any, suggestion: any, event: MouseEvent) {
    event.stopPropagation();
    event.preventDefault();
    this.deleteSuggestionOption = {
      fileItem: fileItem,
      suggestion: suggestion,
    };
    this.deleteSuggestionModal = this.modalService.open(this.content, { size: 'xs' });
  }

  /**
   * 删除 AI 建议 —— 步骤 ②：用户点弹窗确认后调后端 + UI 更新
   * 与单文件视图 codemig-file-change-view.component.ts:961 deleteSuggestion 中
   * "todo 增加后端屏蔽建议功能接口"分支一致：调 updateSuggestionIgnored(body)，
   * 成功后从 aiSuggestions 数组移除（用 change_id 精确匹配，不依赖 start/end_line）。
   */
  confirmDeleteSuggestion() {
    if (!this.deleteSuggestionOption) {
      if (this.deleteSuggestionModal) this.deleteSuggestionModal.close();
      return;
    }
    const fileItem = this.deleteSuggestionOption.fileItem;
    const suggestion = this.deleteSuggestionOption.suggestion;
    if (this.deleteSuggestionModal) {
      this.deleteSuggestionModal.close();
    }
    this.deleteSuggestionOption = null;

    if (!fileItem || !suggestion || suggestion.change_id == null) {
      // 没有 change_id（如老缓存数据）直接前端过滤兜底
      this.executeRemoveSuggestionUi(fileItem, suggestion);
      this.plxMessage.success('已删除该建议', '');
      return;
    }

    const body: any = {
      dir_id: this.dir_id,
      file_id: fileItem.file_id,
      change_id: suggestion.change_id,
      ignored: true,
    };
    this.codeMigApi.updateSuggestionIgnored(body).subscribe({
      next: (response: any) => {
        if (response && response.code === 0) {
          this.executeRemoveSuggestionUi(fileItem, suggestion);
          this.plxMessage.success('已删除该建议', '');
        } else {
          this.plxMessage.error('删除建议失败', response?.msg || '后端返回失败');
        }
      },
      error: (err: any) => {
        console.warn('[一键迁移] updateSuggestionIgnored 错误', err);
        this.plxMessage.error('删除建议失败', err?.error?.msg || err?.message || '网络错误');
      },
    });
  }

  /**
   * 删除 AI 建议 —— UI 更新（共享片段）
   * 与原 removeSuggestion 中 filter 逻辑一致：从 aiSuggestions 移除并刷新装饰器。
   */
  private executeRemoveSuggestionUi(fileItem: any, suggestion: any) {
    if (!fileItem || !fileItem.aiSuggestions) return;
    fileItem.aiSuggestions = fileItem.aiSuggestions.filter((s: any) =>
      s.change_id != null ? s.change_id !== suggestion.change_id
                          : (s.start_line !== suggestion.start_line || s.end_line !== suggestion.end_line)
    );
    fileItem.totalSuggestions =
      (fileItem.aiSuggestions?.length || 0) +
      (fileItem.manualSelections?.length || 0);

    // 同步从 lastAiChangesByFileId 中删除 —— 与 aiSuggestions 统一以 change_id 为锚点。
    // 之前这里按 (start_line, end_line) 匹配：两条建议行号相同时会误删未删除的那条；
    // 保存后行号漂移（DB 已 remap、内存缓存未同步）时则匹配不到，残留过期装饰。
    // 8 元组列序：[start, end, append_or_replace, suggestion, change_id, type, ignored, is_manual]
    const fid = fileItem.file_id;
    if (this.lastAiChangesByFileId[fid]) {
      this.lastAiChangesByFileId[fid] = this.lastAiChangesByFileId[fid].filter((c: any) =>
        suggestion.change_id != null
          ? !(c && c[4] === suggestion.change_id)
          : !(c && c[0] === suggestion.start_line && c[1] === suggestion.end_line)
      );
    }

    if (this.selectedFileId === fid && this.editorRef) {
      // 方案 A：去掉 renderDecorationsFromAnchors，改用 renderDecorationsForFile 统一渲染
      // 同时画 AI（橙色）+ manual（绿色），避免删除 AI 时把 manual 也抹掉。
      this.renderDecorationsForFile(fid);
    }
    this.cdr.markForCheck();
  }
  
  /**
   * 将当前 manualMigrateItemsMap 一次性落库到后端 codemig_manual_selection 表。
   * 触发时机：
   *   1. 切换文件时（queryParams.file_id 变化）
   *   2. 切换 task/dir 时
   *   3. 组件销毁（ngOnDestroy）
   * 设计：
   *   - 覆盖式写入：后端按 (task_id, dir_id) DELETE 后再 INSERT，避免增量 diff 复杂度
   *   - file_path 来源：fileList → extraFileListItems → lastLoadedFileMeta（按优先级）
   *   - 没有 file_path 的项跳过（不会污染 DB）
   */
  private flushManualSelectionsToBackend(): void {
    // v4.0 no-op：manual 选中通过 insertManualSuggestion 在用户点击时立即入库，
    // 不再需要批量 flush。删除/取消选中也通过 deleteManualSuggestion 立即生效。
    // 保留此方法为 no-op 以避免破坏现有调用点（L222/L234/L2256）。
  }

  /**
   * 从后端 DB 加载的手动选中中，in-place 合并到现有的 manualMigrateItemsMap。
   *
   * 背景：之前的实现是 `this.manualMigrateItemsMap = map` 整体替换，这会破坏 fileList
   *       中已有的 manualSelections 数组引用，导致 DB 数据加载回来后 fileList 仍显示空。
   *
   * 设计：
   *   - 不替换 Map 实例，只更新每个 file_id 内部的 selections 数组（in-place 替换元素）
   *   - 这样 fileList 中已存在的 manualSelections 引用会通过 React/Angular 检测自动同步
   *   - 强制重置 fileList 中所有相关项的 manualSelections 与 totalSuggestions，并强制刷新 UI
   *   - 对于当前未在 fileList 中出现的 file_id，会先确保它在 fileList 中存在（ensureFileInList）
   */
  private mergeManualSelectionsFromDb(
    dbMap: Map<number, Array<{ start_line: number; end_line: number; file_path?: string }>>
  ): void {
    if (!dbMap || dbMap.size === 0) {
      return;
    }

    let changedAny = false;
    for (const fileId of dbMap.keys()) {
      const dbSelections = dbMap.get(fileId);
      if (!dbSelections || dbSelections.length === 0) continue;

      // ★ 关键：把 DB 返回的 file_path 写回 lastLoadedFileMeta，
      //   确保后续 ensureFileInList 能拿到真实路径，而不是 file_<id> 占位。
      const dbFilePath = (dbSelections.find(s => !!s.file_path) || {}).file_path;
      if (dbFilePath) {
        const metaForFile = this.lastLoadedFileMeta[fileId] || {};
        if (metaForFile.file_path !== dbFilePath) {
          this.lastLoadedFileMeta[fileId] = {
            ...metaForFile,
            file_path: dbFilePath,
          };
        }
      }

      // 1) in-place 更新 manualMigrateItemsMap[fileId]
      const existing = this.manualMigrateItemsMap.get(fileId);
      // 用去重逻辑：DB 数据 + in-memory 数据合并（DB 为权威，但 in-memory 用户当前未 flush 的也保留）
      const merged = new Map<string, { start_line: number; end_line: number }>();
      if (existing) {
        for (const s of existing) {
          merged.set(`${s.start_line}-${s.end_line}`, { ...s });
        }
      }
      for (const s of dbSelections) {
        const key = `${s.start_line}-${s.end_line}`;
        if (!merged.has(key)) {
          merged.set(key, { start_line: Number(s.start_line), end_line: Number(s.end_line) });
        }
      }

      const mergedArr = Array.from(merged.values()).sort(
        (a, b) => a.start_line - b.start_line
      );

      // 比较是否变化
      const existingLen = existing ? existing.length : 0;
      const changed =
        !existing ||
        existingLen !== mergedArr.length ||
        mergedArr.some((m, idx) => {
          const e = existing[idx];
          return !e || e.start_line !== m.start_line || e.end_line !== m.end_line;
        });

      this.manualMigrateItemsMap.set(fileId, mergedArr);
      if (changed) changedAny = true;

      // 2) 强制重置 fileList 中对应项
      // 注意：loadFileList 异步加载时 fileList 可能还没建立，但 merge 会兜底
      let fileItem = this.fileList.find(f => f.file_id === fileId);
      if (!fileItem) {
        fileItem = this.extraFileListItems.get(fileId);
      }
      if (!fileItem) {
        // 文件不在 list 中：若 lastLoadedFileMeta 已有真实 file_path，
        // 立即调用 ensureFileInList 把这条外部项加入 fileList，
        // 这样刷新页面后从 DB 恢复的"手动选中"能在侧栏展示出来，
        // 而不只是被默默丢弃。
        const meta = this.lastLoadedFileMeta[fileId] || {};
        if (meta.file_path) {
          fileItem = this.ensureFileInList(fileId);
        } else {
          // meta 为空时不要创建占位 "file_<id>"，避免污染后续 loadFileList 合并
          // 等用户真正访问该文件（loadFileDiff 触发）后再补建
          continue;
        }
      } else {
        // 已经在 fileList 中：用 meta 中的真实路径修正占位 file_name/file_path
        // 解决"显示 file_<id>"的历史遗留问题
        const meta = this.lastLoadedFileMeta[fileId] || {};
        if (meta.file_path && fileItem.file_path !== meta.file_path) {
          fileItem.file_path = meta.file_path;
          const tail = meta.file_path.split(/[/\\]/).pop();
          if (tail && (fileItem.file_name === `file_${fileId}` || !fileItem.file_name)) {
            fileItem.file_name = tail;
          }
        }
      }
      // 共享同一个数组引用
      if (!fileItem) continue;
      fileItem.manualSelections = mergedArr;
      fileItem.totalSuggestions =
        (fileItem.aiSuggestions?.length || 0) +
        mergedArr.length;
    }

    if (changedAny) {
      this.cdr.markForCheck();
      console.info('[一键迁移] mergeManualSelectionsFromDb 完成', {
        changedFiles: Array.from(dbMap.keys()),
      });
    }
  }

  /**
   * 删除手动选中的建议
   *
   * 一键迁移设计：fileList.manualSelections 与 manualMigrateItemsMap 共享同一数组引用。
   * 因此删除时直接修改 Map 中的数组即可，fileList 项会自动反映最新状态。
   */
  removeManualSelection(fileItem: any, manual: any, event: MouseEvent) {
    event.stopPropagation();
    const fileId = fileItem.file_id;

    // 关键：直接从 Map 修改（因为 fileList 与 Map 共享同一数组引用）
    const selections = this.manualMigrateItemsMap.get(fileId);
    if (selections) {
      const filtered = selections.filter(m =>
        m.start_line !== manual.start_line || m.end_line !== manual.end_line
      );
      if (filtered.length === 0) {
        this.manualMigrateItemsMap.delete(fileId);
      } else {
        // 保持 Map 中的引用不变，in-place 修改
        selections.length = 0;
        selections.push(...filtered);
      }
    }

    // 同步更新 fileItem 的显示（与 Map 共享同一数组引用，所以会反映最新状态）
    fileItem.manualSelections = this.manualMigrateItemsMap.get(fileId) || [];
    fileItem.totalSuggestions =
      (fileItem.aiSuggestions?.length || 0) +
      (fileItem.manualSelections?.length || 0);

    // 方案 A：去掉 removeManualAnchor + renderDecorationsFromAnchors，
    // 改用 renderDecorationsForFile 统一重新渲染（AI 橙色 + manual 绿色）
    if (this.selectedFileId === fileId) {
      this.renderDecorationsForFile(fileId);
    }
    this.cdr.markForCheck();

    this.plxMessage.success('已取消选中', '');

    // 关键修复：删除单条时调专用 delete 接口，精准从 DB 删一行。
    // 不能再调 flushManualSelectionsToBackend()，因为删除最后一条后 Map 会被清空，
    // flush 的"避免误清空 DB"拦截逻辑会把这次删除跳过，导致刷新后又出现。
    this.codeMigApi.deleteManualSuggestion({
      user_name: this.user_name,
      dir_id: this.dir_id,
      file_id: fileId,
      start_line: manual.start_line,
      end_line: manual.end_line,
    }).subscribe({
      next: (res: any) => console.info('[一键迁移] manual_selection 单条已删除', {
        fileId, start: manual.start_line, end: manual.end_line, res,
      }),
      error: (err) => console.warn('[一键迁移] manual_selection 单条删除失败（已忽略）', err),
    });
  }

  ngOnDestroy() {
    // 取消 AI 请求
    this.cancelRequest();
    // 会话保活心跳随组件销毁停止（任务在跑时用户离开页面，不再续期）
    this._stopSessionKeepalive();

    // 解绑文件树点击通道订阅
    if (this.migrateNavigateSub) {
      this.migrateNavigateSub.unsubscribe();
      this.migrateNavigateSub = null;
    }

    // 关键：组件销毁前将状态保存到 Service
    // 因为 migrate_project 路由有 data: { reuse: false }，组件被销毁后下次会重新创建。
    // 必须把用户的手动选中等状态持久化到 Service，新组件创建时从 Service 恢复。
    if (this.task_id && this.dir_id) {
      this.stateService.saveManualSelections(
        this.task_id,
        this.dir_id,
        this.manualMigrateItemsMap
      );
      this.stateService.saveAiChanges(
        this.task_id,
        this.dir_id,
        this.lastAiChangesByFileId
      );
      this.stateService.saveFileMeta(
        this.task_id,
        this.dir_id,
        this.lastLoadedFileMeta
      );
      console.info('[一键迁移] 状态已保存到 Service', {
        taskId: this.task_id,
        dirId: this.dir_id,
        fileCount: this.manualMigrateItemsMap.size,
      });

      // 落库到数据库（刷新页面/重启服务后仍能恢复）
      this.flushManualSelectionsToBackend();
    }

    // 取消未完成的 diff 加载请求
    if (this.pendingFileDiffSub && typeof this.pendingFileDiffSub.unsubscribe === 'function') {
      this.pendingFileDiffSub.unsubscribe();
      this.pendingFileDiffSub = null;
    }

    // 清理所有防抖定时器
    if (this.fileListLoadDebounceTimer) {
      clearTimeout(this.fileListLoadDebounceTimer);
      this.fileListLoadDebounceTimer = null;
    }
    if (this.aiStreamDebounceTimer) {
      clearTimeout(this.aiStreamDebounceTimer);
      this.aiStreamDebounceTimer = null;
    }
    if (this.editorLayoutDebounceTimer) {
      clearTimeout(this.editorLayoutDebounceTimer);
      this.editorLayoutDebounceTimer = null;
    }

    // 清理 Monaco 监听器
    if (this.selectionListenerDisposable) {
      this.selectionListenerDisposable.dispose();
      this.selectionListenerDisposable = null;
    }

    // 方案 A：删除 decorationRecalcTimer + diffChangeListener 字段清理

    // 清理右键菜单监听器与 DOM
    if (this.manualSelectionContextMenuDisposable) {
      this.manualSelectionContextMenuDisposable.dispose();
      this.manualSelectionContextMenuDisposable = null;
    }
    this._removeManualSelectionContextMenu();

    // 清理悬浮 Widget
    this.removeAiWidget();

    // 清理临时 flash 高亮 collection + timer（revealLine 用，独立于主 collection）
    if (this.flashHighlightTimer) {
      clearTimeout(this.flashHighlightTimer);
      this.flashHighlightTimer = null;
    }
    if (this.flashDecorationsCollection) {
      this.flashDecorationsCollection.clear();
      this.flashDecorationsCollection = null;
    }

    // 清理装饰器集合
    if (this.decorationsCollection) {
      this.decorationsCollection.clear();
    }
  }
}
