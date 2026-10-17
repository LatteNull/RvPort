import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Injectable({
  providedIn: 'root'
})
export class CodeMigApi{

    constructor(private http: HttpClient) { }

    /*
        创建迁移任务
    */
    public createMigTask(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/create"
        return this.http.post(url, body, options)
    }

    /*
        上传文件夹
    */
    public uploadFolder(body?: any, options?: any){
        const url = "/action/plugin/codemig/dir/upload"
        return this.http.post(url, body, options)
    }

    /*
        上传压缩包
    */
    public uploadZip(body?: any, options?: any){
        const url = "/action/plugin/codemig/dir/upload_zip"
        return this.http.post(url, body, options)
    }

    /*
        移除上传文件夹/压缩包
    */
    public deleteFolder(body?: any, options?: any){
        const url = "/action/plugin/codemig/dir/delete_folder"
        return this.http.post(url, body, options)
    }

    /*
        获取任务列表
    */
    public getTaskList(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/list"
        return this.http.post(url, body, options)
    }

    /*
        删除某个任务
    */
    public deleteTask(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/delete"
        return this.http.post(url, body, options)
    }

    /*
        获取源码扫描信息结果以及问题统计摘要
    */
    public getTaskFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/files"
        return this.http.post(url, body, options)
    }

    /*
        获取软件包扫描信息
    */
    public getTaskSoftware(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/software"
        return this.http.post(url, body, options)
    }

    /*
        获取缺失文件扫描信息
    */
    public getTaskMissingFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/missing_files"
        return this.http.post(url, body, options)
    }

    /*
        获取一键迁移的缺失文件列表
    */
    public getProjectMigrateMissingFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/project_migrate_missing_files"
        return this.http.post(url, body, options)
    }

    /*
        ★ 功能验证（ut_test）阶段：获取 <repo>/test/ 下生成的测试产物清单
        对应后端 POST /action/plugin/codemig/task/ut_test_files
          - 输入：user_name、dir_id
          - 输出：{code, data: {targets: [{target_name, rel_path,
              files: [{name, path, size}], has_coverage, diff_passed}]}}
        前端把 targets 填进 ② 功能验证节点的 items 渲染。
    */
    public getUtTestFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/ut_test_files"
        return this.http.post(url, body, options)
    }


    /*
        获取依赖包扫描信息
    */
    public getTaskDependence(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence"
        return this.http.post(url, body, options)
    }

    public getTaskDependenceSummary(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/depsum"
        return this.http.post(url, body, options)
    }

    /*
        获取缺失文件所对应的现存架构文件信息
    */
    public getTaskExistingArch(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/existing_arch"
        return this.http.post(url, body, options)
    }

    /*
        导出扫描下载报告
    */
    public exportReportDownload(body?: any, options?: any){
        const url = "/action/plugin/codemig/report/download"
        return this.http.post(url, body, options)
    }

    /*
        导出patch补丁文件
    */
    public exportPatchDownload(body?: any, options?: any){
        const url = "/action/plugin/codemig/report/download_patch"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包中的源码扫描信息结果以及问题统计摘要
    */
    public getTaskDependenceFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_files"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包中的软件包扫描信息
    */
    public getTaskDependencedeSoftware(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_software"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包中的缺失文件扫描信息
    */
    public getTaskDependenceMissingFiles(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_missing_files"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包中的缺失文件所对应的现存架构文件信息
    */
    public getTaskDependenceExistingArch(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_existing_arch"
        return this.http.post(url, body, options)
    }

    /*
        获取源码扫描中查看建议源码树结构
    */
    public getTaskFiletree(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/filetree"
        return this.http.post(url, body, options)
    }

    /*
        获取源码扫描中查看建议源码文件内容
    */
    public getTaskOriginalFile(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/original_file"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包中的源码扫描中查看建议源码树结构
    */
    public getTaskDependenceFiletree(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_filetree"
        return this.http.post(url, body, options)
    }

    /*
        保存源码扫描文件修改
    */
    public saveTaskFileChange(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/changesave"
        return this.http.post(url, body, options)
    }

    /*
        获取源码扫描文件可修改建议信息
    */
    public getTaskFileChange(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/changes"
        return this.http.post(url, body, options)
    }

    /*
        获取依赖包扫描源码扫描文件可修改建议信息
    */
    public getTaskDependenceFileChange(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_changes"
        return this.http.post(url, body, options)
    }

    public getTaskFileGenerateUrl(){
        return "/action/plugin/codemig/task/generate"
    }

    /*
        获取依赖包扫描源码扫描文件可修改建议信息
    */
    public getTaskDependenceFileGenerate(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/dependence_generate"
        return this.http.post(url, body, options)
    }

    /*
        获取用户初始python、go配置信息
    */
    public queryInitConfiguration(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/query_init_configuration"
        return this.http.post(url, body, options)
    }

    /*
        获取AI建议信息路由
    */
    public queryAISuggestionUrl(){
        return "/action/plugin/codemig/advise/ai_suggestion"
    }

    /*
        取消AI建议信息路由
    */
    public cancelAISuggestionUrl(){
        return "/action/plugin/codemig/advise/ai_suggestion_cancel"
    }

    /*
        检测文件是否存在
    */
    public checkFileExists(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/check_file_exists"
        return this.http.post(url, body, options)
    }

    /*
        保存文件内容
    */
    public saveFileContent(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/save_file_content"
        return this.http.post(url, body, options)
    }

    /*
        一键迁移：保存项目级文件修改（仅写文件 + commit，不触发 AI 扫描）
    */
    public saveProjectFileChange(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/project_file_changesave"
        return this.http.post(url, body, options)
    }

    /*
        创建文件或目录
    */
    public createFileOrDirectory(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/create_file_or_directory"
        return this.http.post(url, body, options)
    }

    /*
        删除文件或目录
    */
    public deleteFileOrDirectory(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/delete_file_or_directory"
        return this.http.post(url, body, options)
    }

    /*
        更新建议信息忽略状态
    */
    public updateSuggestionIgnored(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/update_suggestion_ignored"
        return this.http.post(url, body, options)
    }

    /*
        回退上一版本
    */
    public rollbackFile(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/rollback_file"
        return this.http.post(url, body, options)
    }

    /*
        项目级一键迁移路由
    */
    public migrateProjectUrl(){
        return "/action/plugin/codemig/task/migrate_project"
    }

    /*
        项目级迁移手动回退（回退到最近一次迁移前）
    */
    public rollbackProjectMigrate(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/rollback_project_migrate"
        return this.http.post(url, body, options)
    }

    /*
        项目级迁移刷新恢复（获取最近一次迁移的 AI 建议）
        v4.x：body 可带 stage（project_migrate/ut_test）按阶段恢复；
        缺省取全部阶段里最近的一次（兼容旧行为）。
    */
    public reopenProjectAi(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/reopen_project_ai"
        return this.http.post(url, body, options)
    }

    /*
        ★ v4.x：项目级阶段历史列表（AI 面板切换器数据源）
        对应后端 POST /action/plugin/codemig/task/project_ai_history
          - 输入：user_name、dir_id
          - 输出：{code, data: [{ai_id, stage, mode, run_time, finished,
              request_id, created_at}]}（最近在前，最多 50 条，不含正文大字段）
    */
    public getProjectAiHistory(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/project_ai_history"
        return this.http.post(url, body, options)
    }

    /*
        列出项目迁移的所有历史快照点（基于 reflog，仅供一键迁移使用）
    */
    public listProjectHistory(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/list_project_history"
        return this.http.post(url, body, options)
    }

    /*
        生成两个 commit 之间的增量 patch（文件流下载）
    */
    public generateProjectPatch(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/generate_project_patch"
        return this.http.post(url, body, options)
    }

    /*
        一键迁移：单击"添加到 AI 建议"时立即入库，避免刷新后丢失
        v4.0：插入到 codemig_task_directory_file_suggestion 表 is_manual=1 的行
    */
    public insertManualSuggestion(body?: any, options?: any){
        const url = "/action/plugin/codemig/advise/suggestion/insert_manual"
        return this.http.post(url, body, options)
    }

    /*
        一键迁移：删除一条手动选中的代码段（右键菜单 / 取消选中时调用）
        v4.0：从 codemig_task_directory_file_suggestion 表 WHERE is_manual=1 删除
    */
    public deleteManualSuggestion(body?: any, options?: any){
        const url = "/action/plugin/codemig/advise/suggestion/delete_manual"
        return this.http.post(url, body, options)
    }

    /*
        一键迁移：列出某 dir 下所有手动选中的代码段（组件初始化时调用，用于刷新页面后恢复）
        v4.0：从 codemig_task_directory_file_suggestion 表 WHERE is_manual=1 取
    */
    public listManualSuggestionsByDir(body?: any, options?: any){
        const url = "/action/plugin/codemig/advise/suggestion/list_manual_by_dir"
        return this.http.post(url, body, options)
    }

    /*
        ★ v4.x.0-RUN-FLOW：② 功能验证
        对应后端视图 codemig_ai_bp（url_prefix='/advise'）下的
        POST /action/plugin/codemig/advise/skill/ut_test
          - 输入：user_name、task_id、dir_id、agent_model、api_format、request_uuid
          - 处理：注入 ut_test skill，拉一个项目 Agent 跑（生成可对比单元测试 + 交叉编译 + qemu 回归）
          - 输出：流式（前端 queryAI 风格）+ rescan + git commit
    */
    public runUtTestUrl(){
        return "/action/plugin/codemig/advise/skill/ut_test"
    }
    public runUtTest(body?: any, options?: any){
        return this.http.post(this.runUtTestUrl(), body, options)
    }


    /*
        ★ v4.x.0-RESUME：一键迁移 / ut_test 两阶段"继续"按钮
        对应后端 POST /action/plugin/codemig/advise/skill/migrate_resume
          - 输入：{stage, dir_id, model?, request_uuid?}
          - 行为：注入 _resume=True，复用既有阶段 impl 启动 qwen --continue。
          - 输出：流式（SSE / stream-json），与"运行"按钮走同一套 queryAI 流式消费。
    */
    public migrateResumeUrl(){
        return "/action/plugin/codemig/advise/skill/migrate_resume"
    }
    public migrateResume(body?: any, options?: any){
        return this.http.post(this.migrateResumeUrl(), body, options)
    }

    /*
        ★ v4.x.0-RESUME：探测一键迁移各阶段是否各自存在可恢复的 qwen 会话
        对应后端 POST /action/plugin/codemig/advise/skill/migrate_resumable_status
          - 输入：{dir_id}
          - 输出：{stages: {project_migrate, ut_test}, each: {available}}
    */
    public migrateResumableStatusUrl(){
        return "/action/plugin/codemig/advise/skill/migrate_resumable_status"
    }
    public migrateResumableStatus(body?: any, options?: any){
        return this.http.post(this.migrateResumableStatusUrl(), body, options)
    }

    /*
        ★ v3.2：前端硬边界 commit 入口
        对应后端 POST /action/plugin/codemig/advise/skill/boundary_commit
          - 输入：{user_name, dir_id, reason, src?, stage?, type?}
          - 行为：调 force_commit_marker 产生 allow-empty commit，
                  让每个用户动作（点击运行 / 点击继续 / 阶段收尾）
                  都在 git 历史里留下锚点。
          - 输出：{code, msg, sha}
        调用方：
          - _preBoundaryCommit（点击"运行"瞬间）
          - _preResumeBoundaryCommit（点击"继续"瞬间）
          - _postBoundaryCommit（阶段 success/error/cancel 收尾）
    */
    public migrateBoundaryCommitUrl(){
        return "/action/plugin/codemig/advise/skill/boundary_commit"
    }
    public migrateBoundaryCommit(body?: any, options?: any){
        return this.http.post(this.migrateBoundaryCommitUrl(), body, options)
    }

    /*
        ★ v5.0.0：一键迁移视图的"重新扫描"按钮
        启动后台 rescan 任务（异步执行），对 file_source='changed' 的所有文件重跑 18 种代码识别器。
        返回 total：changed 文件总数（前端用来显示 "扫描中 X/Y" 的 Y）。
        复用 query_ai_handler.rescan_file + update_file_suggestion_to_database，
        已有的人工选中段（is_manual=1）豁免，AI 生成的旧建议（is_manual=0）被新结果替换。
    */
    public rescanTask(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/rescan"
        return this.http.post(url, body, options)
    }

    /*
        ★ v5.0.0：查询重扫状态（前端轮询调用，5s/次，前 10 次后改为 10s/次）
        返回字段：
          - status: 0=空闲 / 1=运行中 / 2=成功 / 3=失败
          - processed: 已处理文件数
          - total: 总文件数
          - fail_reason: 失败原因（status=3 时非空）
    */
    public getRescanStatus(body?: any, options?: any){
        const url = "/action/plugin/codemig/task/rescan_status"
        return this.http.post(url, body, options)
    }
}
