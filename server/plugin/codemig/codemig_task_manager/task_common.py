import os
import sys
from enum import Enum

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# pylint: disable=too-few-public-methods
class TaskStatus(Enum):
    CREATED = 0
    PROCESSING = 1
    SUCCESS = 2
    FAILED = 3
    DELETED = 4

# pylint: disable=too-few-public-methods
class TaskDependenceStatus(Enum):
    CREATED = 0
    PROCESSING = 1
    SUCCESS = 2
    FAILED = 3

# pylint: disable=too-few-public-methods
class DependencePackagesStatus(Enum):
    FAILED = 0
    SUCCESS = 1
