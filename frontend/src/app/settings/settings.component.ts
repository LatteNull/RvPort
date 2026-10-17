import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router, ActivatedRoute, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { Subscription } from 'rxjs';
import { PluginManagerApi } from '../api/plugin-manager-api.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
  standalone: false,
})
export class SettingsComponent implements OnInit, OnDestroy {
  CurrentRole: any;
  private routerSubscription?: Subscription;

  // 已装插件映射：type -> 是否已装(isOK==='OK')。
  // 设置分组按插件显示：framework->通用设置, codemig->代码迁移。
  // 用 pluginKnown 标志区分：未加载/接口异常时默认全部显示，避免设置页空白；
  // 加载成功后正向判断（只有 isOK==='OK' 才显示），absent(未装) 与 notOK 都隐藏。
  private installedPlugins: Map<string, boolean> = new Map();
  private pluginKnown = false;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private pluginManagerApi: PluginManagerApi,
  ) {
    this.CurrentRole = localStorage.getItem('userRole');
  }

  menuConfig: any;

  ngOnInit(): void {
    this.menuConfig = this.getmeunConfig();

    // 拉取已装插件列表，按结果重建菜单（过滤未装插件对应的分组）
    this.pluginManagerApi.getPluginList().subscribe({
      next: (res: any) => {
        if (res?.code === 0 && Array.isArray(res.data)) {
          for (const item of res.data) {
            this.installedPlugins.set(item.type, item.isOK === 'OK');
          }
          this.pluginKnown = true;
          this.menuConfig = this.getmeunConfig();
        }
      },
      error: () => {
        // 接口异常时保持默认（全部显示），不隐藏设置项
      }
    });

    this.routerSubscription = this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe(() => {
        this.menuConfig = this.getmeunConfig();
      });
  }

  ngOnDestroy(): void {
    if (this.routerSubscription) {
      this.routerSubscription.unsubscribe();
    }
  }

  private isPluginInstalled(type: string): boolean {
    // 插件列表未成功获取（初始加载/接口异常）时默认显示，避免设置页空白
    if (!this.pluginKnown) {
      return true;
    }
    // 正向判断：只有列表里 isOK==='OK' 的才显示；未装(absent)/notOK 都隐藏
    return this.installedPlugins.get(type) === true;
  }

  getCurrentPath(): string {
    return this.router.url;
  }

  getmeunConfig() {
    const currentPath = this.getCurrentPath();

    const setSelected = (menuItem: any) => ({
      ...menuItem,
      selected: menuItem.href === currentPath
    });

    // 通用：所有部署均需要的设置项（framework 插件）
    const commonMenuItems = [
      { name: '系统设置', href: '/settings/systemsettings' },
      { name: '日志管理', href: '/settings/logmanagement' },
      { name: '用户管理', href: '/settings/usermanagement' },
    ];

    // 系统面板：依赖 codemig 插件
    if (this.isPluginInstalled('codemig')) {
      commonMenuItems.push({ name: '系统面板', href: '/settings/systempanel' });
    }

    // 代码迁移工具独有（codemig 插件）
    const codemigMenuItems = [
      { name: 'API key管理', href: '/settings/agentmanagement' },
      { name: '网络代理配置', href: '/settings/networkproxyconfiguration' },
    ];

    // 普通用户：按相同分组展示其有权限的菜单项
    const userCommonMenuItems = [
      { name: '日志管理', href: '/settings/logmanagement' },
    ];
    const userCodemigMenuItems = [
      { name: 'API key管理', href: '/settings/agentmanagement' },
      { name: '网络代理配置', href: '/settings/networkproxyconfiguration' },
    ];
    // 按已装插件拼装分组：framework->通用设置, codemig->代码迁移
    // 未装对应插件的分组不显示。分组默认展开（matchRouter:true）。
    const buildMenusData = (common: any[], codemig: any[]) => {
      const menusData: any[] = [];
      if (this.isPluginInstalled('framework')) {
        menusData.push({ name: '通用设置', matchRouter: true, children: common.map(setSelected) });
      }
      if (this.isPluginInstalled('codemig')) {
        menusData.push({ name: '代码迁移', matchRouter: true, children: codemig.map(setSelected) });
      }
      return menusData;
    };

    if (this.CurrentRole === 'admin') {
      // admin：保留分组目录树结构，含全部菜单项
      return {
        toggleBtn: {
          text: '收起',
          collapsedText: '侧边栏展开'
        },
        menusData: buildMenusData(commonMenuItems, codemigMenuItems)
      };
    }

    // 普通用户：按相同分组展示其有权限的菜单项
    return {
      toggleBtn: {
        text: '收起',
        collapsedText: '侧边栏展开'
      },
      menusData: buildMenusData(userCommonMenuItems, userCodemigMenuItems)
    };
  }

  menuClick(event: any) {
    if (event.menu.href) {
      this.router.navigate([event.menu.href]);
    }
  }

  collapseBtnClick(event: any) {
    console.log(event);
  }
}
