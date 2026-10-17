import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlxModule } from 'paletx';
import { MarkdownModule } from 'ngx-markdown';
import { MonacoEditorModule } from 'ngx-monaco-editor-v2';
import { CodemigProjectMigrateViewComponent } from './codemig-project-migrate-view.component';
import { RouterModule } from '@angular/router';

@NgModule({
  declarations: [
    CodemigProjectMigrateViewComponent,
  ],
  imports: [
    CommonModule,
    FormsModule,
    PlxModule,
    MarkdownModule.forChild(),
    MonacoEditorModule,
    RouterModule.forChild([
      { path: '', component: CodemigProjectMigrateViewComponent }
    ]),
  ]
})
export class CodemigProjectMigrateViewModule {}
