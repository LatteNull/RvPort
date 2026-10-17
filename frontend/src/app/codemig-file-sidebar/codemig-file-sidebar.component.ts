import { Component, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Router } from '@angular/router';
import { TreeNode } from 'paletx';
import { Subscription, interval } from 'rxjs';
import { environment } from '../environment/environment';
import { CodeMigApi } from '../api/codemig-api.service';
import { CodemigFileSidebarService } from '../services/codemig-file-sidebar.service';

const SourceType = {
  ORIGINAL: "original",
  CHANGED: "changed",
  MISSING: "missing",
  GENERATED: "generated",
}

@Component({
  selector: 'app-codemig-file-sidebar',
  templateUrl: './codemig-file-sidebar.component.html',
  styleUrl: './codemig-file-sidebar.component.css',
  standalone: false,
})
export class CodemigFileSidebarComponent {
  @ViewChild('tree') tree: any;
  user_name: any;
  task_id: any;
  dir_id: any;
  file_id: any;
  dependence_id: any;
  public treeNodes: TreeNode[] = [];
  private subscription!: Subscription;
  // 保存展开状态的节点路径集合
  private expandedPaths: Set<string> = new Set<string>();
  // 当前任务ID，用于检测任务切换
  private currentTaskId: number | null = null;
  // 标记是否是第一次加载
  private isFirstLoad: boolean = true;
  private missingToGenerateMap = new Map<number, number>();
  private generateToMissingMap = new Map<number, number>();

  searchOptions = {
    show: true,
    ignoreCase: true,
  };

  constructor(
    private codeMigApi: CodeMigApi,
    private route: ActivatedRoute,
    private router: Router,
    private codemigFileSidebarService: CodemigFileSidebarService,
  ) {
    this.user_name = localStorage.getItem('user_name');
  }

  ngOnInit(): void {
    this.codemigFileSidebarService.refresh$.subscribe(() => {
      this.freshTreeNodes();
    });
    this.route.queryParams.subscribe((params: any) => {
      const newTaskId = Number(params['task_id']);
      const newDirId = Number(params['dir_id']);
      const newFileId = Number(params['file_id']);
      const newDependenceId = Number(params['dependence_id']);

      // 检查是否是任务切换（task_id 或 dir_id 变化）
      const isTaskChanged = this.currentTaskId !== null && 
                           (this.currentTaskId !== newTaskId || this.dir_id !== newDirId);

      // 如果任务ID变化，清空展开状态
      if (isTaskChanged) {
        this.expandedPaths.clear();
      }
      this.currentTaskId = newTaskId;

      // 更新路由参数
      this.task_id = newTaskId;
      this.dir_id = newDirId;
      this.file_id = newFileId;
      this.dependence_id = newDependenceId;

      // 第一次打开或任务切换时，刷新文件树
      if (this.isFirstLoad || isTaskChanged) {
        this.freshTreeNodes();
        this.isFirstLoad = false;
      } else {
        this.scrollToSelectedFile();
      }
    });
  }

  ngOnDestroy(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }


  freshTreeNodes() {
    // 如果没有必要的参数，不执行请求
    if (!this.task_id || !this.dir_id) {
      return;
    }

    let body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
    };
    if (this.dependence_id){
      body.dependence_id = this.dependence_id
      this.codeMigApi.getTaskDependenceFiletree(body).subscribe({
        next: (response: any) => {
          this.processFileTree(response.file_tree);
          this.tree.dataChanged();
          // 数据加载完成后，滚动到选中的文件
          setTimeout(() => {
            this.scrollToSelectedFile();
          }, 200);
        },
        error: (errorResponse: any) => {
          console.error('Error: ', errorResponse);
        },
      });
    }
    else{
      this.codeMigApi.getTaskFiletree(body).subscribe({
        next: (response: any) => {
          this.processFileTree(response.file_tree);
          this.tree.dataChanged();
          // 数据加载完成后，滚动到选中的文件
          setTimeout(() => {
            this.scrollToSelectedFile();
          }, 200);
        },
        error: (errorResponse: any) => {
          console.error('Error: ', errorResponse);
        },
      });
    }
  }

  /**
   * 获取节点的完整路径
   */
  private getNodePath(node: any): string | null {
    if (!node) {
      return null;
    }
    const findPath = (nodes: any[], targetNode: any, currentPath: string = ''): string | null => {
      if (!nodes || nodes.length === 0) {
        return null;
      }
      for (const n of nodes) {
        const nodePath = currentPath ? `${currentPath}/${n.label}` : n.label;
        if (n === targetNode) {
          return nodePath;
        }
        if (n.children && n.children.length > 0) {
          const found = findPath(n.children, targetNode, nodePath);
          if (found) {
            return found;
          }
        }
      }
      return null;
    };
    return findPath(this.treeNodes, node);
  }

  /**
   * 保存当前树的展开状态
   */
  private saveExpandedState(): void {
    this.expandedPaths.clear();
    const traverse = (nodes: any[], currentPath: string = '') => {
      if (!nodes || nodes.length === 0) {
        return;
      }
      for (const node of nodes) {
        const nodePath = currentPath ? `${currentPath}/${node.label}` : node.label;
        if (!node.isLeaf && node.isExpanded) {
          this.expandedPaths.add(nodePath);
        }
        if (node.children && node.children.length > 0) {
          traverse(node.children, nodePath);
        }
      }
    };
    traverse(this.treeNodes);
  }

  /**
   * 恢复树的展开状态
   */
  private restoreExpandedState(): void {
    if (this.expandedPaths.size === 0) {
      return;
    }
    const traverse = (nodes: any[], currentPath: string = '') => {
      if (!nodes || nodes.length === 0) {
        return;
      }
      for (const node of nodes) {
        const nodePath = currentPath ? `${currentPath}/${node.label}` : node.label;
        if (!node.isLeaf && this.expandedPaths.has(nodePath)) {
          node.isExpanded = true;
        }
        if (node.children && node.children.length > 0) {
          traverse(node.children, nodePath);
        }
      }
    };
    traverse(this.treeNodes);
  }

  /**
   * 处理文件树数据，构建层级目录结构
   * @param file_tree 文件树数据，格式：[(parent_path, [(task_id, dir_id, file_id, file_name), ...]), ...]
   */
  processFileTree(file_tree: any) {
    // 在重新构建树之前，保存当前展开状态
    if (this.treeNodes.length > 0) {
      this.saveExpandedState();
    }

    // 用于存储路径到节点的映射
    const pathToNodeMap = new Map<string, any>();
    const rootNodes: any[] = [];

    // 遍历所有文件数据
    for (let i = 0; i < file_tree.length; ++i) {
      const tree_node = file_tree[i];
      const parent_path = tree_node[0]; // 父路径
      const files = tree_node[1]; // 文件列表

      // 处理每个文件
      for (let j = 0; j < files.length; ++j) {
        const file = files[j];

        const task_id = file[0];
        const dir_id = file[1];
        const file_id = file[2];
        const file_name = file[3];
        const file_source = file.length > 4 ? file[4] : SourceType.ORIGINAL;
        const is_missing = file_source === SourceType.MISSING;
        const is_generate = file_source === SourceType.GENERATED;
        const is_file = file.length > 5 ? file[5] : false;

        // parent_path 可能是 './project/src' 这样的格式
        // file_name 是文件名，如 'main.c'
        // 需要构建完整路径：'./project/src/main.c'
        let full_path = '';
        if (parent_path === './' || parent_path === '' || parent_path === '.') {
          full_path = file_name;
        } else {
          // 确保 parent_path 以 '/' 结尾时去掉，避免双斜杠
          const normalized_parent = parent_path.endsWith('/') ? parent_path.slice(0, -1) : parent_path;
          full_path = `${normalized_parent}/${file_name}`;
        }

        // 分割路径为目录层级，过滤掉空字符串和 '.'
        // 注意：这里需要处理路径中可能包含的前缀（如 user_name/task_id/original）
        const path_parts = full_path.split('/').filter((part: string) => part && part !== '.');
        // 如果路径为空，跳过
        if (path_parts.length === 0) {
          continue;
        }

        // 构建目录树
        let current_path = '';
        let parent_node: any = null;

        for (let k = 0; k < path_parts.length; ++k) {
          let part = path_parts[k];
          current_path = current_path ? `${current_path}/${part}` : part;
          const is_leaf = (k === path_parts.length - 1) && is_file; // 最后一部分是文件
          const is_last_part = k === path_parts.length - 1;
          // 检查节点是否已存在
          let node = pathToNodeMap.get(current_path);

          if (!node) {
            // 创建新节点
            node = {
              label: part,
              isExpanded: false,  // 默认折叠状态
              children: [],
              isLeaf: is_leaf,
            };

            if (is_last_part) {
              // if (is_missing) {
              //   // 对于缺失文件，使用特殊标记
              //   node.label += '(缺失)';
              // }
              if (is_generate) {
                //与缺失文件路径相同，后端才提供source_file_id 与 file_id 一一对应
                node.source_file_id = file.length > 6 ? file[6] : 0; 
                if (node.source_file_id)
                  this.missingToGenerateMap.set(node.source_file_id, file_id);
                  this.generateToMissingMap.set(file_id, node.source_file_id);
              }

              node.task_id = task_id;
              node.dir_id = dir_id;
              node.file_id = file_id;
              node.dependence_id = this.dependence_id;
              node.file_path = current_path;
              node.isNodeSelected = this.isNodeSelected(task_id, dir_id, file_id);
              node.file_source = file_source;
              node.styleClass = this.getFileSourceStyleClass(file_source);
              node.nodeClass = this.getFileSourceStyleClass(file_source);
              node.key = this.getNodeKey(task_id, dir_id, current_path);
            }

            pathToNodeMap.set(current_path, node);

            // 添加到父节点的子节点列表
            if (parent_node) {
              if (!parent_node.children) {
                parent_node.children = [];
              }
              // 检查是否已存在，避免重复添加
              const exists = parent_node.children.some((child: any) => child === node);
              if (!exists) {
                parent_node.children.push(node);
              }
            } else {
              // 根节点
              // 检查是否已存在，避免重复添加
              const exists = rootNodes.some((root: any) => root === node);
              if (!exists) {
                rootNodes.push(node);
              }
            }
          } else {
            // 节点已存在
            if (!is_leaf && node.isLeaf) {
              // 如果之前被标记为叶子节点，现在需要改为目录节点
              node.isLeaf = false;
              if (!node.children) {
                node.children = [];
              }
            } else if (is_last_part) {
              // 如果是文件节点，更新文件信息（如果文件来源不同，可能需要更新样式）
              node.task_id = task_id;
              node.dir_id = dir_id;
              node.file_id = file_id;
              node.dependence_id = this.dependence_id;
              node.file_path = current_path;
              // 使用 dir_id 和 file_id 来判断文件是否选中
              node.isNodeSelected = this.isNodeSelected(task_id, dir_id, file_id);
              // 确保key已设置，使用 task_id、dir_id 和 current_path
              if (!node.key) {
                node.key = this.getNodeKey(task_id, dir_id, current_path);
              }
              // 如果文件来源不同，更新样式（changed 优先于 original）
              if (file_source === SourceType.CHANGED && node.file_source !== SourceType.CHANGED) {
                node.label = part;
                node.file_source = file_source;
                node.styleClass = this.getFileSourceStyleClass(file_source);
                node.nodeClass = this.getFileSourceStyleClass(file_source);
              } else if (!node.file_source) {
                node.label = part;
                node.file_source = file_source;
                node.styleClass = this.getFileSourceStyleClass(file_source);
                node.nodeClass = this.getFileSourceStyleClass(file_source);
              }
            }
          }
          parent_node = node;
        }
      }
    }

    // 对树节点进行排序：目录在前，文件在后，然后按名称排序
    const sortNodes = (nodes: any[]): void => {
      if (!nodes || nodes.length === 0) {
        return;
      }
      // 排序：目录在前（isLeaf为false），文件在后（isLeaf为true），然后按label排序
      nodes.sort((a, b) => {
        // 首先按类型排序：目录在前，文件在后
        if (a.isLeaf !== b.isLeaf) {
          return a.isLeaf ? 1 : -1;
        }
        // 相同类型，按名称排序（不区分大小写）
        const labelA = (a.label || '').toLowerCase();
        const labelB = (b.label || '').toLowerCase();
        return labelA.localeCompare(labelB);
      });
      // 递归排序子节点
      nodes.forEach(node => {
        if (node.children && node.children.length > 0) {
          sortNodes(node.children);
        }
      });
    };

    // 对根节点进行排序
    sortNodes(rootNodes);

    // 从叶子节点向上遍历，为目录节点设置样式
    // 如果目录下有 changed 或 missing 文件，目录也应该显示相应样式
    const updateDirectoryStyle = (node: any): string => {
      if (!node) {
        return SourceType.ORIGINAL;
      }
      // 如果是文件节点，直接返回其 file_source
      if (node.isLeaf) {
        return node.file_source || SourceType.ORIGINAL;
      }

      // 如果是目录节点，检查子节点的状态
      if (node.children && node.children.length > 0) {
        let hasChanged = false;
        let hasMissing = false;
        let hasGenerate = false;
        let hasOriginal = false;

        for (const child of node.children) {
          const childSource = updateDirectoryStyle(child);
          if (childSource === SourceType.CHANGED) {
            hasChanged = true;
          } else if (childSource === SourceType.MISSING) {
            hasMissing = true;
          } else if (childSource === SourceType.GENERATED) {
            hasGenerate = true;
          } else {
            hasOriginal = true;
          }
        }
        // 优先级：changed > missing > generate > original
        let dirSource = SourceType.ORIGINAL;
        if (hasChanged) {
          dirSource = SourceType.CHANGED;
        } else if (hasMissing) {
          dirSource = SourceType.MISSING;
        } else if (hasGenerate) {
          dirSource = SourceType.GENERATED;
        }
        // 为目录节点设置样式
        node.styleClass = this.getFileSourceStyleClass(dirSource);
        node.nodeClass = this.getFileSourceStyleClass(dirSource);
        return dirSource;
      }

      return node.file_source || SourceType.ORIGINAL;;
    };

    // 遍历所有根节点，更新目录样式
    rootNodes.forEach(node => {
      updateDirectoryStyle(node);
    });

    // 更新 treeNodes
    this.treeNodes = rootNodes;

    // 恢复之前保存的展开状态
    this.restoreExpandedState();
  }

  isNodeSelected(task_id: any, dir_id: any, file_id: any) {
    // 使用 dir_id 和 file_id 来唯一标识文件（包括 original 文件）
    return (
      task_id === this.task_id &&
      dir_id === this.dir_id &&
      file_id === this.file_id
    );
  }

  /**
   * 根据文件来源获取样式类名
   * @param file_source 文件来源：'original' | 'changed' | 'missing' | 'generate'
   * @returns 样式类名
   */
  getFileSourceStyleClass(file_source: string): string {
    switch (file_source) {
      case SourceType.CHANGED:
        return 'file-source-changed';
      case SourceType.MISSING:
        return 'file-source-missing';
      case SourceType.GENERATED:
        return 'file-source-generate';
      case SourceType.ORIGINAL:
      default:
        return 'file-source-original';
    }
  }

  updateLeafIfNeeded(child: any, leaf: any, isNodeSelected: any) {
    if (child.label !== leaf[3]) {
      child.label = leaf[3];
    }
    if (child.task_id !== leaf[0]) {
      child.task_id = leaf[0];
    }
    if (child.dir_id !== leaf[1]) {
      child.dir_id = leaf[1];
    }
    if (child.file_id !== leaf[2]) {
      child.file_id = leaf[2];
    }
    if (child.isNodeSelected !== isNodeSelected) {
      child.isNodeSelected = isNodeSelected;
    }
  }

  processTreeLeaf(treeNode: any, treeLeaf: any) {
    treeNode.children ||= [];
    let children = treeNode.children;
    for (let i = 0; i < treeLeaf.length; ++i) {
      const leaf = treeLeaf[i];
      const isNodeSelected = this.isNodeSelected(leaf[0], leaf[1], leaf[2]);
      if (i < children.length) {
        this.updateLeafIfNeeded(children[i], leaf, isNodeSelected);
      } else {
        children.push({
          label: leaf[3],
          task_id: leaf[0],
          dir_id: leaf[1],
          file_id: leaf[2],
          is_missing: leaf[4],
          dependence_id: this.dependence_id,
          isLeaf: true,
          isNodeSelected: isNodeSelected,
        });
      }
    }
    children.length = treeLeaf.length;
  }

  /**
   * 获取节点的唯一标识key
   * 使用 task_id、dir_id 和 current_path 来确定唯一标识
   */
  getNodeKey(task_id: any, dir_id: any, current_path: string): string {
    return `node_${task_id}_${dir_id}_${current_path}`;
  }

  /**
   * 滚动到选中的文件节点
   */
  scrollToSelectedFile(): void {
    if (!this.task_id || !this.dir_id || !this.file_id) {
      return;
    }

    if (!this.tree) {
      // 如果树还没有初始化，延迟重试
      setTimeout(() => {
        this.scrollToSelectedFile();
      }, 100);
      return;
    }

    let currentNode = null;
    let generateId = this.missingToGenerateMap.get(this.file_id);
    if(generateId){
      currentNode = this.getFileNode(generateId);
    }
    else{
      // 获取当前文件节点，使用其 file_path 来构建 key
      currentNode = this.getCurrentFileNode();
    }

    if (!currentNode || !currentNode.file_path) {
      return;
    }

    const nodeKey = this.getNodeKey(this.task_id, this.dir_id, currentNode.file_path);

    // 使用 Paletx Tree 的 doLocation 方法定位节点
    // 第二个参数 true 表示展开父节点
    try {
      this.tree.doLocation(nodeKey, true);
    } catch (error) {
      console.warn('定位节点失败:', error);
    }
  }

  /**
   * 获取所有文件节点
   */
  getAllNodes(): any[] {
    const allNodes: any[] = [];
    const traverse = (nodes: any[]) => {
      if (!nodes || nodes.length === 0) {
        return;
      }

      for (const node of nodes) {
        allNodes.push(node);
        // 递归处理子节点
        if (node.children && node.children.length > 0) {
          traverse(node.children);
        }
      }
    };

    traverse(this.treeNodes);
    return allNodes;
  }

  /**
   * 获取所有非original文件节点（changed或missing）
   */
  getNonOriginalFiles(): any[] {
    const nonOriginalFiles: any[] = [];
    
    const traverse = (nodes: any[]) => {
      if (!nodes || nodes.length === 0) {
        return;
      }
      
      for (const node of nodes) {
        if (node.isLeaf) {
          // 非original文件：file_source为'changed'或'missing'
          const fileSource = node.file_source || SourceType.ORIGINAL;
          if (fileSource === SourceType.CHANGED ||
              fileSource === SourceType.MISSING ||
              fileSource === SourceType.GENERATED) {
            nonOriginalFiles.push(node);
          }
        }
        else if (node.file_source === SourceType.MISSING ||
                 node.file_source === SourceType.GENERATED) {
          nonOriginalFiles.push(node);
        }
        
        // 递归处理子节点
        if (node.children && node.children.length > 0) {
          traverse(node.children);
        }
      }
    };
    
    traverse(this.treeNodes);
    return nonOriginalFiles;
  }

  /**
   * 获取当前文件节点
   */
  getCurrentFileNode(): any {
    if (!this.task_id || !this.dir_id || !this.file_id) {
      return null;
    }
    
    const allNodes = this.getAllNodes();
    // 使用 dir_id 和 file_id 来查找文件
    return allNodes.find(node => 
      node.task_id === this.task_id &&
      node.dir_id === this.dir_id &&
      node.file_id === this.file_id
    ) || null;
  }

  getFileNode(file_id: number): any {
    if (!this.task_id || !this.dir_id || !file_id) {
      return null;
    }
    
    const allNodes = this.getAllNodes();
    // 使用 dir_id 和 file_id 来查找文件
    return allNodes.find(node => 
      node.task_id === this.task_id &&
      node.dir_id === this.dir_id &&
      node.file_id === file_id
    ) || null;
  }

  /**
   * 判断当前文件是否是original文件
   */
  isCurrentFileOriginal(): boolean {
    const currentNode = this.getCurrentFileNode();
    if (!currentNode) {
      return false;
    }
    // original文件：file_source为'original'或未设置
    const fileSource = currentNode.file_source || SourceType.ORIGINAL;
    return fileSource === SourceType.ORIGINAL;
  }

  /**
   * 找到最近的changed或missing文件（向前或向后）
   */
  findNearestChangedFile(direction: 'previous' | 'next'): any {
    const allNodes = this.getAllNodes();
    const currentNode = this.getCurrentFileNode();
    
    if (!currentNode) {
      return null;
    }
    // 查找当前文件在列表中的索引 使用 dir_id 和 file_id 来匹配
    const currentIndex = allNodes.findIndex(node => {
        return node.task_id === currentNode.task_id &&
               node.dir_id === currentNode.dir_id &&
               node.file_id === currentNode.file_id;
    });
    
    if (currentIndex === -1) {
      return null;
    }
    
    // 查找changed或missing文件
    if (direction === 'previous') {
      // 向前查找
      for (let i = currentIndex - 1; i >= 0; i--) {
        const fileSource = allNodes[i].file_source || SourceType.ORIGINAL;
        if (fileSource === SourceType.CHANGED || 
            fileSource === SourceType.MISSING || 
            fileSource === SourceType.GENERATED) {
          return allNodes[i];
        }
      }
    } else {
      // 向后查找
      for (let i = currentIndex + 1; i < allNodes.length; i++) {
        const fileSource = allNodes[i].file_source || SourceType.ORIGINAL;
        if (fileSource === SourceType.CHANGED || 
            fileSource === SourceType.MISSING || 
            fileSource === SourceType.GENERATED) {
          return allNodes[i];
        }
      }
    }
    
    return null;
  }

  /**
   * 获取当前文件在非original文件列表中的索引
   */
  getCurrentFileIndex(): number {
    if (!this.task_id) {
      return -1;
    }
    
    const nonOriginalFiles = this.getNonOriginalFiles();
    // 对于 generate 文件， 使用 dir_id 和 generate_file_id 来匹配
    let generate_file_id = this.missingToGenerateMap.get(this.file_id);
    if (this.dir_id && generate_file_id){
      return nonOriginalFiles.findIndex(file => 
        file.task_id === this.task_id &&
        file.dir_id === this.dir_id &&
        file.file_id === generate_file_id
      );
    }
    // 对于 changed/missing 文件，使用 dir_id 和 file_id 来匹配
    if (this.dir_id && this.file_id) {
      return nonOriginalFiles.findIndex(file => 
        file.task_id === this.task_id &&
        file.dir_id === this.dir_id &&
        file.file_id === this.file_id
      );
    }
    return -1;
  }

  /**
   * 是否可以导航到上一个
   */
  canNavigatePrevious(): boolean {
    // 如果当前是original文件，检查是否有前面的changed文件
    if (this.isCurrentFileOriginal()) {
      const nearestChanged = this.findNearestChangedFile('previous');
      return nearestChanged !== null;
    }
    
    // 否则按原来的逻辑
    const currentIndex = this.getCurrentFileIndex();
    return currentIndex > 0;
  }

  /**
   * 是否可以导航到下一个
   */
  canNavigateNext(): boolean {
    // 如果当前是original文件，检查是否有后面的changed文件
    if (this.isCurrentFileOriginal()) {
      const nearestChanged = this.findNearestChangedFile('next');
      return nearestChanged !== null;
    }
    
    // 否则按原来的逻辑
    const currentIndex = this.getCurrentFileIndex();
    const nonOriginalFiles = this.getNonOriginalFiles();
    return currentIndex >= 0 && currentIndex < nonOriginalFiles.length - 1;
  }

  /**
   * 导航到上一个非original文件
   */
  navigateToPrevious(): void {
    // 如果当前是original文件，找到最近的changed文件
    if (this.isCurrentFileOriginal()) {
      const nearestChanged = this.findNearestChangedFile('previous');
      if (nearestChanged) {
        this.navigateToFile(nearestChanged);
      }
      return;
    }
    
    // 否则按原来的逻辑：在非original文件列表中导航
    const currentIndex = this.getCurrentFileIndex();
    if (currentIndex <= 0) {
      return;
    }
    
    const nonOriginalFiles = this.getNonOriginalFiles();
    const previousFile = nonOriginalFiles[currentIndex - 1];
    
    if (previousFile) {
      this.navigateToFile(previousFile);
    }
  }

  /**
   * 导航到下一个非original文件
   */
  navigateToNext(): void {
    // 如果当前是original文件，找到最近的changed文件
    if (this.isCurrentFileOriginal()) {
      const nearestChanged = this.findNearestChangedFile('next');
      if (nearestChanged) {
        this.navigateToFile(nearestChanged);
      }
      return;
    }
    
    // 否则按原来的逻辑：在非original文件列表中导航
    const currentIndex = this.getCurrentFileIndex();
    const nonOriginalFiles = this.getNonOriginalFiles();
    
    if (currentIndex < 0 || currentIndex >= nonOriginalFiles.length - 1) {
      return;
    }
    
    const nextFile = nonOriginalFiles[currentIndex + 1];
    
    if (nextFile) {
      this.navigateToFile(nextFile);
    }
  }

  /**
   * 导航到指定文件
   */
  private navigateToFile(file: any): void {
    if (!file || !file.task_id) {
      return;
    }

    // 检测当前路由是否是一键迁移视图
    const currentUrl = this.router.url.split('?')[0]; // 移除查询参数
    if (currentUrl.includes('migrate_project')) {
      // 一键迁移视图：复用子组件内部的 onFileClick，不要触发 router.navigate。
      // 原因：路由 reuse:false，router.navigate 会销毁并重建子组件，
      //       ngOnDestroy -> cancelRequest -> SSE 中断 + 后台 Docker 容器停止。
      this.codemigFileSidebarService.notifyMigrateNavigate({
        file_id: file.file_id,
      });
      return;
    }

    let params: any = {
      task_id: file.task_id,
      dir_id: file.dir_id,
      file_id: file.file_id,
    };
    
    if (this.dependence_id) {
      params.dependence_id = this.dependence_id;
    }
    
    let source_file_id = this.generateToMissingMap.get(file.file_id);
    if (source_file_id){
      params.source_file_id = source_file_id;
    }

    const fileSource = file.file_source || SourceType.ORIGINAL;
    let targetPath = '/filechange/view';
    switch (fileSource) {
      case SourceType.GENERATED:
      case SourceType.MISSING:
        targetPath = '/filechange/generate';
        break;
      case SourceType.CHANGED:
      case SourceType.ORIGINAL:
      default:
        targetPath = '/filechange/view';
    }

    this.router.navigate([targetPath], { queryParams: params });
  }

  /**
   * 修改指定节点的折叠状态，不影响其他节点
   * @param node 要修改的节点
   * @param expanded 是否展开（true=展开，false=折叠，undefined=切换）
   */
  toggleNodeExpanded(node: any, expanded?: boolean): void {
    if (!node || node.isLeaf) {
      // 叶节点不能折叠
      return;
    }

    // 获取节点路径，用于更新保存的状态
    const nodePath = this.getNodePath(node);

    // 只修改当前节点的状态
    const newExpandedState = expanded === undefined ? !node.isExpanded : expanded;
    node.isExpanded = newExpandedState;

    // 更新保存的展开状态
    if (nodePath) {
      if (newExpandedState) {
        this.expandedPaths.add(nodePath);
      } else {
        this.expandedPaths.delete(nodePath);
      }
    }

    // 通知树组件更新视图（只更新当前节点，不影响其他节点）
    if (this.tree) {
      this.tree.dataChanged();
    }
  }

  click(node: any) {
    // 如果是missing生成的文件目录，则展开节点并导航到生成文件页面。 注：如果是文件则不需要额外调整，只针对目录
    if (node.file_source === SourceType.GENERATED && !node.isLeaf) {
      this.toggleNodeExpanded(node);
      this.navigateToFile(node);
      return;
    }
    if ((!node.isLeaf) && (node.file_source !== SourceType.MISSING)) {
      // 使用专门的方法修改节点折叠状态，只影响当前节点
      this.toggleNodeExpanded(node);
      return;
    }
    this.navigateToFile(node);
  }

  /**
   * 获取当前节点的父目录路径（用于新建文件/目录）
   */
  private getParentDirectoryPath(): string {
    const currentNode = this.getSelectedNode();
    if (currentNode) {
      const nodePath = this.getNodePath(currentNode);
      if (nodePath) {
        // 移除节点标签中的状态标记（如"(缺失)"）
        let cleanPath = nodePath.replace(/\(缺失\)$/, '');
        
        // 如果是文件，返回其父目录路径
        if (currentNode.isLeaf) {
          const lastSlashIndex = cleanPath.lastIndexOf('/');
          if (lastSlashIndex > 0) {
            return cleanPath.substring(0, lastSlashIndex);
          } else if (lastSlashIndex === 0) {
            return '';
          } else {
            // 没有斜杠，说明是根目录下的文件
            return '';
          }
        } else {
          // 如果是目录，返回目录本身
          return cleanPath;
        }
      }
    }
    // 如果没有当前节点，返回根目录（空字符串表示根目录）
    return '';
  }

  /**
   * 新建文件
   */
  createNewFile(): void {
    const parentPath = this.getParentDirectoryPath();
    const fileName = prompt('请输入文件名：');
    
    if (!fileName || !fileName.trim()) {
      return;
    }
    
    const filePath = parentPath ? `${parentPath}/${fileName.trim()}` : fileName.trim();
    
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_path: filePath,
      is_directory: false
    };
    
    if (this.dependence_id) {
      console.error(`创建文件失败: 依赖包不支持创建文件或目录`);
      alert(`创建文件失败，依赖包不支持创建文件或目录`);
      return;
    }
    
    this.codeMigApi.createFileOrDirectory(body).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          // 刷新文件树
          this.freshTreeNodes();
        } else {
          alert(`创建文件失败: ${response.msg || '未知错误'}`);
        }
      },
      error: (error: any) => {
        console.error('创建文件失败:', error);
        alert('创建文件失败，请稍后重试');
      }
    });
  }

  /**
   * 新建目录
   */
  createNewDirectory(): void {
    const parentPath = this.getParentDirectoryPath();
    const dirName = prompt('请输入目录名：');
    
    if (!dirName || !dirName.trim()) {
      return;
    }
    
    const dirPath = parentPath ? `${parentPath}/${dirName.trim()}` : dirName.trim();
    
    const body: any = {
      user_name: this.user_name,
      task_id: this.task_id,
      dir_id: this.dir_id,
      file_path: dirPath,
      is_directory: true
    };
    
    if (this.dependence_id) {
      console.error(`创建目录失败: 依赖包不支持创建文件或目录`);
      alert(`创建目录失败，依赖包不支持创建文件或目录`);
      return;
    }
    
    this.codeMigApi.createFileOrDirectory(body).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          // 刷新文件树
          this.freshTreeNodes();
        } else {
          alert(`创建目录失败: ${response.msg || '未知错误'}`);
        }
      },
      error: (error: any) => {
        console.error('创建目录失败:', error);
        alert('创建目录失败，请稍后重试');
      }
    });
  }

  /**
   * 获取选中的节点（文件或目录）
   */
  getSelectedNode(): any {
    // 先尝试获取当前文件节点
    const currentFileNode = this.getCurrentFileNode();
    if (currentFileNode && currentFileNode.isNodeSelected) {
      return currentFileNode;
    }
    
    // 如果当前文件节点不存在或未选中，遍历树查找选中的节点
    const findSelectedNode = (nodes: any[]): any => {
      if (!nodes || nodes.length === 0) {
        return null;
      }
      for (const node of nodes) {
        if (node.isNodeSelected) {
          return node;
        }
        if (node.children && node.children.length > 0) {
          const found = findSelectedNode(node.children);
          if (found) {
            return found;
          }
        }
      }
      return null;
    };
    
    return findSelectedNode(this.treeNodes);
  }

  /**
   * 判断是否可以删除
   */
  canDelete(): boolean {
    if (this.dependence_id) {
      return false;
    }

    const selectedNode = this.getSelectedNode();
    if (!selectedNode) {
      return false;
    }

    // 能删除changed generate的文件/目录，不能删除original或missing文件/目录
    const fileSource = selectedNode.file_source || SourceType.ORIGINAL;
    return fileSource === SourceType.CHANGED || fileSource === SourceType.GENERATED;
  }

  /**
   * 判断是否可以创建文件
   */
  canCreateFile(): boolean {
    if (this.dependence_id) {
      return false;
    }
    return true;
  }

  /**
   * 判断是否可以创建目录
   */
  canCreateDirectory(): boolean {
    if (this.dependence_id) {
      return false;
    }
    return true;
  }
  /**
   * 删除当前节点（文件或目录）
   */
  deleteCurrentNode(): void {
    const selectedNode = this.getSelectedNode();
    if (!selectedNode) {
      alert('请先选择一个文件或目录');
      return;
    }
    
    // 检查是否可以删除
    if (!this.canDelete()) {
      alert('只能删除已修改的文件/目录，不能删除原始或缺失文件/目录');
      return;
    }

    // 获取节点名称（移除状态标记）
    let nodeName = selectedNode.label || '';
    nodeName = nodeName.replace(/\(缺失\)$/, '');
    const nodeType = selectedNode.isLeaf ? '文件' : '目录';
    const confirmMessage = `确定要删除${nodeType} "${nodeName}" 吗？`;
    
    if (!confirm(confirmMessage)) {
      return;
    }
    
    const body: any = {
      user_name: this.user_name,
      file_id: selectedNode.file_id,
      dir_id: selectedNode.dir_id,
    };
    
    if (this.dependence_id) {
      console.error(`删除${nodeType}失败: 依赖包不支持删除文件或目录`);
      alert(`删除${nodeType}失败，依赖包不支持删除文件或目录`);
      return;
    }
    
    this.codeMigApi.deleteFileOrDirectory(body).subscribe({
      next: (response: any) => {
        if (response.code === 0) {
          // 刷新文件树
          this.freshTreeNodes();
        } else {
          alert(`删除${nodeType}失败: ${response.msg || '未知错误'}`);
        }
      },
      error: (error: any) => {
        console.error(`删除${nodeType}失败:`, error);
        alert(`删除${nodeType}失败，请稍后重试`);
      }
    });
  }

  /**
   * 全部折叠
   */
  collapseAll(): void {
    const collapse = (nodes: any[]) => {
      if (!nodes || nodes.length === 0) {
        return;
      }
      for (const node of nodes) {
        if (!node.isLeaf && node.isExpanded) {
          node.isExpanded = false;
        }
        if (node.children && node.children.length > 0) {
          collapse(node.children);
        }
      }
    };
    
    collapse(this.treeNodes);
    this.expandedPaths.clear();
    
    // 通知树组件更新视图
    if (this.tree) {
      this.tree.dataChanged();
    }
  }
}