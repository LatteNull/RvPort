import { Component, ChangeDetectorRef, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CodemigTaskDependenceButtonComponent } from '../codemig-task-dependence-button/codemig-task-dependence-button.component'
import { CodeMigApi } from '../api/codemig-api.service'
interface SummaryItem {
  type: string;      // 建议类型
  issues: number;    // 问题数量
  affectedLines: number | null; // 影响行数，可能为空
}

@Component({
  selector: 'app-codemig-task-dependence-view',
  templateUrl: './codemig-task-dependence-view.component.html',
  styleUrl: './codemig-task-dependence-view.component.css',
  standalone: false,
})
export class CodemigTaskDependenceViewComponent {
  @ViewChild('plxTable') plxTable: any;
  task_id: any;
  dependence_id: any;
  user_name: any

  dependence_name: any;
  version: any;

  created_time: any;
  summary_data: Array<SummaryItem> = [];

  showLoading = false;

  file_data: Array<any> = [];
  file_columns: Array<any> = [];

  software_data: Array<any> =[];
  software_columns: Array<any> = [];

  missing_file_data: Array<any> = []
  missing_file_columns: Array<any> = []

  tabItems: Array<any> = [];
  constructor(
    private codeMigApi: CodeMigApi,
    private route: ActivatedRoute,
    private cdr: ChangeDetectorRef) {
      this.user_name = localStorage.getItem('user_name');
      this.route.queryParams.subscribe(params => {
        this.task_id = params["task_id"]
        this.dependence_id = params["dependence_id"]
      });
  }

  ngOnInit() {
    this.InitTab()
    this.queryData();
  }

  InitTab(){
    this.tabItems.push({activeId: '源码扫描信息', title: '源码扫描信息', data: [], columns: this.createFileColumns(), is_obtain: false})
    this.tabItems.push({activeId: '软件包扫描信息', title: '软件包扫描信息', data: [], columns: this.createSoftWareColumns(), is_obtain: false})
    this.tabItems.push({activeId: '缺失文件信息', title: '缺失文件信息', data: [], columns: this.createMissingFileColumns(), is_obtain: false})
  }

  queryData(){
    const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dependence_id': this.dependence_id };
    this.codeMigApi.getTaskDependenceFiles(body).subscribe({
      next: (response: any) => {
        if (response.code == 0){
          if (response.code == 0){
            const my_data = response.data;
            this.created_time = my_data.created_time;
            this.dependence_name = my_data.dependence_name
            this.version = my_data.version
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
          }

        }
      },
    });
  }

  sharedColumns(){
    return [
      {
        key: 'file_index',
        title: '序号',
        width: '100px',
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
      },
      {
        key: 'file_name',
        title: '文件名',
        width: '200px',
        show: true,
      }
    ]
  }

  createFileColumns() {
    return [
      ...this.sharedColumns(),
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
        component: CodemigTaskDependenceButtonComponent,
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
        key: 'file_path',
        title: '缺失RV文件/现有架构文件',
        width: '800px',
        show: true,
      },
      {
        key: 'operation',
        title: '操作',
        show: true,
        contentType: 'component',
        component: CodemigTaskDependenceButtonComponent,
      },
      {
        key: 'is_missing',
        show: false,
      },
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
      is_missing: false,
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
      file_name: missing_file[4],
      file_path: missing_file[5],
      is_missing: true,
      children: [],
    }]);
  }

  tabChange(event: any){
    if (event.nextId == '软件包扫描信息' && !this.tabItems[1].is_obtain){
      const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dependence_id': this.dependence_id };
      this.codeMigApi.getTaskDependencedeSoftware(body).subscribe({
        next: (response: any) => {
          if (response.code == 0){
            const my_data = response.data;
            for (const software of my_data.dependence_software_rows) {
              this.addSoftware(software);
            }
            this.tabItems[1].data = this.software_data
            this.tabItems[1].is_obtain = true
          }
        },
      });
    }else if (event.nextId == '缺失文件信息' && !this.tabItems[2].is_obtain){
      const body = { 'user_name': this.user_name, 'task_id': this.task_id, 'dependence_id': this.dependence_id  };
      this.codeMigApi.getTaskDependenceMissingFiles(body).subscribe({
        next: (response: any) => {
          console.log(response)
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
    }
  }

  getChilrednNode(row: any, data: any){
    let children:any = []
    for (const key in data){
      let obj: any = {
        file_index:  Number(key) + 1,
        file_id:data[key][0],
        file_name: data[key][1].split('/').pop(),
        'file_path': data[key][1],
        "isLeaf": true,
        "parent": row.file_index
      }
      children.push(obj)
    }
    return children
  }

  onRowExpandCollapse(event: any){
    console.log(event['row'])
    if (event['row'].isExpanded) { // 如果是展开事件
      this.showLoading = true
      const body = { 'file_id': event['row'].file_id, 'dependence_id': this.dependence_id };
      this.codeMigApi.getTaskDependenceExistingArch(body).subscribe({
        next: (response: any) => {
          event['row']['children'] = this.getChilrednNode(event['row'], response.data)
          this.showLoading = false;
          this.plxTable.dataChanged();
        },
      });
    }
  }
}
