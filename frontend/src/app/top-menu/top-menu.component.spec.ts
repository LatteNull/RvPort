import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TopMenuComponent } from './top-menu.component';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { provideRouter } from '@angular/router';
import { Router } from '@angular/router';

describe('TopMenuComponent', () => {
  let component: TopMenuComponent;
  let fixture: ComponentFixture<TopMenuComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [TopMenuComponent],
      providers: [provideRouter([])],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    router = TestBed.inject(Router);
    fixture = TestBed.createComponent(TopMenuComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('创建应用', () => {
    expect(component).toBeTruthy();
  });

  it('测试按钮点击', () => {
    const navigateSpy = spyOn(router, 'navigate');
    component.goBack();
    expect(navigateSpy).toHaveBeenCalledWith(['cardmodel']);
    component.clickTitle();
    expect(navigateSpy).toHaveBeenCalledWith(['main']);
    component.logout();
    expect(navigateSpy).toHaveBeenCalledWith(['login']);
    component.goSettings();
    expect(navigateSpy).toHaveBeenCalledWith(['settings']);
  });
});
