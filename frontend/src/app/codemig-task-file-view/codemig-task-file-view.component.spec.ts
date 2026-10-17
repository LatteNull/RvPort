import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { PlxTableService } from 'paletx';
import { PlxModule } from 'paletx';

import { CodemigTaskFileViewComponent } from './codemig-task-file-view.component';

describe('CodemigTaskFileViewComponent', () => {
  let component: CodemigTaskFileViewComponent;
  let fixture: ComponentFixture<CodemigTaskFileViewComponent>;
  let plxTableServiceMock: jasmine.SpyObj<PlxTableService>;

  beforeEach(async () => {
    plxTableServiceMock = jasmine.createSpyObj('PlxTableService', ['getPositionInfo']);
    plxTableServiceMock.getPositionInfo.and.returnValue({
      currentRowData: { file_name: 'abcde' },
      rowIndex: 0,
      colIndex: 0,
      currentTotalRows: 0,
      currentTotalCols: 0,
      currentColumn: undefined,
      columns: undefined,
      index: undefined,
      highlightInfo: undefined
    });
    await TestBed.configureTestingModule({
      declarations: [
        CodemigTaskFileViewComponent,
      ],
      imports: [
        PlxModule.forRoot(),
      ],
      providers: [
        { provide: PlxTableService, useValue: plxTableServiceMock }
      ],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
    })
    .compileComponents();

    fixture = TestBed.createComponent(CodemigTaskFileViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('测试创建应用', () => {
    expect(component).toBeTruthy();
  });

  it('测试安装成功', () => {
    expect(component.rowData.file_name).toBe('abcde');
  });

});
