import { Component } from '@angular/core';
import { PlxTableService } from 'paletx';
import { Router, ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-codemig-task-dependence-button',
  templateUrl: './codemig-task-dependence-button.component.html',
  styleUrl: './codemig-task-dependence-button.component.css',
  standalone: false,
})
export class CodemigTaskDependenceButtonComponent {
  rowData: any;
  dependence_id: any;
  helpText: string = '';
  constructor(
    private plxTableService: PlxTableService,
    private router: Router,
    private route: ActivatedRoute,) {
    this.rowData = this.plxTableService.getPositionInfo().currentRowData;
    if(this.rowData.isLeaf){
      this.helpText = '';
    }
    else{
      if(this.rowData.is_missing){
        this.helpText = '生成文件';
      }
      else{
        this.helpText = '查看建议源码';
      }
    }
  }

  viewDependenceFile() {
    this.route.queryParams.subscribe((params: any) => {
      this.dependence_id = params["dependence_id"]
    });
    const params = {
      task_id: this.rowData.task_id,
      dir_id: this.rowData.dir_id,
      file_id: this.rowData.file_id,
      dependence_id: this.dependence_id,
    };
    if (this.rowData.is_missing){
      this.router.navigate(['/filechange/generate'], { queryParams: params });
    }
    else{
      this.router.navigate(['/filechange/view'], { queryParams: params });
    }
  }
}
