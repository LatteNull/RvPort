import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CardModelComponent } from './card-model.component';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { PlxModule } from 'paletx';
import { provideRouter } from '@angular/router';
import { Router } from '@angular/router';

describe('CardModelComponent', () => {
  let component: CardModelComponent;
  let fixture: ComponentFixture<CardModelComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        CardModelComponent
      ],
      imports: [
        PlxModule.forRoot(),
      ],
      providers: [
        provideRouter([])
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    router = TestBed.inject(Router);
    fixture = TestBed.createComponent(CardModelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('测试创建应用', () => {
    expect(component).toBeTruthy();
  });

  it('测试按钮点击', () => {
    const navigateSpy = spyOn(router, 'navigate');
    component.logout();
    expect(navigateSpy).toHaveBeenCalledWith(['login']);
    component.clickM();
    expect(navigateSpy).toHaveBeenCalledWith(['/main/dataform/overview']);
  });

});
