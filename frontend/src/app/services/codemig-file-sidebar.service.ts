import { Injectable } from '@angular/core';
import { Subject, Subscription } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class CodemigFileSidebarService {

  private freshSource = new Subject<void>();
  refresh$ = this.freshSource.asObservable();

  // 一键迁移视图专用导航通道：
  // 文件树点击文件时不走 router.navigate（避免 reuse:false 销毁子组件、杀掉 SSE/Docker），
  // 而是 emit 一个 { file_id }，由一键迁移子组件内部 onFileClick 接管。
  private migrateNavSource = new Subject<{ file_id: number }>();
  migrateNavigate$ = this.migrateNavSource.asObservable();

  freshFileTree() {
    this.freshSource.next();
  }

  notifyMigrateNavigate(payload: { file_id: number }) {
    this.migrateNavSource.next(payload);
  }
}
