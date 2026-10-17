import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Injectable({
  providedIn: 'root'
})
export class ConfigApi{

    constructor(private http: HttpClient) { }

    /*
        获取系统配置
    */
    public getConfig(options?: any){
        const url = '/action/config'
        return this.http.get(url, options)
    }

    /*
        获取系统配置
    */
    public postConfig(body?: any, options?: any){
        const url = '/action/config'
        return this.http.post(url, body, options)
    }

}
