import { Injectable } from '@angular/core';
import { Router } from '@angular/router'
import { AuthApi } from '../api/auth-api.service';
import { Subject } from 'rxjs';
@Injectable({
  providedIn: 'root'
})
export class LogoutService {
  private _logout$ = new Subject<void>();
  public logout$ = this._logout$.asObservable();

  constructor(
    private router: Router,
    private authApi: AuthApi
  ) { }

  logout(){
    this.authApi.logout().subscribe();;
    // 清除本地缓存信息
    localStorage.clear();
    this._logout$.next();
    // 跳转登录页
    this.router.navigateByUrl('/login');
  }
}
