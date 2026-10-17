
import ctypes
from ctypes import CDLL, cdll

# 标准加载方式
libc = ctypes.CDLL("libc.so.6")
libc = ctypes.cdll.LoadLibrary("libc.so.6")