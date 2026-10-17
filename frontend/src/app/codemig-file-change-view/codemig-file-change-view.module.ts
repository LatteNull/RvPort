import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CodemigFileChangeViewComponent } from './codemig-file-change-view.component';
import { RouterModule } from '@angular/router';

@NgModule({
  imports: [
    CommonModule,
    RouterModule.forChild([
      { path: '', component: CodemigFileChangeViewComponent }
    ]),
  ]
})
export class CodemigFileChangeViewModule {}