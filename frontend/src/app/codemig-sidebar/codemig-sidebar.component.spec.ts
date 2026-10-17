import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CodemigSidebarComponent } from './codemig-sidebar.component';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { provideRouter } from '@angular/router';
import { Router } from '@angular/router';
import { PlxModule } from 'paletx';

describe('CodemigSidebarComponent', () => {
  let component: CodemigSidebarComponent;
  let fixture: ComponentFixture<CodemigSidebarComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        CodemigSidebarComponent,
      ],
      imports: [
        PlxModule.forRoot(),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideRouter([]),
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    router = TestBed.inject(Router);
    fixture = TestBed.createComponent(CodemigSidebarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('测试创建组件', () => {
    expect(component).toBeTruthy();
  });

  it('测试按钮点击', () => {
    const navigateSpy = spyOn(router, 'navigate');
    const node = { task_id: 123, isLeaf: true };
    component.click(node);
    expect(navigateSpy).toHaveBeenCalledWith(
      ['/codemig/task'],
      { queryParams: { task_id: 123 } }
    );
  });

  it('测试路由跳转', () => {
    spyOn(router, 'navigate');
    const operation = component.treeNodes[0].children[0].operations[0];
    operation.callback();
    expect(router.navigate).toHaveBeenCalledWith(['/codemig/sourcecodemig']);
  });

  it('测试按钮点击', () => {
    const navigateSpy = spyOn(router, 'navigate');
    const testNode = { task_id: '123', isLeaf: true };
    component.click(testNode);
    expect(navigateSpy).toHaveBeenCalledWith(['/codemig/task'], { queryParams: { task_id: '123' } });
  });

  it('测试按钮点击2', () => {
    const navigateSpy = spyOn(router, 'navigate');
    const testNode = { id: 'sourcecodemig' };
    component.click(testNode);
    expect(navigateSpy).toHaveBeenCalledWith(['/codemig/sourcecodemig']);
  });

  it('测试 updateTreeNodes 更改长度', () => {
    component.updateTreeNodes([[1, "name1"], [2, "name2"], [3, "name3"], [4, "name4"]], 3);
    expect(component.treeNodes[0].children[0].children.length).toBe(4);
    expect(component.treeNodes[0].children[0].children[0].label).toBe('name1');
    expect(component.treeNodes[0].children[0].children[0].task_id).toBe(1);
    expect(component.treeNodes[0].children[0].children[0].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[0].isNodeSelected).toBe(false);
    expect(component.treeNodes[0].children[0].children[1].label).toBe('name2');
    expect(component.treeNodes[0].children[0].children[1].task_id).toBe(2);
    expect(component.treeNodes[0].children[0].children[1].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[1].isNodeSelected).toBe(false);
    expect(component.treeNodes[0].children[0].children[2].label).toBe('name3');
    expect(component.treeNodes[0].children[0].children[2].task_id).toBe(3);
    expect(component.treeNodes[0].children[0].children[2].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[2].isNodeSelected).toBe(true);
    expect(component.treeNodes[0].children[0].children[3].label).toBe('name4');
    expect(component.treeNodes[0].children[0].children[3].task_id).toBe(4);
    expect(component.treeNodes[0].children[0].children[3].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[3].isNodeSelected).toBe(false);

    component.updateTreeNodes([[1, "name1"], [2, "name2"]], 2);
    expect(component.treeNodes[0].children[0].children.length).toBe(2);
    expect(component.treeNodes[0].children[0].children[0].label).toBe('name1');
    expect(component.treeNodes[0].children[0].children[0].task_id).toBe(1);
    expect(component.treeNodes[0].children[0].children[0].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[0].isNodeSelected).toBe(false);
    expect(component.treeNodes[0].children[0].children[1].label).toBe('name2');
    expect(component.treeNodes[0].children[0].children[1].task_id).toBe(2);
    expect(component.treeNodes[0].children[0].children[1].isLeaf).toBe(true);
    expect(component.treeNodes[0].children[0].children[1].isNodeSelected).toBe(true);
  });

});
