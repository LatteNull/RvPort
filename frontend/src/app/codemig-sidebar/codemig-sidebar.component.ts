import { Component, ViewChild } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { interval, Subscription } from 'rxjs';
import { environment } from '../environment/environment';
import { PlxMessage, PlxModal } from 'paletx';
import { CodeMigApi } from '../api/codemig-api.service'

@Component({
  selector: 'app-codemig-sidebar',
  templateUrl: './codemig-sidebar.component.html',
  styleUrl: './codemig-sidebar.component.css',
  standalone: false,
})
export class CodemigSidebarComponent {
  private subscription!: Subscription;
  @ViewChild('tree') tree: any;
  user_name: any;
  deleteModal:any;
  deleteNode:any;
  @ViewChild('content') public content:any;

  searchOptions = {
    show: true,
    ignoreCase: true,
  };

  task_id:any;
  dependence_id: any;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private plxMessage: PlxMessage,
    private modalService: PlxModal,
    private codeMigApi: CodeMigApi,
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  ngOnInit(): void {
    this.refreshData();
    this.route.queryParams.subscribe((params: any) => {
      this.task_id = Number(params['task_id']);
      this.dependence_id = Number(params['dependence_id'])
      this.refreshData();
      if (environment.refreshSidebar && !this.subscription) {
        this.subscription = interval(2000).subscribe(() => {
          this.refreshData();
        });
      }
    });
  }

  ngOnDestroy(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  refreshData(): void {
    if (this.tree?.searchKey) return;

    const request_body = { user_name: this.user_name };
    this.codeMigApi.getTaskList(request_body).subscribe({
        next: (response: any) => {
          this.updateTreeNodes(response.data);
          this.tree.dataChanged();
        },
      });
  }

  updateTreeNodes(data: any) {
    this.updateTreeNode(this.treeNodes[0], data);
  }

  showDeleteModal(node:any){
    this.deleteNode = node
    this.deleteModal = this.modalService.open(this.content, {size: 'xs'});
  }

  deleteclick(node:any){
    let rootLabel = node.parent.label
    let judge = false
    const request_body = {
      task_id: node.task_id,
      task_name: node.label,
      user_name: this.user_name
    };
    this.route.queryParams.subscribe(params => {
      if (params["task_id"] == node.task_id) {
        judge = true
      }
    });
    this.codeMigApi.deleteTask(request_body).subscribe({
        next: (response: any) => {
          console.log("delete",response)
          if (response.code == 0 && response.msg == 'ok'){
            this.plxMessage.success("任务删除成功", "")
            // 任务删除后回到源码迁移首页
            this.router.navigate(["/codemig/sourcecodemig"]);
            this.tree.doLocation(rootLabel, true);
            this.tree = this.tree;
            if (judge){
              this.router.navigate(["/codemig/sourcecodemig"])
            }
            this.deleteModal.close();
            this.tree.dataChanged();
            this.refreshData();
          }
        },
        error: (errorResponse: any) => {
          console.log('Error: ', errorResponse);
        },
      });
  }

  updateTaskFieldIfNeeded(child: any, data: any){
    if (child["label"] != data[1]) {
      child["label"] = data[1];
    }
    if (child["task_id"] != data[0]) {
      child["task_id"] = data[0];
    }
    if (child["isLeaf"] != (data[2] == 0)){
      child["isLeaf"] = (data[2] == 0)
    }
    child['isNodeSelected'] = (!this.dependence_id && this.task_id == data[0]),
    child["operations"] = [{
      icon: 'plx-ico-delete-16',
      callback:() => this.showDeleteModal(child),
      tooltip: '删除'
    }]
  }

  updateTreeNode(treeNode: any, data: any) {
    treeNode["children"] ||= [];
    let children = treeNode.children;
    for (let i = 0; i < data.length; ++i) {
      if (i < children.length) {
        this.updateTaskFieldIfNeeded(children[i], data[i]);
        if (data[i][2] == 1){
          this.updateSubTreeNode(children[i], data[i])
        }
      }else{
        children.push({
          label: data[i][1],
          task_id: data[i][0],
          isLeaf: data[i][2] == 0,
          isNodeSelected: (!this.dependence_id && this.task_id == data[i][0]),
          "operations" : [{
            icon: 'plx-ico-delete-16',
            callback:() => this.showDeleteModal(children[i]),
            tooltip: '删除'
          }]
        });
        if (data[i][2] == 1){
          this.updateSubTreeNode(children[i], data[i])
        }
      }
    }
    children.length = data.length;
  }

  updateSubTreeNode(treeNode: any, data: any){
    treeNode.children = [];
    let children = treeNode.children;
    for (let i = 0; i < data[3].length; ++i){
      children.push({
        label:  `${data[3][i][1]}_${data[3][i][2]}`,
        task_id: data[0],
        dependence_id: data[3][i][0],
        isNodeSelected: (this.dependence_id == data[3][i][0] && this.task_id == data[0]),
        isLeaf: true,
      });
    }
  }


  click(node: any) {
    if (node.parent == undefined) {
      this.router.navigate(['/codemig/sourcecodemig']);
      return
    }
    // 判断节点层级
    const isLevel2 = node.parent.parent == undefined;  // 二级节点
    if (isLevel2) {
      this.router.navigate(['/codemig/task'], {
        queryParams: { task_id: node.task_id },
      });
    }else{
      this.router.navigate(['/codemig/dependence'], {
        queryParams: { task_id: node.task_id, dependence_id: node.dependence_id},
      });
    }
  }

  treeNodes: any[] = [
    {
      label: '源码迁移',
      id: 'sourcecodemig',
      isExpanded: true,
      operations: [
        {
          icon: 'plx-ico-add-16',
          callback: () => {
            this.router.navigate(['/codemig/sourcecodemig']);
          },
          tooltip: '添加',
        },
      ],
    },
  ];
}
