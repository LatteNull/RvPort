import { ComponentFixture, TestBed } from '@angular/core/testing';

import { NetworkProxyConfigurationComponent } from './network-proxy-configuration.component';

describe('NetworkProxyConfigurationComponent', () => {
  let component: NetworkProxyConfigurationComponent;
  let fixture: ComponentFixture<NetworkProxyConfigurationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NetworkProxyConfigurationComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(NetworkProxyConfigurationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
