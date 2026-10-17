import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import {
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';
import {
  provideHttpClientTesting,
  HttpTestingController,
} from '@angular/common/http/testing';
import { CodemigFileSidebarComponent } from './codemig-file-sidebar.component';
import { provideRouter, ActivatedRoute } from '@angular/router';
import { PlxModule } from 'paletx';
import { Router } from '@angular/router';
import { of } from 'rxjs';

describe('CodemigFileSidebarComponent', () => {
  let component: CodemigFileSidebarComponent;
  let fixture: ComponentFixture<CodemigFileSidebarComponent>;
  let httpMock: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CodemigFileSidebarComponent],
      imports: [PlxModule.forRoot()],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              url: [{ path: 'testTask' }],
            },
            queryParams: of({ task_id: '123', dir_id: '456', file_id: '789' }),
          },
        },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();

    router = TestBed.inject(Router);
    fixture = TestBed.createComponent(CodemigFileSidebarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    httpMock = TestBed.inject(HttpTestingController);
    httpMock.expectOne('/action/plugin/codemig/task/filetree');
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('测试创建组件', () => {
    expect(component).toBeTruthy();
  });

  it('测试按钮点击成功', () => {
    const navigateSpy = spyOn(router, 'navigate');
    const node = {
      task_id: '123',
      dir_id: '456',
      file_id: '789',
      isLeaf: true,
    };
    component.click(node);
    expect(navigateSpy).toHaveBeenCalledWith(['/filechange/view'], {
      queryParams: { task_id: '123', dir_id: '456', file_id: '789' },
    });
  });

  it('测试按钮点击失败', () => {
    const navigateSpy = spyOn(router, 'navigate');
    const invalidNodes = [
      {},
      { task_id: '1' },
      { task_id: '1', dir_id: '2' },
      { task_id: '1', dir_id: '2', file_id: '3', isLeaf: false },
    ];
    for (const node of invalidNodes) {
      component.click(node);
    }
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('测试 processTreeLeaf 初始为空', () => {
    const treeNode = {} as { children: any[] };
    const treeLeaf = [
      [123, 456, 789, 'Leaf A'],
      [2, 20, 200, 'Leaf B'],
    ];

    component.processTreeLeaf(treeNode, treeLeaf);

    expect(treeNode['children'].length).toBe(2);
    expect(treeNode['children'][0]).toEqual({
      label: 'Leaf A',
      task_id: 123,
      dir_id: 456,
      file_id: 789,
      isLeaf: true,
      isNodeSelected: true,
    });
    expect(treeNode['children'][1]).toEqual({
      label: 'Leaf B',
      task_id: 2,
      dir_id: 20,
      file_id: 200,
      isLeaf: true,
      isNodeSelected: false,
    });
  });

  it('测试 processTreeLeaf 有初始值', () => {
    const treeNode = {
      children: [
        {
          label: 'Old Label',
          task_id: 0,
          dir_id: 0,
          file_id: 0,
          isLeaf: true,
          isNodeSelected: true,
        },
      ],
    };
    const treeLeaf = [[9, 99, 999, 'New Label']];

    component.processTreeLeaf(treeNode, treeLeaf);

    expect(treeNode['children'].length).toBe(1);
    expect(treeNode['children'][0]).toEqual({
      label: 'New Label',
      task_id: 9,
      dir_id: 99,
      file_id: 999,
      isLeaf: true,
      isNodeSelected: false,
    });
  });

  it('测试 processTreeLeaf 长度不同', () => {
    const treeNode = {
      children: [
        { label: 'Leaf 1', task_id: 1, dir_id: 10, file_id: 100, isLeaf: true },
        { label: 'Leaf 2', task_id: 2, dir_id: 20, file_id: 200, isLeaf: true },
      ],
    };
    const treeLeaf = [
      [1, 10, 100, 'Leaf 1'], // unchanged
    ];

    component.processTreeLeaf(treeNode, treeLeaf);

    expect(treeNode['children'].length).toBe(1);
    expect(treeNode['children'][0].label).toBe('Leaf 1');
  });

  it('测试 processFileTree 初始为空', () => {
    spyOn(component, 'processTreeLeaf'); // mock 掉子树处理

    const file_tree = [
      ['Folder A', [['Task A', 1, 2, 'Leaf A']]],
      ['Folder B', [['Task B', 3, 4, 'Leaf B']]],
    ];

    component.processFileTree(file_tree);

    expect(component.treeNodes.length).toBe(2);
    expect(component.treeNodes[0].label).toBe('Folder A');
    expect(component.treeNodes[1].label).toBe('Folder B');

    expect(component.processTreeLeaf).toHaveBeenCalledTimes(2);
  });

  it('测试 processFileTree 数据更改', () => {
    component.treeNodes = [
      { label: 'Old Folder A', isExpanded: true, children: [], isLeaf: false },
    ];
    spyOn(component, 'processTreeLeaf');

    const file_tree = [['New Folder A', [['Task A', 1, 2, 'Leaf A']]]];

    component.processFileTree(file_tree);

    expect(component.treeNodes.length).toBe(1);
    expect(component.treeNodes[0].label).toBe('New Folder A');
    expect(component.processTreeLeaf).toHaveBeenCalledTimes(1);
  });

  it('测试 processFileTree 长度变短', () => {
    component.treeNodes = [
      { label: 'Folder A', isExpanded: true, children: [], isLeaf: false },
      { label: 'Folder B', isExpanded: true, children: [], isLeaf: false },
    ];
    spyOn(component, 'processTreeLeaf');

    const file_tree = [['Folder A', [['Task A', 1, 2, 'Leaf A']]]];

    component.processFileTree(file_tree);

    expect(component.treeNodes.length).toBe(1);
    expect(component.treeNodes[0].label).toBe('Folder A');
  });

  it('测试 addTreeNodes', () => {
    component.user_name = 'test_user';
    const mockResponse = {
      file_tree: [['Node1', []]],
    };

    spyOn(component, 'processFileTree');
    const navigateSpy = spyOn(component.tree, 'dataChanged');

    component.addTreeNodes();

    const req = httpMock.expectOne('/action/plugin/codemig/task/filetree');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name: 'test_user', task_id: 123 });
    req.flush(mockResponse);

    expect(component.processFileTree).toHaveBeenCalledWith(
      mockResponse.file_tree
    );
    expect(navigateSpy).toHaveBeenCalled();
  });
});
