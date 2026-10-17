import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CodemigTaskDependenceViewComponent } from './codemig-task-dependence-view.component';

describe('CodemigTaskDependenceViewComponent', () => {
  let component: CodemigTaskDependenceViewComponent;
  let fixture: ComponentFixture<CodemigTaskDependenceViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CodemigTaskDependenceViewComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CodemigTaskDependenceViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
