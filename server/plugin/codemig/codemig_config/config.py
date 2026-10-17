import json
import os
import sys
from threading import Lock

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public.public import ROOT_PATH


class ConfigManager:
    _instance = None
    enable_dependence = False
    _lock = Lock()
    _initialized = False

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    config_file_path = os.path.join(ROOT_PATH, 'server', "config.json")
                    try:
                        with open(config_file_path, "r", encoding='utf-8') as config_file:
                            config = json.load(config_file)
                            enable = config.get("enable_dependence", "False")
                            self.enable_dependence = enable.lower() == "true"
                    except (FileNotFoundError, IOError, PermissionError, OSError) as e:
                        print(f"警告: 配置文件异常: {config_file_path}：{str(e)}")
                        self.enable_dependence = False
                    except json.JSONDecodeError:
                        print(f"错误: 配置文件格式错误: {config_file_path}")
                        self.enable_dependence = False
                    self.__class__._initialized = True

    @classmethod
    def _get_instance(cls):
        """获取单例实例（内部方法）"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_enable_dependence(cls, enable):
        instance = cls._get_instance()
        instance.enable_dependence = enable

    @classmethod
    def get_enable_dependence(cls) -> bool:
        """获取依赖启用状态"""
        instance = cls._get_instance()
        return instance.enable_dependence
