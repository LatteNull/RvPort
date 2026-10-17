import { Injectable } from '@angular/core';

/**
 * 一键迁移组件状态持久化服务
 *
 * 背景：migrate_project 路由配置了 data: { reuse: false }，
 *       CustomReuseStrategy.shouldReuseRoute 在 reuse=false 时会强制返回 false，
 *       导致每次 router.navigate(..., { queryParams: ... }) 都会销毁并重建组件实例。
 *
 * 一键迁移是整个工程的整体迁移，所有文件的 manualSelection 状态必须跨文件切换保留，
 * 因此将权威存储 manualMigrateItemsMap + lastAiChangesByFileId 提升到全局单例 Service，
 * 组件销毁前自动保存到 Service，组件创建后从 Service 恢复。
 *
 * 隔离策略：按 (task_id, dir_id) 分组保存，不同任务之间互不干扰。
 */
@Injectable({
  providedIn: 'root'
})
export class ProjectMigrateStateService {

  private manualSelectionsStore: Map<string, Map<number, Array<{ start_line: number; end_line: number }>>> = new Map();
  private aiChangesStore: Map<string, { [fileId: number]: any[] }> = new Map();
  private fileMetaStore: Map<string, { [fileId: number]: any }> = new Map();

  private buildKey(taskId: number, dirId: number): string {
    return `${taskId}_${dirId}`;
  }

  saveManualSelections(taskId: number, dirId: number, map: Map<number, Array<{ start_line: number; end_line: number }>>): void {
    if (!taskId || !dirId) return;
    const key = this.buildKey(taskId, dirId);
    const cloned = new Map<number, Array<{ start_line: number; end_line: number }>>();
    for (const [fileId, selections] of map) {
      cloned.set(fileId, selections.map(s => ({ ...s })));
    }
    this.manualSelectionsStore.set(key, cloned);
  }

  loadManualSelections(taskId: number, dirId: number): Map<number, Array<{ start_line: number; end_line: number }>> {
    if (!taskId || !dirId) return new Map();
    const key = this.buildKey(taskId, dirId);
    const stored = this.manualSelectionsStore.get(key);
    if (!stored) return new Map();
    const cloned = new Map<number, Array<{ start_line: number; end_line: number }>>();
    for (const [fileId, selections] of stored) {
      cloned.set(fileId, selections.map(s => ({ ...s })));
    }
    return cloned;
  }

  saveAiChanges(taskId: number, dirId: number, changes: { [fileId: number]: any[] }): void {
    if (!taskId || !dirId) return;
    const key = this.buildKey(taskId, dirId);
    this.aiChangesStore.set(key, { ...changes });
  }

  loadAiChanges(taskId: number, dirId: number): { [fileId: number]: any[] } {
    if (!taskId || !dirId) return {};
    const key = this.buildKey(taskId, dirId);
    return { ...(this.aiChangesStore.get(key) || {}) };
  }

  saveFileMeta(taskId: number, dirId: number, meta: { [fileId: number]: any }): void {
    if (!taskId || !dirId) return;
    const key = this.buildKey(taskId, dirId);
    this.fileMetaStore.set(key, { ...meta });
  }

  loadFileMeta(taskId: number, dirId: number): { [fileId: number]: any } {
    if (!taskId || !dirId) return {};
    const key = this.buildKey(taskId, dirId);
    return { ...(this.fileMetaStore.get(key) || {}) };
  }

  clearTask(taskId: number, dirId: number): void {
    if (!taskId || !dirId) return;
    const key = this.buildKey(taskId, dirId);
    this.manualSelectionsStore.delete(key);
    this.aiChangesStore.delete(key);
    this.fileMetaStore.delete(key);
  }
}
