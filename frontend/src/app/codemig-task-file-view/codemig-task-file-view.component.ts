import { Component, ViewEncapsulation } from '@angular/core';
import { PlxTableService } from 'paletx';
import { Router } from '@angular/router';

@Component({
  selector: 'app-codemig-task-file-view',
  templateUrl: './codemig-task-file-view.component.html',
  styleUrl: './codemig-task-file-view.component.css',
  standalone: false,
  encapsulation: ViewEncapsulation.None,
})
export class CodemigTaskFileViewComponent {

  rowData: any;
  helpText: string = '';
  constructor(
    private plxTableService: PlxTableService,
    private router: Router) {
    this.rowData = this.plxTableService.getPositionInfo().currentRowData;
    if (this.rowData.isLeaf){
      this.helpText = '';
    }
    else{
      if (this.rowData.is_missing == 'missing'){
        this.helpText = '生成文件';
      }
      else if (this.rowData.is_missing == 'file'){
        this.helpText = '查看建议源码';
      }
    }
  }

  viewFile() {
    const params = {
      task_id: this.rowData.task_id,
      dir_id: this.rowData.dir_id,
      file_id: this.rowData.file_id,
    };
    if (this.rowData.is_missing == 'missing'){
      this.router.navigate(['/filechange/generate'], { queryParams: params });
    }
    else if (this.rowData.is_missing == 'file'){
      this.router.navigate(['/filechange/view'], { queryParams: params });
    }
  }

}
