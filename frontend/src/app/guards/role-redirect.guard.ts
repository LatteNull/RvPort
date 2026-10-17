import { Injectable } from '@angular/core';
import { CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';

@Injectable({
    providedIn: 'root'
})
export class RoleRedirectGuard implements CanActivate {
    constructor(private router: Router) {}

    canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {
    const userRole = localStorage.getItem('userRole');

    if (userRole === 'admin') {
        // Admin用户重定向到系统设置
        this.router.navigate(['/settings/systemsettings']);
    } else {
        // 普通用户重定向到日志管理
        this.router.navigate(['/settings/logmanagement']);
    }

    return false; // 阻止当前路由激活，因为我们进行了重定向
    }
}