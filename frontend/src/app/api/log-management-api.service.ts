import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Injectable({
  providedIn: 'root'
})
export class LogManagementApi{

    constructor(private http: HttpClient) { }

    /*
        获取日志清单
    */
    public getLogMangerList(body?: any, options?: any){
        const url = '/action/logmanager/list'
        return this.http.post(url, body, options)
    }

    /*
        获取日志过滤清单
    */
    public getFilter(options?: any){
        const url = '/action/logmanager/filter'
        return this.http.get(url, options)
    }

    /*
        获取csv
    */
    public getLogMangerCsv(options?: any){
        const url = '/action/logmanager/csv'
        return this.http.get(url, options)
    }

    /*
        下载日志信息
    */
    public downloadLogManager(body?: any, options?: any){
        const url = '/action/logmanager/download'
        return this.http.post(url, body, options)
    }

}
