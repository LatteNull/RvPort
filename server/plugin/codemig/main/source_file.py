import os
import re
import sys
import magic
import chardet

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger

LOGGER = logger.init_log('codemig')


def is_text_file(file_path):
    try:
        if not os.path.exists(file_path):
            return True
        file_info = magic.from_file(file_path)

        text_types = ['text/', 'application/x-shellscript', 'application/x-sh']
        if 'shell' in file_info:
            if 'binary' in file_info:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    null_count = content.count(b'\x00')
                    if null_count > 0:
                        LOGGER.warning(f"{file_path}  警告: 发现空字符，可能包含二进制内容")
                    patterns = [
                        b'begin-base64',  # base64编码开始标记
                        b'begin [0-9]+',  # uuencode开始标记
                        b'\x1f\x8b',  # gzip魔数
                        b'\x50\x4b\x03\x04',  # ZIP魔数
                        b'\x7fELF',  # ELF可执行文件魔数
                        b'MZ',  # Windows PE可执行文件魔数
                    ]
                    for pattern in patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            LOGGER.warning(f'{file_path} has {pattern} content:{match.group()}')
                            return False
                LOGGER.warning(f'{file_path} seems like a binary  file')
                return False

            return True
        mime_type = magic.from_file(file_path, mime=True)
        return any(type in mime_type for type in text_types)

    except (OSError, IOError, PermissionError, FileNotFoundError, UnicodeError) as e:
        print(f"check file type error: {e}")
        return False


class SourceFile():

    def __init__(self, file_path):
        self.file_path = file_path
        self.code = None
        self.code_lines = None
        self.code_remove_c_comments = None
        self.code_remove_c_comments_lines = None
        self.code_remove_makefile_comments = None
        self.code_remove_multiple_comments = None
        self.code_remove_multiple_comments_lines = None

    def get_file_path(self):
        return self.file_path

    def get_code(self):
        if self.code is not None:
            return self.code

        try:
            with open(self.file_path, "rb") as file:
                raw_data = file.read()
            if not raw_data:
                return ''
            # 检测编码
            encoding_info = chardet.detect(raw_data)
            encoding = encoding_info['encoding']
            # confidence = encoding_info['confidence']
            content = ''
            try:
                if encoding.lower() in ['utf-8', 'utf-8-sig']:
                    content = raw_data.decode('utf-8-sig')  # 自动处理 BOM
                else:
                    content = raw_data.decode(encoding)
                # 移除可能的 BOM
                if content.startswith('\ufeff'):
                    content = content[1:]
            except (UnicodeDecodeError, AttributeError, LookupError):
                # 尝试其他编码
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        content = raw_data.decode(enc)
                        if content.startswith('\ufeff'):
                            content = content[1:]
                        break
                    except (UnicodeDecodeError, UnicodeError, LookupError):
                        continue
            self.code = content
            self.code = self.code.replace('\x0c', '').replace('\r\n', '\n').replace('\r', '\n')
            return self.code
        except (FileNotFoundError, OSError, PermissionError) as err:
            LOGGER.warning(f"Cannot find the target file: {self.file_path}, error: {err}.")
            return ''
        except (UnicodeError, UnicodeDecodeError):
            try:
                with open(self.file_path, "r", encoding='utf-8', errors='replace') as file:
                    self.code = file.read()
                    self.code = self.code.replace('\x0c', '')
                    return self.code
            except (UnicodeError, UnicodeDecodeError) as e2:
                LOGGER.error(
                    f"Error when processing the target file: {self.file_path}, error: {e2}.")
                raise

    def get_code_lines(self):
        if self.code_lines is None:
            self.code_lines = self.get_code().splitlines()
        return self.code_lines

    def _compute_remove_c_comments(self):
        """移除 C 语言风格的注释，并保持原始行号"""
        code = self.get_code()

        # 一次性处理所有情况的正则表达式
        pattern = r'''
            ("(?:\\.|[^"\\])*")|      # 双引号字符串
            ('(?:\\.|[^'\\])*')|      # 单引号字符
            (/\*[\s\S]*?\*/)|         # 多行注释
            (//[^\n]*)                # 单行注释
        '''

        def replacer(match):
            # 按组判断匹配类型
            if match.group(1):  # 双引号字符串
                return match.group(1)
            if match.group(2):  # 单引号字符
                return match.group(2)
            if match.group(3):  # 多行注释
                comment = match.group(3)
                return '\n' * comment.count('\n')
            if match.group(4):  # 单行注释
                return ''
            return match.group(0)

        return re.sub(pattern, replacer, code, flags=re.VERBOSE)

    def remove_c_comments(self):
        if self.code_remove_c_comments is None:
            self.code_remove_c_comments = self._compute_remove_c_comments()
        return self.code_remove_c_comments

    def remove_c_comments_lines(self):
        if self.code_remove_c_comments_lines is None:
            self.code_remove_c_comments_lines = self.remove_c_comments().splitlines()
        return self.code_remove_c_comments_lines

    def _compute_remove_multiple_comments(self):
        """ 移除 shell文件中单行以及多行注释，并保持原始行号 """
        if self.code is None:
            if not is_text_file(self.file_path):
                LOGGER.warning(f"The target file is not a text file: {self.file_path}.")
                self.code = ''
                return self.code
        code = self.get_code()
        # 处理多行注释:<<
        code = re.sub(r'^[ \t]*:<<[ \t]*([\'"]?)(\w+)\1[ \t]*\n.*?\n^\2[ \t]*$',
                      lambda m: '\n' * m.group().count('\n'),
                      code,
                      flags=re.DOTALL | re.MULTILINE)
        # 处理单行注释
        code = re.sub(r'#.*?$', ' ', code, flags=re.MULTILINE)
        return code

    def remove_multiple_comments_lines(self):
        if self.code_remove_multiple_comments is None:
            self.code_remove_multiple_comments = self._compute_remove_multiple_comments()

        if self.code_remove_multiple_comments_lines is None:
            self.code_remove_multiple_comments_lines = \
                self.code_remove_multiple_comments.splitlines()
        return self.code_remove_multiple_comments_lines

    def _remove_mkfile_comments(self):
        """ 删除 `#` 单行注释 """
        return re.sub(r'#.*?$', '', self.get_code(), flags=re.MULTILINE)

    def remove_makefile_comments(self):
        if self.code_remove_makefile_comments is None:
            self.code_remove_makefile_comments = self._remove_mkfile_comments().splitlines()
        return self.code_remove_makefile_comments
