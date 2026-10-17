from enum import Enum


# pylint: disable=too-few-public-methods
class DependenceInfo:
    def __init__(self, scan, lang=None, python=None, python_config=None, go=None, go_config=None):
        self.scan = scan
        self.lang = lang
        self.python = python
        self.python_config = python_config
        self.go = go
        self.go_config = go_config


# pylint: disable=too-few-public-methods
class DepStatus(Enum):
    created = 0
    failed = 1
    finished = 2


DOWNLOAD_TIMEOUT = 10800
