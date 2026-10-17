import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { HttpHeaders, HttpResponse, provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { PlxModule, PlxTableModule } from 'paletx';
import { of } from 'rxjs';
import { CodemigTaskViewComponent } from './codemig-task-view.component';
import { CodemigTaskFileViewComponent } from '../codemig-task-file-view/codemig-task-file-view.component';
import { provideAnimations } from '@angular/platform-browser/animations';

interface SummaryItem {
  type: string;      // 建议类型
  issues: number;    // 问题数量
  affectedLines: number | null; // 影响行数，可能为空
}

describe('CodemigTaskViewComponent', () => {
  let component: CodemigTaskViewComponent;
  let fixture: ComponentFixture<CodemigTaskViewComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        CodemigTaskViewComponent,
        CodemigTaskFileViewComponent,
      ],
      imports: [
        PlxModule.forRoot(),
        PlxTableModule.forRoot(),
      ],
      providers: [
        provideAnimations(),
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              url: [{ path: 'testTask' }],
            },
            queryParams: of({ task_id: '123' }),
          },
        },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    }).compileComponents();
    
    fixture = TestBed.createComponent(CodemigTaskViewComponent);
    component = fixture.componentInstance;
    component.plxTable = {
      dataChanged: jasmine.createSpy('dataChanged')
    };

    fixture.detectChanges();
    httpMock = TestBed.inject(HttpTestingController);
    httpMock.expectOne('/action/plugin/codemig/task/files');
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('测试创建组件', () => {
    expect(component).toBeTruthy();
  });

  it('测试任务ID初始化', () => {
    expect(component.task_id).toBe(123);
  });

  it('测试初始化tab数据', () => {
    expect(component.tabItems.length).toEqual(3);
    expect(component.tabItems[0].activeId).toEqual('源码扫描信息');
    expect(component.tabItems[1].activeId).toEqual('软件包扫描信息');
    expect(component.tabItems[2].activeId).toEqual('缺失文件信息');
  });

  it('测试创建源码表格列数据配置', () => {
    expect(component.createFileColumns()).toEqual([
      { key: 'file_index', title: '序号',  width: '150px', show: true },
      { key: 'task_id', show: false },
      { key: 'dir_id', show: false },
      { key: 'file_id', show: false },
      { key: 'file_name', title: '文件名',  width: '200px', show: true },
      { key: 'file_path', title: '路径', width: '800px', show: true },
      { key: 'num_changed_lines', title: '发现问题数量', show: true },
      {
        key: 'operation',
        title: '操作',
        show: true,
        contentType: 'component',
        component: CodemigTaskFileViewComponent,
      },
      { key: 'is_missing', show: false },
    ]);
  });

  it('测试创建软件包表格列数据配置', () => {
    expect(component.createSoftWareColumns()).toEqual([
      { key: 'file_index', title: '序号',  width: '150px', show: true },
      { key: 'task_id', show: false },
      { key: 'dir_id', show: false },
      { key: 'file_id', show: false },
      { key: 'file_name', title: '文件名',  width: '200px', show: true },
      { key: 'file_path', title: '路径', width: '800px', show: true },
      { key: 'support_architecture', title: '支持架构', show: true },
      { key: 'suggestion', title: '建议信息', show: true },
    ]);
  });


  it('测试添加源码子任务数据', () => {
    const file = [0, 1, 2, 3, 4, 5, 6];
    component.addFile(file);
    expect(component.file_data.length).toBe(1);
    expect(component.file_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: 4,
        file_path: 5,
        num_changed_lines: 6,
        is_missing: 'file'
      }
    );
  });

  it('测试添加软件包子任务数据', () => {
    const file = [0, 1, 2, 3, 4, 5, 6, 7];
    component.addSoftware(file);
    expect(component.software_data.length).toBe(1);
    expect(component.software_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: 4,
        file_path: 5,
        support_architecture: 6,
        suggestion: 7
      }
    );
  });

  it('测试添加缺失文件子任务数据', () => {
    const file = [0, 1, 2, 3, 4, 5, 0];
    component.addMissingFile(file);
    expect(component.missing_file_data.length).toBe(1);
    expect(component.missing_file_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: component.file_icon + 4,
        file_path: 5,
        is_missing: 'missing',
        children: []
      }
    );
  });

  it('测试从HTTP请求源码文件任务数据', () => {
    component.user_name = 'testUser';
    const mockResponse = {
      code: 0,
      data: {
        task_name: 'Main Task',
        created_time: "123",
        directories: ["abc"],
        files: [[0, 1, 2, 3, 4, 5, 6]],
        summary: [["100", 200, 300], ["400", 500, 600]],
      }
    };

    component.queryData();

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/task/files');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 123 });
    
    // 返回模拟的响应数据
    req.flush(mockResponse);

    // 断言任务名称是否正确更新
    expect(component.task_name).toBe('Main Task');

    // 断言 `data` 是否正确添加
    expect(component.file_data.length).toBe(1);
    expect(component.file_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: 4,
        file_path: 5,
        num_changed_lines: 6,
        is_missing: 'file'
      }
    );
    let expected: Array<SummaryItem> = [];
    expected.push({ type: "100", issues: 200, affectedLines: 300 });
    expected.push({ type: "400", issues: 500, affectedLines: 600 });
    expect(component.summary_data).toEqual(expected);
  });

  it('测试从HTTP请求软件包任务数据', () => {
    component.user_name = 'testUser';
    const mockResponse = {
      code: 0,
      data: {
        software: [[0, 1, 2, 3, 4, 5, 6, 7]],
      }
    };

    expect(component.tabItems[1].is_obtain).toEqual(false);

    const event = {
      nextId: '软件包扫描信息'
    }
    expect(event.nextId).toEqual('软件包扫描信息');

    component.tabChange(event);

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/task/software');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 123 });
    
    // 返回模拟的响应数据
    req.flush(mockResponse);
    expect(component.tabItems[1].is_obtain).toEqual(true);
    expect(component.software_data.length).toBe(1);
    expect(component.software_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: 4,
        file_path: 5,
        support_architecture: 6,
        suggestion: 7
      }
    );
  });

  it('测试从HTTP请求缺失文件任务数据', () => {
    component.user_name = 'testUser';
    const mockResponse = {
      code: 0,
      data: {
        missing_files_rows: [[0, 1, 2, 3, 4, 5, 0]],
      }
    };

    expect(component.tabItems[2].is_obtain).toEqual(false);

    const event = {
      nextId: '缺失文件信息'
    }
    expect(event.nextId).toEqual('缺失文件信息');

    component.tabChange(event);

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/task/missing_files');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 123 });
    
    // 返回模拟的响应数据
    req.flush(mockResponse);
    expect(component.tabItems[2].is_obtain).toEqual(true);
    expect(component.missing_file_data.length).toBe(1);
    expect(component.missing_file_data[0]).toEqual(
      {
        file_index: 0,
        task_id: 1,
        dir_id: 2,
        file_id: 3,
        file_name: component.file_icon + 4,
        file_path: 5,
        is_missing: 'missing',
        children: []
      }
    );
  });

  it('测试软件包数据不会重复获取', () => {
    component.user_name = 'testUser';
    const mockResponse = {
      code: 0,
      data: {
        software: [[0, 1, 2, 3, 4, 5, 6, 7]],
      }
    };
    
    expect(component.tabItems[1].is_obtain).toEqual(false);

    const event1 = {
      nextId: '源码扫描信息'
    }
    const event2 = {
      nextId: '软件包扫描信息'
    }

    expect(event1.nextId == '软件包扫描信息' && !component.tabItems[1].is_obtain).toEqual(false);
    expect(event2.nextId == '软件包扫描信息' && !component.tabItems[1].is_obtain).toEqual(true);

    component.tabChange(event2);

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/task/software');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 123 });
    
    // 返回模拟的响应数据
    req.flush(mockResponse);

    // 执行完一次内容后，判断由true变为false
    expect(event2.nextId == '软件包扫描信息' && !component.tabItems[1].is_obtain).toEqual(false);
  });

  it('测试缺失文件任务数据不会重复获取', () => {
    component.user_name = 'testUser';
    const mockResponse = {
      code: 0,
      data: {
        missing_files_rows: [[0, 1, 2, 3, 4, 5]],
      }
    };

    expect(component.tabItems[2].is_obtain).toEqual(false);

    const event = {
      nextId: '缺失文件信息'
    }
    expect(event.nextId).toEqual('缺失文件信息');

    component.tabChange(event);

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/task/missing_files');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 123 });
    
    // 返回模拟的响应数据
    req.flush(mockResponse);

    // 执行完一次内容后，判断由true变为false
    expect(event.nextId == '软件包扫描信息' && !component.tabItems[2].is_obtain).toEqual(false);
  });

  it('测试展开缺失文件子表', () => {
    // 确保 plxTable 存在
    component.plxTable = {
      dataChanged: jasmine.createSpy('dataChanged')
    };
    const mockEvent = {
      row: {
        isExpanded: true,
        file_id: 123,
        user_naem: component.user_name,
        task_id: 1,
        dir_id: 1,
        children: null,
        file_index: 1
      }
    };
  
    component.onRowExpandCollapse(mockEvent);
  
    // 验证请求是否正确发送
    const req = httpMock.expectOne('/action/plugin/codemig/task/existing_arch');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({user_name: component.user_name, file_id: 123, task_id: 1, dir_id: 1});
    
    // 模拟成功响应
    const mockResponse = {code: 0, data: [[1, 1, 1, 'home/admin/test_armd64.go']] };
    req.flush(mockResponse);
  
    expect(mockEvent.row.children).toBeDefined();
  });

  it('测试缺失文件添加子数据', () => {
    const rowData = {
      row: {
        isExpanded: true,
        file_id: 123,
        user_naem: component.user_name,
        task_id: 1,
        dir_id: 1,
        children: null,
        file_index: 1
      }
    };
    const data = [[1, 1, 1, 'home/admin/test_armd64.go'] ]
    
    const children = component.getChildrenNode(rowData['row'], data)

    expect(children[0]).toEqual({ 
      file_index: ``,
      task_id: 1,
      dir_id: 1,
      file_id: 1,
      file_name: component.file_icon + 'test_armd64.go',
      'file_path': 'home/admin/test_armd64.go',
      "isLeaf": true,
      "type": 'file',
      "children": []
    });

  });

  function createMockResponse(body: any, filename: string) {
    const headers = new HttpHeaders().set(
      'Content-Disposition',
      `attachment; filename*=UTF-8''${filename}`
    );
    return new HttpResponse({
      body: body,
      headers: headers
    });
  }

  it('测试 exportExcel', () => {
    // 模拟DOM方法
    const realAnchor = document.createElement('a');
    spyOn(document, 'createElement').and.returnValue(realAnchor);
    const clickSpy = spyOn(realAnchor, 'click').and.callThrough();
    const createObjectURLSpy = spyOn(URL, 'createObjectURL').and.callThrough();
    const revokeObjectURLSpy = spyOn(URL, 'revokeObjectURL').and.callThrough();
    const appendChildSpy = spyOn(document.body, 'appendChild').and.callThrough();
    const removeChildSpy = spyOn(document.body, 'removeChild').and.callThrough();

    component.user_name = 'testUser';
    component.task_id = 100;

    component.exportExcel();

    // 模拟 HTTP 请求
    const req = httpMock.expectOne('/action/plugin/codemig/report/download');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name:'testUser', task_id: 100 });

    const mockBlob = new Blob(['test content'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const mockResponse = createMockResponse(mockBlob, 'test_report.xlsx');
    // 返回模拟的响应数据
    req.event(mockResponse);

    // 验证结果
    expect(document.createElement).toHaveBeenCalledWith('a');
    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    expect(realAnchor.download).toBe('test_report.xlsx');
    expect(clickSpy).toHaveBeenCalled();

    // 验证 appendChild 接收了真实的 anchor 元素
    expect(appendChildSpy).toHaveBeenCalledWith(realAnchor);
    expect(removeChildSpy).toHaveBeenCalledWith(realAnchor);
    expect(revokeObjectURLSpy).toHaveBeenCalled();
  });

  it('测试 exportPatch 正常下载补丁', () => {
    const clickSpy = jasmine.createSpy('click');
    const realAnchor = { click: clickSpy, download: '', href: '' };
    spyOn(document, 'createElement').and.returnValue(realAnchor as any);
    spyOn(document.body, 'appendChild');
    spyOn(document.body, 'removeChild');
    const createObjectURLSpy = spyOn(URL, 'createObjectURL').and.returnValue('blob:mock');
    spyOn(URL, 'revokeObjectURL');

    component.user_name = 'testUser';
    component.task_id = 100;

    component.exportPatch();

    const req = httpMock.expectOne('/action/plugin/codemig/report/download_patch');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_name: 'testUser', task_id: 100 });

    // 正常响应：text/plain blob + Content-Disposition
    const mockBlob = new Blob(['patch content'], { type: 'text/plain' });
    const headers = new HttpHeaders().set(
      'Content-Disposition', `attachment; filename*=UTF-8''test_task.patch`);
    req.flush(mockBlob, { headers });

    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    expect(realAnchor.download).toBe('test_task.patch');
    expect(clickSpy).toHaveBeenCalled();
  });

  it('测试 exportPatch 后端错误 JSON blob 时弹错误且不下载', async () => {
    const errorSpy = spyOn((component as any).plxMessage, 'error');
    const createObjectURLSpy = spyOn(URL, 'createObjectURL');

    component.user_name = 'testUser';
    component.task_id = 100;

    component.exportPatch();

    const req = httpMock.expectOne('/action/plugin/codemig/report/download_patch');
    // 后端错误：HTTP 200 + application/json（responseType:blob 时被包成 Blob）
    const errorBlob = new Blob([JSON.stringify({ code: 1, msg: '任务不存在' })],
      { type: 'application/json' });
    req.flush(errorBlob);

    // blob.text() 异步链较长，用宏任务等待其完成
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(errorSpy).toHaveBeenCalledWith('导出失败', '任务不存在');
    expect(createObjectURLSpy).not.toHaveBeenCalled();
  });

  it('测试 exportPatch HTTP 错误回调弹错误', () => {
    const errorSpy = spyOn((component as any).plxMessage, 'error');

    component.user_name = 'testUser';
    component.task_id = 100;

    component.exportPatch();

    const req = httpMock.expectOne('/action/plugin/codemig/report/download_patch');
    // responseType:blob 的请求即使错误响应也必须 flush Blob 实例
    req.flush(new Blob(['server error'], { type: 'text/plain' }),
      { status: 500, statusText: 'Internal Server Error' });

    expect(errorSpy).toHaveBeenCalledWith('导出失败', '');
  });

});
