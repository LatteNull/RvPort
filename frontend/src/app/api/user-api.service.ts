import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { SKIP_PASSWORD_VALIDATION_WARNING } from '../interceptors/http-context-tokens';
@Injectable({
  providedIn: 'root'
})
export class UserApi{

    constructor(private http: HttpClient) { }

    /*
        获取用户列表
    */
    public getUserList(options?: any){
        const url = '/action/user/list'
        return this.http.get(url, options)
    }

    /*
        新增用户
    */
    public addUser(body?: any, options?: any){
        const url = '/action/user'
        const context = (options?.context || new HttpContext()).set(SKIP_PASSWORD_VALIDATION_WARNING, true);
        return this.http.post(url, body, {
            ...options,
            context
        })
    }

    /*
        删除用户
    */
    public deleteUser(user_id: any, body?: any, options?: any){
        const url = `/action/user/rm/${user_id}`
        const context = (options?.context || new HttpContext()).set(SKIP_PASSWORD_VALIDATION_WARNING, true);
        return this.http.post(url, body, {
            ...options,
            context
        })
    }

}
