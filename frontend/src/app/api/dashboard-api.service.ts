import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class DashboardApi {
  constructor(private http: HttpClient) {}

  public getSystemPanel(
    params?: { start?: string; end?: string },
    options?: any,
  ) {
    const url = '/action/dashboard/system_panel';
    return this.http.get(url, { ...options, params: params || {} });
  }
}

