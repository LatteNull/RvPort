import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { SourceCodeMigComponent } from './source-codemig.component';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { PlxModule, PlxGlobalLoadingService, PlxMessage} from 'paletx';
import { Router } from '@angular/router';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { of } from 'rxjs';

describe('SourceCodeMigComponent', () => {
  let component: SourceCodeMigComponent;
  let fixture: ComponentFixture<SourceCodeMigComponent>;
  let httpMock: HttpTestingController;
  let plxGlobalLoading: PlxGlobalLoadingService;
  let plxMessage: jasmine.SpyObj<PlxMessage>;
  let router: Router;

  beforeEach(async () => {
    const plxMessageSpy = jasmine.createSpyObj('PlxMessage', ['success', 'warning','error']);
    await TestBed.configureTestingModule({
      declarations: [
        SourceCodeMigComponent,
      ],
      imports: [
        PlxModule.forRoot(),
        FormsModule,
        ReactiveFormsModule,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: PlxMessage, useValue: plxMessageSpy },
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    plxGlobalLoading = TestBed.inject(PlxGlobalLoadingService);
    plxMessage = TestBed.inject(PlxMessage) as jasmine.SpyObj<PlxMessage>;
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.returnValue(Promise.resolve(true));
    fixture = TestBed.createComponent(SourceCodeMigComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('测试创建组件', () => {
    expect(component).toBeTruthy();
  });


  it('测试 submit 方法 - 任务名称为空', () => {
    component.submit();
    expect(plxMessage.warning).toHaveBeenCalledWith('请补充完整信息...', '');
  });

  it('测试 submit 方法 - 正在上传文件夹', () => {
    component.uploadForm = {
      invalid: false
    } as any; // 使用类型断言避免类型检查
    component.is_uploading_folder = true;
    component.submit();
    expect(plxMessage.warning).toHaveBeenCalledWith('文件夹正在上传...', '');
  });

  it('测试 submit 方法 - 正在上传压缩包', () => {
    component.uploadForm = {
      invalid: false
    } as any; // 使用类型断言避免类型检查
    component.is_uploading_zip = true;
    component.submit();
    expect(plxMessage.warning).toHaveBeenCalledWith('压缩包正在上传...', '');
  });

  it('测试 submit 方法 - 上传列表为空', () => {
    component.uploadForm = {
      invalid: false
    } as any; // 使用类型断言避免类型检查
    component.upload_file_info_lists = [];
    component.submit();
    expect(plxMessage.warning).toHaveBeenCalledWith('请上传文件夹或压缩包', '');
  });

  it('测试 submit 方法 - 成功提交', fakeAsync(() => {
    const loadingSpy = spyOn((component as any).plxGlobalLoading, 'open');
    const loadingCloseSpy = spyOn((component as any).plxGlobalLoading, 'close');
    component.uploadForm = {
      invalid: false,
      value: {
        taskName: '测试任务名称'
      },
    } as any; // 使用类型断言避免类型检查
    component.upload_file_info_lists = [[1, 'file1'], [2, 'file2']];

    component.submit();

    const req = httpMock.expectOne('/action/plugin/codemig/task/create');
    expect(req.request.method).toBe('POST');
    expect(loadingSpy).toHaveBeenCalled();

    req.flush({ task_id: 123 });
    tick();

    expect(plxMessage.success).toHaveBeenCalledWith('创建成功', '');
    expect(router.navigate).toHaveBeenCalledWith(['/codemig/task'], { queryParams: { task_id: 123 } });
    expect(loadingCloseSpy).toHaveBeenCalled();
  }));

  it('测试 submit 方法 - 提交失败', fakeAsync(() => {
    spyOn(console, 'log');
    component.upload_file_info_lists = [[1, 'file1'], [2, 'file2']];
    component.uploadForm = {
      invalid: false,
      value: {
        taskName: '测试任务名称'
      },
    } as any; // 使用类型断言避免类型检查

    component.submit();

    const req = httpMock.expectOne('/action/plugin/codemig/task/create');
    req.error(new ProgressEvent('error'));
    tick();

    expect(console.log).toHaveBeenCalled();
  }));

  it('测试 onFolderSelect - 无文件选择', () => {
    const event = { target: { files: [] } } as unknown as Event;
    component.onFolderSelect(event);
    expect(component.is_uploading_folder).toBeFalse();
  });

  it('测试 onZipSelect - 无文件选择', () => {
    const event = { target: { files: [] } } as unknown as Event;
    component.onZipSelect(event);
    expect(component.is_uploading_zip).toBeFalse();
  });

  it('测试 getKey 方法', () => {
    const obj = { 'test_key': 123 };
    const key = component.getKey(obj);
    expect(key).toBe('test_key');
  });

  it('测试 uploadFile 方法 - 成功', fakeAsync(() => {
    const blob = new Blob(['test']);
    component.uploadedFolders = [{'test': null}];

    component.uploadFile(blob);

    const req = httpMock.expectOne('/action/plugin/codemig/dir/upload');
    req.flush({ code: 0, dir_id: 123 });
    tick();

    expect(plxMessage.success).toHaveBeenCalledWith('文件上传成功', '');
    expect(component.uploadedFolders[0]['test']).toBe(123);
    expect(component.upload_file_info_lists).toEqual([[123, 'upload.zip']]);
    expect(component.is_uploading_folder).toBeFalse();
  }));

  it('测试 uploadFile 方法 - 失败', fakeAsync(() => {
    const blob = new Blob(['test']);
    component.uploadedFolders = [{'test': null}];

    component.uploadFile(blob);

    const req = httpMock.expectOne('/action/plugin/codemig/dir/upload');
    req.flush({ code: 1 }, { status: 500, statusText: 'Server Error' });
    tick();

    expect(component.uploadedFolders.length).toBe(1);
  }));

  it('测试 handleUploadCompletion 方法', () => {
    const file = new File(['test'], 'test.zip');
    component.handleUploadCompletion(file, 123);

    expect(component.is_uploading_zip).toBeFalse();
    expect(component.fileUploadProgressPercentage).toBe(100);
    expect(component.upload_file_info_lists).toEqual([[123, 'test.zip']]);
    expect(component.uploadedFolders).toEqual([{ 'test.zip': 123 }]);
    expect(plxMessage.success).toHaveBeenCalledWith('压缩包 分块test.zip 上传成功', '');
  });

  it('测试 updateProgress 方法', () => {
    const file = new File(['test'], 'test.zip');
    component.filesProgress = { 'test.zip': 50 };
    component.totalSize = 100;

    component.updateProgress(file);

    expect(component.fileUploadProgressSize).toBe(50);
    expect(component.fileUploadProgressPercentage).toBe(100);
  });

  // 模拟 FileReader 的测试辅助函数
  function createMockFileReader(result: string | ArrayBuffer, error?: any): any {
    return {
      readAsText: jasmine.createSpy('readAsText'),
      readAsArrayBuffer: jasmine.createSpy('readAsArrayBuffer'),
      onload: null,
      onerror: null,
      result,
      error,
      triggerLoad: function() {
        if (this.onload) this.onload({ target: { result: this.result } });
      },
      triggerError: function() {
        if (this.onerror) this.onerror(this.error);
      }
    };
  }

  it('测试 readFiles 方法 - 文本文件', async () => {
    const mockFile = {
      name: 'test.txt',
      type: 'text/plain',
      webkitRelativePath: 'path/test.txt'
    } as File;

    const mockFileReader = createMockFileReader('test content');
    spyOn(window, 'FileReader').and.returnValue(mockFileReader);

    const entries: any = {};
    const promises = component.readFiles(entries, [mockFile]);

    mockFileReader.triggerLoad();

    await Promise.all(promises);

    expect(entries['path/test.txt']).toBeDefined();
  });

  it('测试 readFiles 方法 - 二进制文件', async () => {
    const mockFile = {
      name: 'test.bin',
      type: 'application/octet-stream',
      webkitRelativePath: 'path/test.bin'
    } as File;

    const arrayBuffer = new ArrayBuffer(10);
    const mockFileReader = createMockFileReader(arrayBuffer);
    spyOn(window, 'FileReader').and.returnValue(mockFileReader);

    const entries: any = {};
    const promises = component.readFiles(entries, [mockFile]);

    mockFileReader.triggerLoad();

    await Promise.all(promises);

    expect(entries['path/test.bin']).toBeDefined();
  });

  it('测试 uploadChunk 方法', fakeAsync(() => {
    const file = new File(['test content'], 'test.zip');
    const chunkIndex = 0;
    const totalChunks = 2;
    const relativePath = 'test.zip';

    spyOn((component as any).http, 'post').and.returnValue(of({ code: 0 }));

    component.uploadChunk(file, chunkIndex, totalChunks, relativePath).then(() => {
      expect(component.filesProgress['test.zip']).toBe(12);
      expect(component.fileUploadProgressSize).toBe(12);
    });

    tick();
  }));
});
