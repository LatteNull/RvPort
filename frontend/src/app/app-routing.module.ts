import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LoginComponent } from './login/login.component';
import { CardModelComponent } from './card-model/card-model.component';
import { SettingsComponent } from './settings/settings.component';
import { UserManagementComponent } from "./user-management/user-management.component";
import { AgentManagementComponent } from "./agent-management/agent-management.component";
import { SystemSettingsComponent} from "./system-settings/system-settings.component";
import { LogManagementComponent } from "./log-management/log-management.component";
import { CodemigSidebarComponent } from './codemig-sidebar/codemig-sidebar.component';
import { CodemigGuideComponent } from './codemig-guide/codemig-guide.component';
import { PlatformOverviewComponent } from './platform-overview/platform-overview.component';
import { SourceCodeMigComponent } from './source-codemig/source-codemig.component';
import { CodemigTaskViewComponent } from './codemig-task-view/codemig-task-view.component';
import { CodemigFileChangeViewComponent } from './codemig-file-change-view/codemig-file-change-view.component';
import { CodemigFileSidebarComponent } from './codemig-file-sidebar/codemig-file-sidebar.component';
import { CodemigTaskDependenceViewComponent } from './codemig-task-dependence-view/codemig-task-dependence-view.component'
import { RoleRedirectGuard } from './guards/role-redirect.guard';
import { NetworkProxyConfigurationComponent } from './network-proxy-configuration/network-proxy-configuration.component'
import { SystemPanelComponent } from './system-panel/system-panel.component'

const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: 'settings', component: SettingsComponent, canActivate: [RoleRedirectGuard] },
  { path: 'login', component: LoginComponent },
  { path: 'cardmodel', component: CardModelComponent },
    {
      path: 'codemig', component: CodemigSidebarComponent, children: [
        {
          path: '',
          children: [
            { path: 'sourcecodemig', component: SourceCodeMigComponent },
            { path: 'task', component: CodemigTaskViewComponent, data: { reuse: false } },
            { path: 'dependence', component: CodemigTaskDependenceViewComponent, data: { reuse: false } },
          ]
        }
      ]
    },
    {
      path: 'codemig', component: CodemigFileSidebarComponent, children: [
        {
          path: '',
          children: [
            { path: 'migrate_project', loadChildren: () =>
                import('./codemig-project-migrate-view/codemig-project-migrate-view.module').then(
                  m => m.CodemigProjectMigrateViewModule
                ), data: { reuse: false } },
          ]
        }
      ]
    },
    { path: 'codemig/guide', component: CodemigGuideComponent, data: { reuse: false } },
    { path: 'platform/overview', component: PlatformOverviewComponent, data: { reuse: false } },
    {
      path: 'filechange',
      component: CodemigFileSidebarComponent,
      children: [
        {
          path: 'view',
          loadChildren: () =>
            import('./codemig-file-change-view/codemig-file-change-view.module').then(
              m => m.CodemigFileChangeViewModule
            )
        },
        {
          path: 'generate',
          loadChildren: () =>
            import('./codemig-file-generate/codemig-file-generate.module').then(
              m => m.CodemigFileGenerateModule
            )
        }
      ]
    },
    {
      path: 'filechange', component: CodemigFileSidebarComponent, children: [
        {
          path: '',
          children: [
            { path: 'view', component: CodemigFileChangeViewComponent },
          ]
        }
      ]
    },
    {
    path: 'settings', component: SettingsComponent, children: [
      {
        path: '',
        children: [
          { path: 'usermanagement', component:UserManagementComponent},
          { path: 'systemsettings', component:SystemSettingsComponent},
          { path: 'logmanagement', component:LogManagementComponent},
          { path: 'agentmanagement', component:AgentManagementComponent},
          { path: 'networkproxyconfiguration', component:NetworkProxyConfigurationComponent},
          { path: 'systempanel', component:SystemPanelComponent},
        ]
      }
    ]
  }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
