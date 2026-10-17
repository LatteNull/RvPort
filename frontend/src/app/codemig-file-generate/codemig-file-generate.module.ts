import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CodemigFileGenerateComponent } from './codemig-file-generate.component';
import { RouterModule } from '@angular/router';

@NgModule({
  imports: [
    CommonModule,
    RouterModule.forChild([
      { path: '', component: CodemigFileGenerateComponent }
    ]),
  ]
})
export class CodemigFileGenerateModule {}
