import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { PlxModule } from 'paletx';
import { MonacoEditorModule } from 'ngx-monaco-editor-v2';
import { provideHttpClient, withInterceptorsFromDi, HTTP_INTERCEPTORS } from '@angular/common/http';
import { AppRoutingModule } from './app-routing.module';
import { RouteReuseStrategy } from '@angular/router';
import { CustomReuseStrategy } from './custom-reuse-strategy';
import { AppComponent } from './app.component';
import { LoginComponent } from './login/login.component';
import { CardModelComponent } from './card-model/card-model.component';
import { TopMenuComponent } from './top-menu/top-menu.component';
import { SettingsComponent } from './settings/settings.component';
import { LocationStrategy, HashLocationStrategy, CommonModule } from '@angular/common';

import { NgxEchartsModule } from 'ngx-echarts';
import * as echarts from 'echarts';

import { HttpSecurityInterceptorService } from './interceptors/http-security-interceptor.service';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { UserManagementComponent } from "./user-management/user-management.component";
import { SystemSettingsComponent} from "./system-settings/system-settings.component";
import { LogManagementComponent} from "./log-management/log-management.component";
import { AgentManagementComponent} from "./agent-management/agent-management.component";
import { ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { UserModifyComponent } from "./user-modify/user-modify.component"
import { UserResetComponent } from './user-reset/user-reset.component';
import { CodemigSidebarComponent } from './codemig-sidebar/codemig-sidebar.component';
import { CodemigGuideComponent } from './codemig-guide/codemig-guide.component';
import { PlatformOverviewComponent } from './platform-overview/platform-overview.component';
import { SourceCodeMigComponent } from './source-codemig/source-codemig.component';
import { CodemigTaskViewComponent } from './codemig-task-view/codemig-task-view.component';
import { CodemigTaskFileViewComponent } from './codemig-task-file-view/codemig-task-file-view.component';
import { CodemigFileChangeViewComponent } from './codemig-file-change-view/codemig-file-change-view.component';
import { CodemigFileGenerateComponent } from './codemig-file-generate/codemig-file-generate.component';
import { CodemigFileSidebarComponent } from './codemig-file-sidebar/codemig-file-sidebar.component';
import { MarkdownModule } from 'ngx-markdown';
import { CodemigTaskDependenceButtonComponent } from './codemig-task-dependence-button/codemig-task-dependence-button.component'
import { CodemigTaskDependenceViewComponent } from './codemig-task-dependence-view/codemig-task-dependence-view.component'
import { NetworkProxyConfigurationComponent } from './network-proxy-configuration/network-proxy-configuration.component';
import { SystemPanelComponent } from './system-panel/system-panel.component';

@NgModule({
  declarations: [
    AppComponent,
    LoginComponent,
    CardModelComponent,
    TopMenuComponent,
    SettingsComponent,

    UserManagementComponent,
    SystemSettingsComponent,
    LogManagementComponent,
    AgentManagementComponent,
    UserModifyComponent,
    UserResetComponent,
    CodemigSidebarComponent,
    CodemigGuideComponent,
    PlatformOverviewComponent,
    SourceCodeMigComponent,
    CodemigTaskViewComponent,
    CodemigTaskFileViewComponent,
    CodemigFileChangeViewComponent,
    CodemigFileGenerateComponent,
    CodemigFileSidebarComponent,

    CodemigTaskDependenceButtonComponent,
    CodemigTaskDependenceViewComponent,
    NetworkProxyConfigurationComponent,
    SystemPanelComponent,
  ],
  imports: [
    AppRoutingModule,
    BrowserModule,
    FormsModule,
    PlxModule.forRoot(),
    MonacoEditorModule.forRoot(),
    CommonModule,
    NgxEchartsModule.forRoot({ echarts }),
    BrowserAnimationsModule,

    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MarkdownModule.forRoot(),
  ],
  providers: [
    provideHttpClient(withInterceptorsFromDi()),
    {
      provide: HTTP_INTERCEPTORS,
      useClass: HttpSecurityInterceptorService,
      multi: true,
    },
    {
      provide: LocationStrategy,
      useClass: HashLocationStrategy,
    },
    {
      provide: RouteReuseStrategy,
      useClass: CustomReuseStrategy
    }
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
