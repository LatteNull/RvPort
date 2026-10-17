import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CodemigTaskFileViewComponent } from '../codemig-task-file-view/codemig-task-file-view.component';
import { CodeMigApi } from '../api/codemig-api.service'
import { Subscription, interval } from 'rxjs';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { PlxMessage } from 'paletx';
interface SummaryItem {
  type: string;      // 建议类型
  issues: number;    // 问题数量
  affectedLines: number | null; // 影响行数，可能为空
}

@Component({
  selector: 'app-codemig-task-view',
  templateUrl: './codemig-task-view.component.html',
  styleUrl: './codemig-task-view.component.css',
  standalone: false,
})
export class CodemigTaskViewComponent implements OnInit{
  @ViewChild('plxTable') plxTable: any;
  user_name: any;
  task_id: any;
  task_name: any;
  created_time: any;
  summary_data: Array<SummaryItem> = [];
  directories: any;

  showLoading = false;

  file_data: Array<any> = [];
  file_columns: Array<any> = [];

  software_data: Array<any> =[];
  software_columns: Array<any> = [];

  missing_file_data: Array<any> = []
  missing_file_columns: Array<any> = []

  tabItems: Array<any> = [];

  success_dependence_data: Array<any> = [];
  fail_dependence_data: Array<any> = [];
  task_info: any;
  dependence_status: number = 1;
  fail_reason: any;

  switch_status: string = 'success';

  uploadPercentage!: string;

  dir_icon: any = '📂  ';
  file_icon: any = '📄  ';

  private subscription!: Subscription

  // ★ v5.0.0：一键迁移视图的"重新扫描"按钮状态字段
  isRescanning: boolean = false;
  rescanProcessed: number = 0;
  rescanTotal: number = 0;
  rescanStatus: number = 0;          // 0=空闲 / 1=运行中 / 2=成功 / 3=失败
  rescanFailReason: string = '';
  private rescanRequestCount: number = 0;
  // ★ 轮询兜底：后端 _rescan_states 是进程内存态，服务重启即丢失（status 永远回 0）。
  //   记录轮询发起时间，超过上限（30 分钟）仍未到终态就强制结束，避免按钮永久禁用 + 无限轮询。
  private rescanPollStartTime: number = 0;
  private static readonly RESCAN_POLL_TIMEOUT_MS = 30 * 60 * 1000;

  // ★ 切页通知不丢：rescan 轮询订阅必须活过组件销毁 —— 路由 reuse:false 下组件切页即销毁，
  //   若订阅挂在实例上会随 ngOnDestroy 一起被退订，后端扫描完成时前端无人感知、
  //   alert 也弹不出来。static 让订阅 + 轮询闭包（this 捕获）在组件销毁后继续运行，
  //   到终态或超时后自行 unsubscribe。startPollRescanStatus 先退订旧订阅再创建，
  //   同一时刻全局只有一条 rescan 轮询。
  private static rescanSubscription: Subscription | null = null;

  // 组件销毁标记：销毁后 finishRescan 不再刷新数据（queryData 重进页面天然拉新）
  private isDestroyed = false;

  // localStorage "rescan 进行中" 标记 key：用于重进任务页时补查状态 / 补发通知，
  // 顺带避免后端终态（status=2 永久驻留）导致的重复弹窗
  private rescanPendingKey(): string {
    return `rescan_pending_${this.task_id}`;
  }

  constructor(
    private route: ActivatedRoute,
    private codeMigApi: CodeMigApi,
    private router: Router,
    private plxMessage: PlxMessage) {
      this.user_name = localStorage.getItem('user_name');
  }

  ngOnInit() {
    this.InitTab()
    this.route.queryParams.subscribe(params => {
      this.task_id = Number(params['task_id']);
    });
    this.queryData();
  }

  InitTab(){
    this.tabItems.push({activeId: '源码扫描信息', title: '源码扫描信息', data: [], columns: this.createFileColumns(), is_obtain: false})
    this.tabItems.push({activeId: '软件包扫描信息', title: '软件包扫描信息', data: [], columns: this.createSoftWareColumns(), is_obtain: false})
    this.tabItems.push({activeId: '缺失文件信息', title: '缺失文件信息', data: [], columns: this.createMissingFileColumns(), is_obtain: false})
  }

  switchTab(status: any){
    this.switch_status = status
  }

  sharedColumns(){
    return [
      {
        key: 'file_index',
        title: '序号',
        width: '150px',
        show: true,
      },
      {
        key: 'task_id',
        show: false,
      },
      {
        key: 'dir_id',
        show: false,
      },
      {
        key: 'file_id',
        show: false,
      }
    ]
  }

  createFileColumns() {
    return [
      ...this.sharedColumns(),
      {
        key: 'file_name',
        title: '文件名',
        width: '200px',
        show: true,
      },
      {
        key: 'file_path',
        title: '路径',
        width: '800px',
        show: true,
      },
      {
        key: 'num_changed_lines',
        title: '发现问题数量',
        show: true,
      },
      {
        key: 'operation',
        title: '操作',
        show: true,
        contentType: 'component',
        component: CodemigTaskFileViewComponent,
      },
      {
        key: 'is_missing',
        show: false,
      },
    ];
  }

  createSoftWareColumns(){
    return [
      ...this.sharedColumns(),
      {
        key: 'file_name',
        title: '文件名',
        width: '200px',
        show: true,
      },
      {
        key: 'file_path',
        title: '路径',
        width: '800px',
        show: true,
      },
      {
        key: 'support_architecture',
        title: '支持架构',
        show: true,
      },
      {
        key: 'suggestion',
        title: '建议信息',
        show: true,
      },
    ];
  }

  createMissingFileColumns(){
    return [
      ...this.sharedColumns(),
      {
        title: '目录/文件',
        key: 'file_name',
        contentType: 'html',
      },
      {
        key: 'file_path',
        title: '缺失RV文件/现有架构文件',
        width: '600px',
        show: true,
      },
      {
        key: 'operation',
        title: '操作',
        show: true,
        contentType: 'component',
        component: CodemigTaskFileViewComponent,
      },
      {
        key: 'is_missing',
        show: false,
      }
    ]
  }

  addFile(file: any) {
    this.file_data = this.file_data.concat([{
      file_index: file[0],
      task_id: file[1],
      dir_id: file[2],
      file_id: file[3],
      file_name: file[4],
      file_path: file[5],
      num_changed_lines: file[6],
      is_missing: 'file',
    }]);
  }

  addSoftware(software: any) {
    this.software_data = this.software_data.concat([{
      file_index: software[0],
      task_id: software[1],
      dir_id: software[2],
      file_id: software[3],
      file_name: software[4],
      file_path: software[5],
      support_architecture: software[6],
      suggestion: software[7]
    }]);
  }

  addMissingFile(missing_file: any) {
    this.missing_file_data = this.missing_file_data.concat([{
      file_index: missing_file[0],
      task_id: missing_file[1],
      dir_id: missing_file[2],
      file_id: missing_file[3],
      file_name: missing_file[6] == 1 ? this.dir_icon + missing_file[4] : this.file_icon + missing_file[4],
      file_path: missing_file[5],
      is_missing: 'missing',
      children: [],
    }]);
  }

  queryData() {
    const body = { 'user_name': this.user_name, 'task_id': this.task_id };
    this.codeMigApi.getTaskFiles(body).subscribe({
      next: (response: any) => {
        if (response.code == 0){
          const my_data = response.data;
          this.task_name = my_data.task_name;
          this.created_time = my_data.created_time;
          this.directories = my_data.directories;
          for (const file of my_data.files) {
            this.addFile(file);
          }
          this.tabItems[0].data = this.file_data
          this.tabItems[0].is_obtain = true
          for (const summary of my_data.summary) {
            this.summary_data.push({
              type: summary[0],
              issues: summary[1],
              affectedLines: summary[2],
            });
          }
          if (my_data.is_scan_dependence == 1){
            this.tabItems.push({activeId: '依赖包扫描信息', title: '依赖包扫描信息', is_obtain: false})
          }
          // file_data 已就绪（dir_id 可取），补查是否有未收尾的 rescan
          this.checkRescanOnEnter();
        }
      },
      error: (errorResponse: any) => {
        console.error("Error: ", errorResponse);
      }
    });
  }

  // ★ 重进任务页时补查 rescan 状态（依赖 localStorage "进行中" 标记做去重）：
  //   - 还在扫（status=1）：恢复"扫描中 X/Y"显示并接管轮询（覆盖刷新浏览器、
  //     重开标签页等 static 订阅已丢的场景）；
  //   - 已结束（status=2/3）：补发一次通知；数据就是本次 queryData 刚拉的，无需再刷；
  //   - status=0：后端重启丢了内存态，静默清标记（轮询超时兜底已覆盖在场场景）。
  private checkRescanOnEnter() {
    const pendingKey = this.rescanPendingKey();
    if (localStorage.getItem(pendingKey) === null || this.file_data.length === 0) {
      return;
    }
    const dir_id = this.file_data[0].dir_id;
    const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dir_id': dir_id };
    this.codeMigApi.getRescanStatus(body).subscribe({
      next: (response: any) => {
        if (response.code != 0) {
          return;
        }
        if (response.status == 1) {
          this.isRescanning = true;
          this.rescanStatus = 1;
          this.rescanProcessed = response.processed || 0;
          this.rescanTotal = response.total || 0;
          // 接管轮询：startPollRescanStatus 会先退订旧实例留下的 static 订阅，
          // 保证全局只有本实例这一条轮询在跑
          this.startPollRescanStatus();
        } else if (response.status == 2 || response.status == 3) {
          // 复查标记：若切页期间旧轮询已弹过通知（finishRescan 已清标记），不再重复弹
          if (localStorage.getItem(pendingKey) === null) {
            return;
          }
          localStorage.removeItem(pendingKey);
          if (response.status == 2) {
            alert('重新扫描完成，数据已刷新');
          } else {
            alert(`重新扫描失败：${response.fail_reason || '后端扫描失败'}`);
          }
        } else {
          // status=0：后端无此任务状态（典型为后端重启），清标记防止每次进页都查
          localStorage.removeItem(pendingKey);
        }
      },
    });
  }

  tabChange(event: any){
    if (event.nextId == '软件包扫描信息' && !this.tabItems[1].is_obtain){
      const body = { 'user_name': this.user_name, 'task_id': this.task_id };
      this.codeMigApi.getTaskSoftware(body).subscribe({
        next: (response: any) => {
          if (response.code == 0){
            const my_data = response.data;
            for (const software of my_data.software) {
              this.addSoftware(software);
            }
            this.tabItems[1].data = this.software_data
            this.tabItems[1].is_obtain = true
          }
        },
      });
    }else if (event.nextId == '缺失文件信息' && !this.tabItems[2].is_obtain){
      const body = { 'user_name': this.user_name, 'task_id': this.task_id };
      this.codeMigApi.getTaskMissingFiles(body).subscribe({
        next: (response: any) => {
          if (response.code == 0){
            const my_data = response.data;
            for (const missing_file of my_data.missing_files_rows) {
              this.addMissingFile(missing_file);
            }
            this.tabItems[2].data = this.missing_file_data
            this.tabItems[2].is_obtain = true
          }
        },
      });
    }else if (event.nextId == '依赖包扫描信息' && !this.tabItems[3].is_obtain){
      const body = { 'user_name': this.user_name, 'task_id': this.task_id };
      let requestCount = 0;
      this.codeMigApi.getTaskDependenceSummary(body).subscribe({
          next: (response: any) => {
          if (response.code == 0){
            this.tabItems[3].is_obtain = true
          }
        },
      });

      this.codeMigApi.getTaskDependence(body).subscribe({
        next: (response: any) => {
          if (response.code == 0){
            this.task_info = response.data.task_info
            this.tabItems[3].is_obtain = true
            this.dependence_status = response.data.task_info[4]
            if (this.dependence_status == 1){
              this.uploadPercentage = ((response.data.count.total - response.data.count.processing)*100/response.data.count.total).toFixed(2)
              this.subscription = interval(5000).pipe(
                tap(() => {
                  if (requestCount >= 10) {
                    // 如果请求次数超过10次，取消当前订阅并创建新的订阅，间隔时间改为10秒
                    this.subscription.unsubscribe();
                    this.subscription = interval(10000).subscribe(() => {
                      this.queryTaskInfo();
                    });
                  } else {
                    // 请求次数未超过10次，继续执行查询
                    this.queryTaskInfo();
                  }
                  requestCount++;
                })
              ).subscribe();
            }else if (this.dependence_status == 2){
              this.success_dependence_data = response.data.success_dependence_data
              this.fail_dependence_data = response.data.fail_dependence_data
            }else if (this.dependence_status == 3){
              this.fail_reason = response.data.task_info[5]
            }
          }
        },
      });
    }
  }

  queryTaskInfo(){
    const body = { 'user_name': this.user_name, 'task_id': this.task_id };
    this.codeMigApi.getTaskDependence(body).subscribe({
      next: (response: any) => {
        if (response.code == 0){
          this.task_info = response.data.task_info
          this.dependence_status = response.data.task_info[4]
          if (this.dependence_status == 1){
            this.uploadPercentage = ((response.data.count.total - response.data.count.processing)*100/response.data.count.total).toFixed(2)
          }
          if (this.dependence_status == 2){
            this.success_dependence_data = response.data.success_dependence_data
            this.fail_dependence_data = response.data.fail_dependence_data
            this.subscription.unsubscribe();
          }else if (this.dependence_status == 3){
            this.fail_reason = response.data.task_info[5]
            this.subscription.unsubscribe();
          }
        }
      },
    });
  }

  transformNode(nodeData: any, parentIndex: string, taskId: any, dirId: any, fileId: any, selfIndex: any): any {
    const isDirectory = nodeData.type === 'dir';
    const currentPath = nodeData.name || '';
    const currentFullIndex = `${parentIndex}-${selfIndex + 1}`;
    // 处理当前节点
    const newNode: any = {
      file_index: "",
      task_id: taskId,
      dir_id: dirId,
      file_id: fileId,
      file_name: isDirectory ? this.dir_icon + currentPath.split('/').pop() || currentPath : this.file_icon + currentPath.split('/').pop() || currentPath,
      file_path: currentPath,
      isLeaf: !isDirectory,
      type: nodeData.type,
      children: []
    };

    // 【核心】递归处理预载的children
    if (isDirectory && nodeData.children && Array.isArray(nodeData.children)) {
      newNode.children = nodeData.children.map((child: any, index: number) => {
        return this.transformNode(child, currentFullIndex, taskId, dirId, fileId, index);
      });
    }

    return newNode;
  }

  getChildrenNode(row: any, data: any[]) {
    return data.map((item: any, index: number) => {
      const rawData = item[3];
      const isDirectory = item[4] === 1;

      // 如果索引3是对象且是目录
      if (isDirectory && typeof rawData === 'object') {
        // 调用上面的递归函数处理可能的嵌套
        return this.transformNode(rawData, row.file_index, item[0], item[1], item[2], index);
      } else {
        // 如果是普通文件（字符串）
        const filePath = typeof rawData === 'string' ? rawData : rawData.name;
        return {
          file_index: ``,
          task_id: item[0],
          dir_id: item[1],
          file_id: item[2],
          file_name: this.file_icon + filePath.split('/').pop() || filePath,
          file_path: filePath,
          isLeaf: true,
          type: 'file',
          children: []
        };
      }
    });
  }

  onRowExpandCollapse(event: any){
    // 如果是展开事件并且是头节点才会调用！
    if (event['row'].isExpanded && event['row'].parent == null) {
      this.showLoading = true
      const body = { 'user_name': this.user_name, 'file_id': event['row'].file_id, 'task_id': event['row'].task_id, 'dir_id': event['row'].dir_id };
      this.codeMigApi.getTaskExistingArch(body).subscribe({
        next: (response: any) => {
          event['row']['children'] = this.getChildrenNode(event['row'], response.data)
          this.showLoading = false;
          this.plxTable.dataChanged();
        },
      });
    }
  }

  exportExcel() {
    const body = { 'user_name': this.user_name, 'task_id': this.task_id };
    this.codeMigApi.exportReportDownload(body,{
      responseType: 'blob',
      observe: 'response',
    }).subscribe((response: any) => {
      // 从响应头获取文件名
      let filename = 'default.xlsx';
      const content_disposition = response.headers.get('Content-Disposition');
      const match = content_disposition.match(/filename\*=UTF-8''(.+)/i);
      if (match && match.length >= 2 && match[1]) {
        filename = decodeURIComponent(match[1]);
      }

      // 创建下载链接
      const url = window.URL.createObjectURL(response.body);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();

      // 清理
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    });
  }

  exportPatch() {
    const body = { 'user_name': this.user_name, 'task_id': this.task_id };
    this.codeMigApi.exportPatchDownload(body,{
      responseType: 'blob',
      observe: 'response',
    }).subscribe({
      next: (response: any) => {
        // 后端出错时返回 JSON（HTTP 200 + application/json），正常时返回补丁流
        const blob = response.body;
        if (blob && blob.type && blob.type.includes('application/json')) {
          blob.text().then((text: string) => {
            try {
              const err = JSON.parse(text);
              this.plxMessage.error('导出失败', err.msg || '');
            } catch {
              this.plxMessage.error('导出失败', '');
            }
          });
          return;
        }
        // 从响应头获取文件名
        let filename = 'default.patch';
        const content_disposition = response.headers.get('Content-Disposition');
        const match = content_disposition.match(/filename\*=UTF-8''(.+)/i);
        if (match && match.length >= 2 && match[1]) {
          filename = decodeURIComponent(match[1]);
        }

        // 创建下载链接
        const url = window.URL.createObjectURL(response.body);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        // 清理
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      },
      error: (err: any) => {
        this.plxMessage.error('导出失败', '');
        console.error('export patch error:', err);
      },
    });
  }

  ngOnDestroy(): void {
    this.isDestroyed = true;
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
    // ★ 故意不退订 CodemigTaskViewComponent.rescanSubscription：
    //   轮询闭包 + alert 需要在切页后继续工作，终态/超时时 finishRescan 会自行清理。
  }

  handleLinkClick(item: any){
    console.log(item)
    const params = {
      task_id: item[7],
      dependence_id: item[1],
    };
    this.router.navigate(['/codemig/dependence'], { queryParams: params });
  }

  // ─── v5.0.0：重新扫描按钮主入口 ───
  rescanTask() {
    if (this.isRescanning) {
      return;
    }
    if (!confirm('重新扫描将对工程下所有 changed 文件重新跑 18 种代码识别器，AI 旧建议会被新结果替换。\n已有的人工选中段不受影响。\n确认开始？')) {
      return;
    }
    this.isRescanning = true;
    this.rescanProcessed = 0;
    this.rescanTotal = 0;
    this.rescanStatus = 0;
    this.rescanFailReason = '';
    const dir_id = this.file_data.length > 0 ? this.file_data[0].dir_id : null;
    const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dir_id': dir_id };
    if (!dir_id) {
      this.finishRescan(false, '无法获取工程目录 ID，请等待源码扫描数据加载完成');
      return;
    }
    this.codeMigApi.rescanTask(body).subscribe({
      next: (response: any) => {
        if (response.code == 0) {
          this.rescanTotal = response.total;
          // 写"进行中"标记：重进任务页时据此补查状态/补发通知（checkRescanOnEnter）
          localStorage.setItem(this.rescanPendingKey(), String(dir_id));
          this.startPollRescanStatus();
        } else {
          this.finishRescan(false, response.msg || '启动失败');
        }
      },
      error: (err: any) => {
        this.finishRescan(false, err?.message || '网络错误');
      },
    });
  }

  private startPollRescanStatus() {
    this.rescanRequestCount = 0;
    this.rescanPollStartTime = Date.now();
    if (CodemigTaskViewComponent.rescanSubscription) {
      CodemigTaskViewComponent.rescanSubscription.unsubscribe();
    }
    CodemigTaskViewComponent.rescanSubscription = interval(5000).pipe(
      tap(() => {
        // ★ 兜底：超时仍未到终态（典型场景：rescan 中途后端重启，内存态丢失，
        //   status 永远回 0）就强制结束，避免 isRescanning 永久 true、按钮永久禁用。
        if (Date.now() - this.rescanPollStartTime > CodemigTaskViewComponent.RESCAN_POLL_TIMEOUT_MS) {
          this.finishRescan(false, '扫描状态查询超时（可能后端已重启），请手动刷新任务数据');
          return;
        }
        if (this.rescanRequestCount >= 10) {
          CodemigTaskViewComponent.rescanSubscription!.unsubscribe();
          CodemigTaskViewComponent.rescanSubscription = interval(10000).subscribe(() => {
            this.queryRescanStatus();
          });
        } else {
          this.queryRescanStatus();
        }
        this.rescanRequestCount++;
      })
    ).subscribe();
  }

  private queryRescanStatus() {
    const dir_id = this.file_data.length > 0 ? this.file_data[0].dir_id : null;
    const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dir_id': dir_id };
    this.codeMigApi.getRescanStatus(body).subscribe({
      next: (response: any) => {
        if (response.code != 0) {
          this.finishRescan(false, response.msg || '查询失败');
          return;
        }
        this.rescanStatus = response.status;
        this.rescanProcessed = response.processed;
        this.rescanTotal = response.total;
        this.rescanFailReason = response.fail_reason || '';
        if (response.status == 2) {
          this.finishRescan(true);
        } else if (response.status == 3) {
          this.finishRescan(false, this.rescanFailReason || '后端扫描失败');
        }
      },
      error: (err: any) => {
        this.finishRescan(false, err?.message || '网络错误');
      },
    });
  }

  private finishRescan(success: boolean, reason: string = '') {
    if (CodemigTaskViewComponent.rescanSubscription) {
      CodemigTaskViewComponent.rescanSubscription.unsubscribe();
      CodemigTaskViewComponent.rescanSubscription = null;
    }
    // 终态已出，清除"进行中"标记，避免重进任务页时重复补发通知
    localStorage.removeItem(this.rescanPendingKey());
    this.isRescanning = false;
    this.rescanStatus = success ? 2 : 3;
    if (!success) {
      this.rescanFailReason = reason;
    }
    // ★ alert 是 window 级弹窗，组件销毁后（用户已切页）照样全局可见；
    //   刷数据则仅限组件存活时——重进任务页的 queryData 会拉最新数据，无需重复刷。
    if (success) {
      if (!this.isDestroyed) {
        this.refreshAllData();
      }
      alert('重新扫描完成，已刷新任务数据');
    } else {
      alert(`重新扫描失败：${reason}`);
    }
  }

  private refreshAllData() {
    this.file_data = [];
    this.software_data = [];
    this.missing_file_data = [];
    this.summary_data = [];
    this.queryData();
  }

  // ─── 项目级一键迁移 ───
  migrateProject() {
    // ★ 守卫：queryData 尚在请求中（或 refreshAllData 刚清空 file_data）时，
    //   dir_id 取不到。此时跳转会带着 null dir_id 落到静默空白的迁移视图
    //   （所有 if (!this.dir_id) return 守卫触发，无任何报错），不如直接拦截。
    if (this.file_data.length === 0 || !this.file_data[0].dir_id) {
      alert('源码扫描数据尚未加载完成，请稍后重试');
      return;
    }
    const dir_id = this.file_data[0].dir_id;
    this.router.navigate(['/codemig/migrate_project'], {
      queryParams: { task_id: this.task_id, dir_id: dir_id },
    });
  }

}
