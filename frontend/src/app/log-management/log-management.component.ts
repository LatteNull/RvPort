import { Component, OnInit, ViewChild, Input } from '@angular/core';
import { PlxMessage, PlxModal, FieldType } from 'paletx';
import { HttpHeaders } from '@angular/common/http';
import { LogManagementApi } from '../api/log-management-api.service'

@Component({
  selector: 'app-log-management',
  templateUrl: './log-management.component.html',
  styleUrl: './log-management.component.css',
  standalone:false,
})
export class LogManagementComponent implements OnInit{
  @Input() size:any;
  public total: number = 0;
  public pageIndex = 1;
  public pageSizeSelections: number[] = [10, 20, 50, 100, 200];
  public maxPageIndex: any;
  public pageSize = 20;
  result: any;
  module: any;
  user_name: any;
  ip: any;
  customFilters: Array<any> = [];
  filterModule: Array<any> = [];
  filterResult: Array<any> = [];

  @ViewChild('plxTable') plxTable: any;
  showLoading=false;
  scroll:any={y: '330px'};
  data: Array<any> =[];
  formSetting:any;
  @ViewChild('content') content: any;
  modal:any;

  checkboxConfig = {filter: true};

  constructor(
    public plxMessage:PlxMessage,
    private logManagementApi: LogManagementApi,
    private modalService: PlxModal
  ) {

  }

  columns = [
    {
      key: 'user_name',
      title: '操作用户',
      show: true,
      width: '250px',
      class: 'first',
      filter: true,
      contentType: 'html',
    },
    {
      key: 'event',
      title: '操作名称',
      show: true,
      class: 'xx',
      width: '200px',
      showInDropdown: true
    },
    {
      key: 'module',
      title: '所属工具',
      width: '200px',
      show: true,
      class: 'xx',
      filterArray: this.filterModule,
    },
    {
      key: 'result',
      title: '操作结果',
      width: '200px',
      show: true,
      class: 'xx',
      filterArray: this.filterResult,
    },
    {
      key: 'ip',
      title: '操作主机IP',
      filter: true,
    },
    {
      key: 'time',
      title: '操作时间',
    },
    {
      key: 'detail',
      title: '操作详情',
    }
  ];

  ngOnInit(): void {
    this.getFilterList()
    this.getLogList()
  }

  filterInfoChange(event:any) {
    console.log('filterInfoChange', event);
    let no_result = true
    let no_module = true
    let no_username = true
    let no_ip = true
    if (event.selectionFilters){
      for (const filter of event.selectionFilters){
        if (filter.key == "result"){
          no_result = false
          this.result = filter.filters.map((item: { filterKey: any; }) => item.filterKey).join(',');
        }else if (filter.key == "module"){
          no_module = false
          this.module = filter.filters.map((item: { filterKey: any; }) => item.filterKey).join(',');
        }
      }
    }
    if (no_result){
      this.result = ""
    }
    if (no_module){
      this.module = ""
    }
    if (event.singleColFilters){
      for (const filter of event.singleColFilters){
        if (filter.key == "user_name"){
          no_username = false
          this.user_name = filter.filterKey
        }else if (filter.key == "ip"){
          no_ip = false
          this.ip = filter.filterKey
        }
      }
    }
    if (no_username){
      this.user_name = ""
    }
    if (no_ip){
      this.ip = ""
    }
    this.getLogList()
  }

  sortInfoChange(event:any) {
    console.log('sortInfoChange', event);
  }

  public onPageChange(pageInfo:any) {
    this.maxPageIndex = this.getMaxPageIndex(pageInfo['pageSize']);
    this.pageIndex = (pageInfo['pageIndex'] > this.maxPageIndex) ? this.maxPageIndex : pageInfo['pageIndex'];
    this.pageSize = pageInfo['pageSize']
    this.getLogList()
  }

  getFilterList(){
    this.logManagementApi.getFilter().subscribe({
      next: (response: any) => {
        console.log('res', response)
        if (response['code'] === 0) {
          for (const module of response.data.modules){
            this.filterModule.push({
              filterKey: module,
              checked: false
            })
          }
          for (const result of response.data.result){
            this.filterResult.push({
              filterKey: result,
              checked: false
            })
          }
          console.log(this.filterModule, this.filterResult)
        }
      },
    })
  }

  getLogList(){
    const body: any = {
      page:this.pageIndex,
      per_page:this.pageSize,
      filter: {
        user_name: this.user_name,
        ip: this.ip,
        result: this.result,
        module: this.module,
      }
    };
    this.logManagementApi.getLogMangerList(body).subscribe({
      next: (response: any) => {
        console.log('res', response)
        if (response['code'] === 0) {
          this.data = []
          for (const sub_data of response.msg.operation_log_list) {
            this.addData(sub_data);
          }
          this.total = response.msg.total_log_count;
          this.maxPageIndex = this.getMaxPageIndex(this.pageSize);
        }
      },
    });
  }

  private getMaxPageIndex(currPageSize: number): number {
    return Math.ceil(this.total / currPageSize);
  }

  addData(value: any) {
    this.data = this.data.concat([{
      user_name:value.user_name,
      event:value.event,
      module:value.module,
      result:value.result,
      ip:value.ip,
      time:value.time,
      detail:value.detail,
    }])
  }
  private saveFile(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }

  download_log(){
    const headers = new HttpHeaders({
      "Content-Type": 'application/json',
    });
    this.logManagementApi.getLogMangerCsv().subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          console.log("downloadresponse1",response)
          const requestbody ={
            csvfile:response.data
          }
          console.log("downloadrequestbody",requestbody)
          this.logManagementApi.downloadLogManager(requestbody, {
            headers: headers,
            responseType: 'blob'
          }).subscribe({
            next: (res: any) => {
              this.saveFile(res, response.data);
              this.plxMessage.success("下载成功", "");
              this.getLogList();
            },
            error: (err: any) => {
              console.error("下载失败", err);
              this.plxMessage.error("下载失败", err.message || '未知错误');
            }
          });
        }
      },
    });
  }

  submit(){
    const isValid = this.formSetting.validateFields();
    if (isValid) {
      console.log('form value:', this.formSetting.formObject.value);
    }
    let value = this.formSetting.formObject.value;
    const body:Record<string, any> = {
    };
    for (const key in value) {
      if (value[key] !== undefined && value[key] !== null && value[key] !== "") {
          body[key] = value[key];
      }
    }
    body['page'] = this.pageIndex;
    body['per_page'] = this.pageSize;
    console.log("body",body)
    this.logManagementApi.getLogMangerList(body).subscribe({
      next: (response: any) => {
        if (response['code'] === 0) {
          this.data = [];
          for (const sub_data of response.msg.operation_log_list) {
            this.addData(sub_data);
          }
          this.plxMessage.success("查询成功", "");
          if (this.modal) {
            this.modal.close();
          }
        } else {
          this.plxMessage.error("查询失败", response['msg'] || '未知错误');
        }
      },
    });
  }

  cancel(){
    this.modal.close()
  }

  initFormSetting() {
    return {
      isShowHeader: false,
      isGroup: false,
      srcObj:{
        page:1,
        per_page:20,
      },
      fieldWidth: '800px',
      labelWidth: '180px',
      fieldSet: [
        {
          fields: [
            {
              name: 'user_name',
              label: '操作用户',
              type: FieldType.STRING,
              tail: `${'无输入默认全匹配'}</span>`,
            },
            {
              name: 'result',
              label: '操作结果',
              type: FieldType.STRING,
              tail: `${'无输入默认全匹配'}</span>`,
            },
            {
              name: 'ip',
              label: '操作主机IP',
              type: FieldType.STRING,
              tail: `${'无输入默认全匹配'}</span>`,
            },
          ]
        },
      ]
    };
  }
}

