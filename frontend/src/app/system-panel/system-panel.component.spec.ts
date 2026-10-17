import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SystemPanelComponent } from './system-panel.component';

describe('SystemPanelComponent', () => {
  let component: SystemPanelComponent;
  let fixture: ComponentFixture<SystemPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SystemPanelComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SystemPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
