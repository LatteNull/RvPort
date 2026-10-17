import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { SKIP_PASSWORD_VALIDATION_WARNING } from '../interceptors/http-context-tokens';
@Injectable({
  providedIn: 'root'
})
export class AuthApi{

    constructor(private http: HttpClient) { }

    /*
        登录
    */
    public login(body?: any, options?: any){
        const url = '/action/auth/login'
        return this.http.post(url, body, options)
    }

    /*
        管理员登录
    */
    public verifyAdminLogin(body?: any, options?: any){
        const url = '/action/auth/admin'
        return this.http.post(url, body, options)
    }

    /*
        修改密码
    */
    public modifyPassword(body?: any, options?: any){
        const url = '/action/auth/modify-password'
        const context = (options?.context || new HttpContext()).set(SKIP_PASSWORD_VALIDATION_WARNING, true);
        return this.http.post(url, body, {
            ...options,
            context
        })
    }

    /*
        修改密码
    */
    public resetPassword(body?: any, options?: any){
        const url = '/action/auth/reset-password'
        const context = (options?.context || new HttpContext()).set(SKIP_PASSWORD_VALIDATION_WARNING, true);
        return this.http.post(url, body, {
            ...options,
            context
        })
    }

    /*
        登出
    */
    public logout(body?: any, options?: any){
        const url = '/action/auth/logout'
        return this.http.post(url, body, options)
    }

}
