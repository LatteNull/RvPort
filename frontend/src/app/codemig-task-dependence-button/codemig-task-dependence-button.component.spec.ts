import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CodemigTaskDependenceButtonComponent } from './codemig-task-dependence-button.component';

describe('CodemigTaskDependenceButtonComponent', () => {
  let component: CodemigTaskDependenceButtonComponent;
  let fixture: ComponentFixture<CodemigTaskDependenceButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CodemigTaskDependenceButtonComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CodemigTaskDependenceButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
