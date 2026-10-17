import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TopMenuComponent } from '../top-menu/top-menu.component';
import { SettingsComponent } from './settings.component';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PlxModule } from 'paletx';
import { RouterModule } from '@angular/router';
import { ActivatedRoute } from '@angular/router';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let fixture: ComponentFixture<SettingsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        TopMenuComponent,
        SettingsComponent,
      ],
      imports: [
        RouterModule,
        PlxModule.forRoot(),
      ],
      providers: [
        FormsModule,{
        provide: ActivatedRoute,
          useValue: {
            snapshot: {
              url: [{ path: 'testTask' }],
            },
          },
        },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    fixture = TestBed.createComponent(SettingsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('测试创建应用', () => {
    expect(component).toBeTruthy();
  });

  it('测试初始化', () => {
    expect(component.menuConfig).toBeDefined();
    expect(component.menuConfig.toggleBtn.text).toBe('收起');
    expect(component.menuConfig.toggleBtn.collapsedText).toBe('侧边栏展开');
    expect(component.menuConfig.menusData.length).toBe(1);
    expect(component.menuConfig.menusData[0].name).toBe('通用设置');
    expect(component.menuConfig.menusData[0].children.length).toBe(1);
    expect(component.menuConfig.menusData[0].children[0].name).toBe('日志管理');
    expect(component.menuConfig.menusData[0].children[0].href).toBe('/settings/logmanagement');
  });

  it('测试点击menuClick', () => {
    spyOn(component, 'menuClick');
    component.menuClick({});
    expect(component.menuClick).toHaveBeenCalled();
  });

  it('测试点击collapseBtnClick', () => {
    spyOn(component, 'collapseBtnClick');
    component.collapseBtnClick({});
    expect(component.collapseBtnClick).toHaveBeenCalled();
  });

});
