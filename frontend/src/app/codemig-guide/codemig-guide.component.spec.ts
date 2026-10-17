import { TestBed } from '@angular/core/testing';
import { CodemigGuideComponent } from './codemig-guide.component';

describe('CodemigGuideComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CodemigGuideComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(CodemigGuideComponent);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });

  it('should point guide url to assets markdown', () => {
    const fixture = TestBed.createComponent(CodemigGuideComponent);
    const component = fixture.componentInstance;
    expect(component.guideUrl).toBe('assets/markdown/migration-tool-guide.md');
  });
});
