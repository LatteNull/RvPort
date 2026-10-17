import { Component, ChangeDetectorRef, ViewChild, ElementRef } from '@angular/core';
import { FormBuilder, FormGroup, Validators,  AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { CodeMigApi } from '../api/codemig-api.service';
import { Router } from '@angular/router';
import { PlxMessage, PlxGlobalLoadingService } from 'paletx';
import { zipSync, strToU8, Zippable } from 'fflate';
import { environment } from '../environment/environment';
import { lastValueFrom } from 'rxjs';
import { Clipboard } from '@angular/cdk/clipboard';
import { LogoutService } from '../services/logout.service';

@Component({
  selector: 'app-source-codemig',
  templateUrl: './source-codemig.component.html',
  styleUrl: './source-codemig.component.css',
  standalone: false,
})
export class SourceCodeMigComponent{
  @ViewChild('textLoadingTemp') public textLoadingTemp:any;
  @ViewChild('ZipInput', { static: false }) zipInputRef!: ElementRef<HTMLInputElement>;
  uploadForm!: FormGroup;
  user_name: any;

  uploadedFolders: { [key: string]: number | null }[] = [];

  upload_file_info_lists: Array<any>[] = [];

  filesProgress: {[name: string]: number} = {};
  fileUploadProgressPercentage: number = 0;
  fileUploadProgressSize: number = 0;
  totalSize: number = 0;

  // 是否正在上传
  is_uploading_folder: boolean = false;
  is_uploading_zip: boolean = false;

  // 文件大小超额标志
  total_size_exceed: boolean = false;

  enable: boolean = false;

  // 加载进度相关
  loadingPercent: number = 0;
  loadingProgressInterval: any = null;
  fastProgressInterval: any = null;

  go_environment_content: string = 'GOPROXY=https://proxy.internal.com,https://goproxy.cn,direct | GOPRIVATE=git.internal.com | GONOPROXY=git.internal.com | GOSUMDB=sum.golang.google.cn | GONOSUMDB=*.corp.com | GOINSECURE=*.internal.com | SSL_CERT_FILE=/path/to/custom-ca.pem';

  // 提示
  python_interpreter_tip: string = '请根据实际情况填写python解释器路径（如 /usr/bin/python3），点击可复制测试样例';
  python_image_source_tip: string = '请根据实际情况填写python镜像源路径（如 阿里云镜像源https://mirrors.aliyun.com/pypi/simple/），点击可复制测试样例';
  go_install_path_tip: string = '请输入Go解释器的可执行文件路径（如 /usr/bin/go），点击可复制测试样例';
  go_environment_tip: string = '请设置go模块环境变量，多个用 | 分隔（如 ' + this.go_environment_content + '），点击可复制测试样例';


  constructor(
    private codeMigApi: CodeMigApi,
    private router: Router,
    private plxMessage: PlxMessage,
    private cdr: ChangeDetectorRef,
    private plxGlobalLoading: PlxGlobalLoadingService,
    private fb: FormBuilder,
    private clipboard: Clipboard,
    private logoutService: LogoutService
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  showToast(type: any, message: any){
    this.plxMessage.show(type, {
      title: message,
      isLightweight: true
    });
  }

  ngOnInit() {
    this.logoutService.logout$.subscribe(() => {
      // 执行清理：取消定时器、重置 loading、销毁资源等
      this.plxGlobalLoading.close();
    });
    this.uploadForm = this.fb.group({
      taskName: [''],
      scanDependencies: ['no'],
      dependencies: ['python'],
      // Python 相关配置
      pythonInterpreter: [''],
      pythonImageSource: [''],
      // Go 相关配置
      goInstallPath: [''],
      goEnvironment: [''],
    }, { validators: this.dependenciesRequiredValidator() });

    this.codeMigApi.queryInitConfiguration({'user_name': this.user_name}).subscribe({
      next: (response: any) => {
        console.log(response)
        if (response.code == 0){
          this.enable = response.data.enable
          this.uploadForm.patchValue({
            pythonInterpreter: response.data.python_interpreter,
            pythonImageSource: response.data.python_image_source,
            goInstallPath: response.data.go_install_path,
            goEnvironment: response.data.go_environment
          });
        }
      },
      error: (errorResponse: any) => {
        console.log("Error: ", errorResponse);
      }
    });
  }

  // 自定义校验规则
  dependenciesRequiredValidator(): ValidatorFn {
    return (formGroup: AbstractControl): ValidationErrors | null => {
      const getValidatedValue = (controlName: string): string => {
        const value = formGroup.get(controlName)?.value;
        if (value == null) return '';
        return value;
      };
      const taskName = getValidatedValue('taskName');
      const scanDependencies = getValidatedValue('scanDependencies');
      const dependencies = getValidatedValue('dependencies');
      const pythonInterpreter = getValidatedValue('pythonInterpreter');
      const goInstallPath = getValidatedValue('goInstallPath');
      if (!taskName || taskName.trim() === ''){
        return { taskNameRequired: true };
      }
      if (scanDependencies === 'yes' && dependencies === 'python' && pythonInterpreter.trim() === ''){
        return { pythonInterpreterRequired: true };
      }
      if (scanDependencies === 'yes' && dependencies === 'go' && goInstallPath.trim() === ''){
        return { goInstallPathRequired: true };
      }
      return null; // 验证通过
    };
  }

  copyContent(content: string){
    this.clipboard.copy(content);
    this.plxMessage.success("复制成功", "")
  }

  startLoadingProgress(): void {
    // 重置进度
    this.loadingPercent = 0;
    
    // 清除之前的定时器（如果存在）
    this.stopLoadingProgress();

    // 0%-60%阶段：每2秒跳10%
    this.fastProgressInterval = setInterval(() => {
      if (this.loadingPercent < 60) {
        this.loadingPercent += 10;
        this.cdr.detectChanges();
      } else {
        // 到达60%，切换到慢速阶段
        if (this.fastProgressInterval) {
          clearInterval(this.fastProgressInterval);
          this.fastProgressInterval = null;
        }
        
        // 60%-90%阶段：每10秒跳10%
        this.loadingProgressInterval = setInterval(() => {
          if (this.loadingPercent < 90) {
            this.loadingPercent += 10;
            // 确保不超过90%
            if (this.loadingPercent > 90) {
              this.loadingPercent = 90;
            }
            this.cdr.detectChanges();
          } else {
            // 到达90%，停止增长，等待扫描完成
            if (this.loadingProgressInterval) {
              clearInterval(this.loadingProgressInterval);
              this.loadingProgressInterval = null;
            }
          }
        }, 10000); // 10秒
      }
    }, 2000); // 2秒
  }

  stopLoadingProgress(complete: boolean = false): void {
    if (this.fastProgressInterval) {
      clearInterval(this.fastProgressInterval);
      this.fastProgressInterval = null;
    }
    if (this.loadingProgressInterval) {
      clearInterval(this.loadingProgressInterval);
      this.loadingProgressInterval = null;
    }
    if (complete) {
      this.loadingPercent = 100;
      this.cdr.detectChanges();
    } else {
      this.loadingPercent = 0;
    }
  }

  // 计算文件夹大小是否超过限制
  isTotalSizeExceeded(files: any){
    let totalSize = 0;
    for (let i = 0; i < files.length; i++) {
        totalSize += files[i].size;
        // 累计超过限制时立即返回 true
        if (totalSize > environment.MaxSize) {
            return true;
        }
    }
    return false;
  }

  // 上传文件前，重置参数
  resetUpload(){
    this.total_size_exceed = false
  }

  onFolderSelect(event: Event) {
    this.resetUpload()
    const files = (event.target as HTMLInputElement).files;
    if (!files || files.length == 0) return;
    if (this.isTotalSizeExceeded(files)) {
      this.total_size_exceed = true
      return;
  }
    this.is_uploading_folder = true
    const entries: Zippable = {};
    const filePromises = this.readFiles(entries, files);
    const upload_dir = files[0].webkitRelativePath.split('/')[0];
    this.createZipAndUpload(entries, filePromises, upload_dir);
  }

  onZipSelect(event: Event) {
    this.resetUpload()
    const files = (event.target as HTMLInputElement).files;
    if (files == null || files.length == 0) return;
    // 只处理第一个文件（单文件上传）
    const file = files[0];
    this.totalSize = file.size;

    // 重置进度信息
    this.filesProgress = {};
    this.fileUploadProgressSize = 0;
    this.fileUploadProgressPercentage = 0;
    if (this.totalSize > environment.MaxSize){
      this.total_size_exceed = true
      return;
    }else if (this.totalSize > environment.Big_File_Info) {
      this.showToast("warning", "您上传的压缩包较大(超过500MB),处理可能需要一些时间,请耐心等待");
    }
    this.is_uploading_zip = true;
    // 上传单个文件
    this.uploadFileInChunks(file).then(() => {}).catch(error => {
      console.error(`文件上传失败:`, error);
      this.plxMessage.error(`文件上传失败`, "");
    }).finally(() => {
      // 无论成功还是失败，都会执行
      this.is_uploading_zip = false;
    });;
  }

  resetZipInput(){
    if (this.zipInputRef?.nativeElement) {
      this.zipInputRef.nativeElement.value = '';
    }
  }

  submit(){
    // 新增响应式表单校验功能
    if (this.uploadForm.invalid) {
      if (this.uploadForm.hasError('taskNameRequired')) {
        this.plxMessage.warning('任务名称不能为空', "");
      } else if (this.uploadForm.hasError('pythonInterpreterRequired')) {
        this.plxMessage.warning('Python解释器不能为空', "");
      } else if (this.uploadForm.hasError('goInstallPathRequired')) {
        this.plxMessage.warning('Go安装路径不能为空', "");
      } else {
        this.plxMessage.warning('请补充完整信息...', "");
      }
      return;
    }
    if (this.is_uploading_folder){
      this.plxMessage.warning('文件夹正在上传...', "")
      return
    }
    if (this.is_uploading_zip){
      this.plxMessage.warning('压缩包正在上传...', "")
      return
    }
    if (this.upload_file_info_lists == null || this.upload_file_info_lists.length == 0){
      this.plxMessage.warning('请上传文件夹或压缩包', "")
      return
    }
    const formValue = this.uploadForm.value;
    this.plxGlobalLoading.open(this.textLoadingTemp, 0)
    this.plxMessage.success('正在处理中...', "")
    // 启动进度更新
    this.startLoadingProgress();
    let body: any = {
      "user_name": this.user_name,
      "task_name": formValue.taskName,
      "upload_file_info_lists": this.upload_file_info_lists
    }
    if (formValue.scanDependencies == 'yes'){
      body.scan_dependencies = formValue.scanDependencies
      body.dependencies = formValue.dependencies
      if (formValue.dependencies == 'python'){
        body.python_interpreter = formValue.pythonInterpreter
        body.python_image_source = formValue.pythonImageSource
      }else if (formValue.dependencies == 'go'){
        body.go_install_path = formValue.goInstallPath
        body.go_environment = formValue.goEnvironment
      }
    }else{
      body.scan_dependencies = formValue.scanDependencies
    }
    this.codeMigApi.createMigTask(body).subscribe({
      next: (response: any) => {
        // 停止进度更新，任务完成时设置为100%
        this.stopLoadingProgress(true);
        if (response.code == 0){
          this.plxMessage.success('创建成功', "")
          this.router.navigate(['/codemig/task'], { queryParams: { task_id: response.task_id } });
        }
        this.plxGlobalLoading.close()
      },
      error: (errorResponse: any) => {
        // 停止进度更新，出错时重置为0
        this.stopLoadingProgress(false);
        this.plxGlobalLoading.close()
        console.log("Error: ", errorResponse);
      }
    });
  }

  deleteFolder(uploadedFolder:any){
    const key = Object.keys(uploadedFolder)[0];
    const value = uploadedFolder[key];
    const body = {
      user_name: this.user_name,
      dir_id: value
    }
    this.codeMigApi.deleteFolder(body).subscribe({
      next: (response: any) => {
        if (response.code == 0){
          this.plxMessage.success('移除文件夹成功', "")
          this.upload_file_info_lists = this.upload_file_info_lists.filter(
            ([currentDirId, _]) => currentDirId !== value
          );
          this.uploadedFolders = this.uploadedFolders.filter(
            item => JSON.stringify(item) !== JSON.stringify(uploadedFolder)
          );
          this.resetZipInput()
        }
      },
      error: (errorResponse: any) => {
        console.log("Error: ", errorResponse);
      }
    });
  }

  getKey(uploadedFolder: { [key: string]: number | null }): string {
    return Object.keys(uploadedFolder)[0];
  }

  readFiles(entries: Zippable, files: any) {
    return Array.from(files).map((file: any) => {
      return new Promise<void>((resolve, reject) => {
        // 创建一个新的 Promise
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const file_content = e.target.result;
          entries[file.webkitRelativePath || file.name] =
            typeof file_content === 'string'
              ? strToU8(file_content)
              : new Uint8Array(file_content as ArrayBuffer);

          resolve(); // 文件读取完成，调用 resolve，表示异步操作成功
        };
        reader.onerror = reject; // 如果文件读取出错，调用 reject，表示异步操作失败
        if (file.type.startsWith('text/')) {
          reader.readAsText(file); // 文本文件
        } else {
          reader.readAsArrayBuffer(file); // 二进制文件
        }
      });
    });
  }

  createFormDataBody(zip_content: Blob) {
    const formData = new FormData();
    formData.append('file', zip_content, 'upload.zip');
    formData.append('user_name', this.user_name);
    return formData;
  }

  uploadFile(zip_content: Blob): void {
    const formData = this.createFormDataBody(zip_content);
    this.codeMigApi.uploadFolder(formData).subscribe({
      next: (response: any) => {
        if (response.code == 0) {
          const lastFolder = this.uploadedFolders[this.uploadedFolders.length - 1];
          lastFolder[this.getKey(lastFolder)] = response.dir_id;
          this.upload_file_info_lists.push([response.dir_id, 'upload.zip'])
          this.is_uploading_folder = false
          this.resetZipInput()
          this.plxMessage.success("文件上传成功", "")
        } else {
          this.uploadedFolders.pop();
          console.error('Error backend: ', response);
        }
      },
      error: (errorResponse: any) => {
        console.error('Error uploading the files: ', errorResponse);
      },
    });
  }

  createZipAndUpload(entries: Zippable, filePromises: any, upload_dir: string)  {
    // 等待所有文件都读取完毕后再生成 zip 文件
    Promise.all(filePromises)
      .then(() => {
        this.uploadedFolders.push({ [upload_dir]: null });
        const zipped: Uint8Array = zipSync(entries);
        const zip_content = new Blob([zipped as BlobPart], { type: 'application/zip' });
        this.uploadFile(zip_content);
      })
      .catch((error) => {
        console.error('Error reading files:', error);
      });
  }

  async uploadFileInChunks(file: File): Promise<void> {
    const totalChunks = Math.ceil(file.size / environment.CHUNK_SIZE);
    const relativePath = file.webkitRelativePath || file.name;

    // 重置当前文件进度
    this.filesProgress[file.name] = 0;

    // 创建分块数组 [0, 1, 2, ..., totalChunks-1]
    const chunkIndexes = Array.from({ length: totalChunks }, (_, i) => i);

    // 分批上传 (控制并发)
    while (chunkIndexes.length > 0) {
      const currentBatch = chunkIndexes.splice(0, environment.MAX_CONCURRENT_UPLOADS);
      await Promise.all(
        currentBatch.map(chunkIndex =>
          this.uploadChunk(file, chunkIndex, totalChunks, relativePath)
        )
      );
    }
  }

  async uploadChunk(
    file: File,
    chunkIndex: number,
    totalChunks: number,
    relativePath: string,
  ): Promise<void> {
    const start = chunkIndex * environment.CHUNK_SIZE;
    const end = Math.min(file.size, start + environment.CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);

    // 计算当前块的大小
    const chunkSize = end - start;

    const formData = new FormData();
    formData.append('file', chunkBlob, file.name);
    formData.append('current_chunk_idx', chunkIndex.toString());
    formData.append('total_chunk_size', totalChunks.toString());
    formData.append('file_name', file.name);
    formData.append('relativePath', relativePath);
    formData.append('user_name', this.user_name);

    try {
      const response: any = await lastValueFrom(
        this.codeMigApi.uploadZip(formData)
      );

      // 更新上传进度
      this.filesProgress[file.name] = (this.filesProgress[file.name] || 0) + chunkSize;
      this.updateProgress(file);
      // 如果是最后一个分块，处理完成响应
      if (response.code == 0 && response.dir_id != -1) {
        this.handleUploadCompletion(file, response.dir_id);
      }
    } catch (error) {
      console.error(`分块 ${chunkIndex} 上传失败:`, error);
      this.plxMessage.error(`分块 ${chunkIndex} 上传失败:`, "");
    }
  }

  handleUploadCompletion(file: File, dir_id: number): void {
    this.is_uploading_zip = false;
    this.fileUploadProgressPercentage = 100;
    this.cdr.detectChanges();
    this.upload_file_info_lists.push([dir_id, file.name]);
    this.uploadedFolders.push({ [file.name]: dir_id });
    this.resetZipInput()
    this.plxMessage.success(`压缩包 分块${file.name} 上传成功`, "");
  }

  updateProgress(file: File): void {
    // 获取当前已上传大小
    const uploadedSize = this.filesProgress[file.name] || 0;

    // 计算当前文件进度百分比
    const fileProgress = Math.min((uploadedSize / file.size) * 100, 100)
    // 更新全局进度统计
    this.fileUploadProgressSize = uploadedSize;
    this.fileUploadProgressPercentage = +fileProgress.toFixed(2);

    this.cdr.detectChanges();
  }
}
