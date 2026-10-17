import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Injectable({
  providedIn: 'root'
})
export class PluginManagerApi{

    constructor(private http: HttpClient) { }

    /*
        获取插件列表
    */
    public getPluginList(options?: any){
        const url = '/action/pluginmanager/list'
        return this.http.get(url, options)
    }

}
