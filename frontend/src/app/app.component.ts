import { Component, ViewContainerRef } from '@angular/core';
import { PlxMessage } from 'paletx';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  standalone: false,
})

export class AppComponent {
  title = 'homes';
  constructor(
    private vRef : ViewContainerRef,
    private plxMessageService: PlxMessage,
  ) {
    this.plxMessageService.setRootViewContainerRef(this.vRef);
    }
}
