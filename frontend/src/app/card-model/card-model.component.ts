import { Component, ViewChild, TemplateRef, OnInit } from '@angular/core';
import { Router} from '@angular/router'
import { PluginManagerApi } from '../api/plugin-manager-api.service'
@Component({
  selector: 'card-model',
  templateUrl: 'card-model.component.html',
  styleUrl: './card-model.component.css',
  standalone: false,
})
export class CardModelComponent implements OnInit {
  myTypeMap = new Map<string, any>();

  constructor(
    private router: Router,
    private pluginManagerApi: PluginManagerApi
    ) {
  }
  card:object={
    titleshow: true,
    operatingshow: false,
    contentshow: true,
    footshow: false
  }
  public tools: any;
  @ViewChild('dropContent') dropContent!: TemplateRef<any>;

  ngOnInit() {
    this.tools = [{
      icon: 'plx-ico-more-16',
      dropdownContent: this.dropContent
    }];
    this.pluginManagerApi.getPluginList().subscribe({
      next: (res: any) => {
        if (res.code == 0){
          const data = res.data
          for (const i in data){
            this.myTypeMap.set(data[i].type, data[i].isOK)
          }
        } 
      }
    })
  }

  clickM() {
    if (this.myTypeMap.get('codemig') != 'OK') {
      return;
    }
    this.router.navigate(['/codemig/sourcecodemig']);
  }

  openSourceLicense() {
    window.open('assets/open-source-licenses.html', '_blank');
  }
}
