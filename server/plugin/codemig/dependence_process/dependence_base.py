"""
依赖处理公共基础模块
提供依赖安装和处理的公共流程和工具函数
"""
import sys

import multiprocessing
import os
from abc import ABC, abstractmethod

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.db.SQLOperation import db_session_scope, DatabaseException
from plugin.codemig.codemig_task_manager.task_common import TaskDependenceStatus
from plugin.codemig.dependence_process.dependence_sql import insert_task_dependence_update_status
from plugin.codemig.dependence_process.models import DependenceTask, DependencePackages
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.dependence_process.dependence_info import DepStatus

LOGGER = logger.init_log('codemig')


def update_task_dependence_status(task_id, dir_id, pkg_name, version_or_specs, status, dep_id):
    """
    更新任务依赖状态

    Args:
        task_id: 任务ID
        dir_id: 目录ID
        pkg_name: 包名
        version_or_specs: 版本号或规格说明（用于兼容不同语言）
        status: 状态（DepStatus枚举值）
        dep_id: 依赖ID
    """
    DependenceTask.update_task_status(task_id, dir_id, pkg_name, version_or_specs, status, dep_id)


class DependenceProcessor(ABC):
    """
    依赖处理器基类
    提供依赖安装和处理的公共流程
    """

    def __init__(self, config_name, config, to_process, task_id):
        """
        初始化依赖处理器

        Args:
            config_name: 配置名称（用于日志），如 "Go" 或 "Python"
            config: 配置参数（如 (python_path, mirror_url) 或 (go_path, go_env_str)）
            to_process: 待处理的依赖列表
            task_id: 任务ID
        """
        self.config_name = config_name
        self.config = config
        self.to_process = to_process
        self.task_id = task_id
        self.validated_config = ()

    @abstractmethod
    def validate_config(self, config):
        """
        验证配置（子类必须实现）

        Args:
            config: 配置参数（如 (python_path, mirror_url) 或 (go_path, go_env_str)）

        Returns:
            tuple: (is_valid: bool, validated_config or error_msg)
                - is_valid=True: 返回验证后的配置对象
                - is_valid=False: 返回错误消息字符串
        """
        pass

    @abstractmethod
    def _get_base_dir(self):
        """
        获取基础目录路径（子类必须实现）

        Returns:
            str: 基础目录路径
        """
        pass

    @abstractmethod
    def _should_check_installed(self, local_path):
        """
        判断是否需要检查包是否已安装（子类必须实现）

        Args:
            item: 待处理的包项（格式由子类定义）

        Returns:
            bool: 是否需要检查已安装
        """
        pass

    @abstractmethod
    def _extract_version_for_check(self, package, version):
        """
        提取版本号用于检查是否已安装（子类必须实现）

        Args:
            item: 待处理的包项（格式由子类定义）

        Returns:
            str or None: 版本号，如果无法提取则返回 None
        """
        pass

    @staticmethod
    @abstractmethod
    def install_single_package(dir_id, pkg, version, local_path, validated_config):
        """
        安装单个包（子类必须实现）

        Args:
            dir_id: 目录ID
            pkg: 包名
            version: 版本号或规格说明
            local_path: 本地路径
            validated_config: 验证后的配置

        Returns:
            tuple: (success: bool, msg: str, dep_id: int or None)
        """
        pass

    def _check_task_status(self):
        """
        检查任务状态

        Returns:
            tuple: (exists: bool, should_stop: bool)
                exists: 任务是否存在
                should_stop: 是否应该停止（任务不存在或status=4）
        """
        try:
            with db_session_scope() as session:
                task = session.query(CodemigTasks).filter(
                    CodemigTasks.task_id == self.task_id).first()

                if not task:
                    return False, True

                # status=4 表示 deleted
                if task.status == 4:
                    return True, True

                return True, False
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"检查任务状态失败: {e}", exc_info=True)
            # 发生异常时，为了安全起见，返回应该停止
            return False, True

    @staticmethod
    def _install_package_worker(args_dict):
        """
        在进程中安装包的静态工作函数（用于multiprocessing）

        Args:
            args_dict: 参数字典，包含所有必要的参数
                - dir_id: 目录ID
                - pkg: 包名
                - spec: 规格说明
                - local_path: 本地路径
                - base_dir: 基础目录
                - config_name: 配置名称
                - validated_config: 验证后的配置（需要是可序列化的）
                - processor_class: 处理器类名（字符串）
                - result_dict: Manager().dict() 用于返回结果
                - dependence_ids: Manager().list() 用于共享依赖ID列表

        Returns:
            None（结果通过result_dict返回）
        """
        local_logger = logger.init_log('codemig')

        try:
            # 直接调用传入的安装方法
            install_func = args_dict['install_func']
            success, msg, dep_id = install_func(
                args_dict['dir_id'],
                args_dict['pkg'],
                args_dict['spec'],
                args_dict['local_path'],
                args_dict['validated_config']
            )

            # 返回结果
            args_dict['result_dict']['success'] = success
            args_dict['result_dict']['msg'] = msg
            args_dict['result_dict']['dep_id'] = dep_id

        except (ValueError, AttributeError, OSError, IOError, RuntimeError) as e:
            local_logger.error(f"安装包时发生异常: {e}", exc_info=True)
            args_dict['result_dict']['success'] = False
            args_dict['result_dict']['msg'] = f"安装包时发生异常: {str(e)}"
            args_dict['result_dict']['dep_id'] = None

    def _process_packages(self):
        """
        处理包列表的公共流程

        Returns:
            list: dependence_ids 列表，格式为 [(dir_id, dependence_id), ...]
        """
        # 创建基础目录
        base_dir = self._get_base_dir()
        os.makedirs(base_dir, exist_ok=True)

        if not self.to_process:
            LOGGER.warning("警告: 没有找到需要下载的依赖")
            return []

        dependence_ids = []
        task_stopped = False
        for dir_id, pkg, spec, local_path, status, dep_id in self.to_process:

            # 如果状态不是 created，说明已经处理过，直接添加到 dependence_ids
            if status != DepStatus.created.value:
                dependence_ids.append((dir_id, dep_id))
                continue

            # 检查是否已安装
            if self._should_check_installed(local_path):
                version = self._extract_version_for_check(pkg, spec)
                if version:
                    dep = DependencePackages.is_package_installed(pkg, version)
                    if dep:
                        update_task_dependence_status(
                            self.task_id, dir_id, pkg,
                            spec,
                            DepStatus.finished, dep)
                        LOGGER.info(f"{pkg}_{version} 已安装，跳过")
                        dependence_ids.append((dir_id, dep))
                        continue

            # 在进程中安装包（使用multiprocessing以便可以强制终止）
            manager = multiprocessing.Manager()
            result_dict = manager.dict({'success': None, 'msg': None, 'dep_id': None})

            # 准备进程参数（需要可序列化）
            process_args = {
                'dir_id': dir_id,
                'pkg': pkg,
                'spec': spec,
                'local_path': local_path,
                'base_dir': base_dir,
                'config_name': self.config_name,
                'validated_config': self.validated_config,
                'install_func': self.__class__.install_single_package,
                'result_dict': result_dict,
            }

            install_process = multiprocessing.Process(
                target=self._install_package_worker,
                args=(process_args,),
                daemon=False  # 不使用daemon，以便可以控制终止
            )
            install_process.start()

            # 等待进程完成，每5秒检查一次任务状态

            while install_process.is_alive():
                install_process.join(timeout=5.0)

                # 检查任务状态
                _, should_stop = self._check_task_status()
                if should_stop:
                    LOGGER.warning(
                        f"任务 {self.task_id} 已删除或状态为deleted，强制终止安装包 {pkg} 的进程")
                    # 强制终止进程
                    install_process.terminate()
                    # 等待进程结束（最多等待5秒）
                    install_process.join(timeout=5.0)
                    # 如果进程仍在运行，强制杀死
                    if install_process.is_alive():
                        LOGGER.warning(f"安装包 {pkg} 的进程未能及时终止，强制杀死")
                        install_process.kill()
                        install_process.join()
                    # 标记为失败并设置停止标志
                    result_dict['success'] = False
                    result_dict['msg'] = "任务已删除或状态为deleted，安装已停止"
                    result_dict['dep_id'] = None
                    task_stopped = True
                    break

            # 获取安装结果
            success = result_dict.get('success')
            msg = result_dict.get('msg')
            dep_id = result_dict.get('dep_id')

            # 如果任务已停止，跳出整个循环
            if task_stopped:
                dependence_ids = []
                break
            if dep_id:
                dependence_ids.append((dir_id, dep_id))

            # 更新任务状态
            if success is False:
                update_task_dependence_status(self.task_id, dir_id, pkg, spec, DepStatus.failed,
                                              dep_id)
                LOGGER.warning(msg)
            elif success is True:
                update_task_dependence_status(self.task_id, dir_id, pkg, spec, DepStatus.finished,
                                              dep_id)

        return dependence_ids

    def process(self):
        """
        处理依赖的公共流程模板

        Returns:
            None
        """
        try:
            # 验证配置
            is_valid, validated_config_or_error = self.validate_config(self.config)
            if not is_valid:
                CodemigTasks.update_dependence_status(
                    self.task_id, TaskDependenceStatus.FAILED.value, validated_config_or_error)
                return

            # 执行安装
            dependence_ids = self._process_packages()

            # 更新任务状态
            if dependence_ids:
                insert_task_dependence_update_status(self.task_id, dependence_ids)
            else:
                CodemigTasks.update_dependence_status(
                    self.task_id, TaskDependenceStatus.SUCCESS.value, None)

        except (AttributeError, RuntimeError, ValueError, TypeError, OSError) as e:
            error_msg = f"处理{self.config_name}依赖时发生错误: {str(e)}"
            LOGGER.error(error_msg, exc_info=True)
            CodemigTasks.update_dependence_status(
                self.task_id, TaskDependenceStatus.FAILED.value, error_msg)
        finally:
            # 清理临时任务数据
            DependenceTask.delete_by_task_id(self.task_id)
