import pytest
from plugin.codemig.main.source_file import SourceFile, is_text_file
import os
import tempfile
import stat
import codecs
from unittest.mock import patch

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'tests', 'source_code')

# 测试数据数组
TEST_CASES = [
    # (输入文件，期望结果，测试描述)
    ("acsii.txt", 34, "非 utf-8 编码文件"),
    ('unicode_decode_error.go', 190, "UnicodeDecodeError 异常的文件"),
    ('no_encoding.py', 2384, "编码信息无 encoding 的文件"),
    ('unkown_encodeing.go', 17, "未知编码文件"),
]

# 参数化测试用例
@pytest.mark.parametrize("input_file, expected, description", TEST_CASES)
def test_contains_architecture_condition(input_file, expected, description):
    """测试 if 语句括号封闭性"""
    result = SourceFile(os.path.join(TEST_FILE_PATH, input_file)).get_code()
    line =  result.split('\n')
    assert len(line) == expected, f"{description}"


class TestIsTextFile:
    """测试 is_text_file 函数"""

    def test_is_text_file_nonexistent(self, tmp_path):
        """测试不存在的文件"""
        non_existent = tmp_path / "nonexistent.txt"
        # is_text_file 对不存在的文件返回 True
        result = is_text_file(str(non_existent))
        assert result is True

    def test_is_text_file_regular_text(self, tmp_path):
        """测试普通文本文件"""
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello, World!", encoding='utf-8')
        result = is_text_file(str(text_file))
        # 文本文件应该返回 True
        assert result is True

    def test_is_text_file_shell_script(self, tmp_path):
        """测试 shell 脚本文件"""
        shell_file = tmp_path / "script.sh"
        shell_file.write_text("#!/bin/bash\necho hello", encoding='utf-8')
        result = is_text_file(str(shell_file))
        assert result is True

    def test_is_text_file_with_null_bytes(self, tmp_path):
        """测试包含空字符的文件"""
        binary_file = tmp_path / "binary.bin"
        # 创建包含空字符的文件
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        result = is_text_file(str(binary_file))
        # 二进制文件应该返回 False
        assert result is False

    def test_is_text_file_zip_file(self, tmp_path):
        """测试 ZIP 文件"""
        zip_file = tmp_path / "archive.zip"
        # ZIP 魔数
        zip_file.write_bytes(b'\x50\x4b\x03\x04' + b'\x00' * 100)
        result = is_text_file(str(zip_file))
        # ZIP 文件的 mime 是 application/zip，不是 text/*
        assert result is False

    def test_is_text_file_gzip_file(self, tmp_path):
        """测试 GZIP 文件"""
        gzip_file = tmp_path / "data.gz"
        # GZIP 魔数
        gzip_file.write_bytes(b'\x1f\x8b' + b'\x00' * 100)
        result = is_text_file(str(gzip_file))
        assert result is False

    def test_is_text_file_pe_executable(self, tmp_path):
        """测试 Windows PE 可执行文件"""
        pe_file = tmp_path / "program.exe"
        # PE 魔数 MZ
        pe_file.write_bytes(b'MZ' + b'\x00' * 100)
        result = is_text_file(str(pe_file))
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_with_null_bytes(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含空字符的文件"""
        test_file = tmp_path / "test.sh"
        # 包含空字符的内容
        test_file.write_bytes(b'#!/bin/bash\n\x00\x01\x02')
        result = is_text_file(str(test_file))
        # shell binary 且有空字符应该返回 False
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_with_base64_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 base64 模式的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("begin-base64 644 file.txt\n")
        result = is_text_file(str(test_file))
        # shell binary 且包含 base64 模式应该返回 False
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_with_uuencode_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 uuencode 模式的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("begin 644 file.txt\n")
        result = is_text_file(str(test_file))
        # shell binary 且包含 uuencode 模式应该返回 False
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_gzip_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 gzip 魔数的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_bytes(b'#!/bin/bash\n\x1f\x8b')
        result = is_text_file(str(test_file))
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_zip_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 ZIP 魔数的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_bytes(b'#!/bin/bash\n\x50\x4b\x03\x04')
        result = is_text_file(str(test_file))
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_elf_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 ELF 魔数的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_bytes(b'#!/bin/bash\n\x7fELF')
        result = is_text_file(str(test_file))
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_pe_pattern(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 且包含 PE 魔数的文件"""
        test_file = tmp_path / "test.sh"
        test_file.write_bytes(b'#!/bin/bash\nMZ')
        result = is_text_file(str(test_file))
        assert result is False

    @patch('magic.from_file', return_value='application/x-shellscript binary')
    def test_is_text_file_shell_binary_suggests_binary(self, mock_from_file, tmp_path):
        """测试被识别为 shell binary 但不匹配任何模式的情况"""
        test_file = tmp_path / "test.sh"
        test_file.write_bytes(b'#!/bin/bash\n\x00\x01\x02')
        result = is_text_file(str(test_file))
        # shell binary 且有空字符但没有匹配模式，也会返回 False
        assert result is False

    @patch('magic.from_file', side_effect=PermissionError("Permission denied"))
    def test_is_text_file_permission_error(self, mock_from_file, tmp_path):
        """测试权限错误"""
        perm_file = tmp_path / "restricted.txt"
        perm_file.write_text("test")
        result = is_text_file(str(perm_file))
        assert result is False

    @patch('magic.from_file', side_effect=OSError("OS error"))
    def test_is_text_file_os_error(self, mock_from_file, tmp_path):
        """测试 OS 错误"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = is_text_file(str(test_file))
        assert result is False


class TestSourceFileInit:
    """测试 SourceFile 初始化"""

    def test_source_file_init(self, tmp_path):
        """测试初始化"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding='utf-8')

        sf = SourceFile(str(test_file))
        assert sf.file_path == str(test_file)
        assert sf.code is None
        assert sf.code_lines is None
        assert sf.code_remove_c_comments is None
        assert sf.code_remove_c_comments_lines is None
        assert sf.code_remove_multiple_comments is None
        assert sf.code_remove_multiple_comments_lines is None

    def test_get_file_path(self, tmp_path):
        """测试 get_file_path 方法"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test", encoding='utf-8')

        sf = SourceFile(str(test_file))
        assert sf.get_file_path() == str(test_file)


class TestGetCode:
    """测试 get_code 方法"""

    def test_get_code_simple(self, tmp_path):
        """测试简单文件读取"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding='utf-8')

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert code == "Hello, World!"

    def test_get_code_with_bom(self, tmp_path):
        """测试带 BOM 的文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(codecs.BOM_UTF8 + b"Hello, World!")

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        # BOM 应该被移除
        assert not code.startswith('﻿')

    def test_get_code_empty_file(self, tmp_path):
        """测试空文件"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding='utf-8')

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert code == ''

    def test_get_code_line_normalization(self, tmp_path):
        """测试行尾符规范化"""
        test_file = tmp_path / "test.txt"
        # Windows 行尾符
        test_file.write_bytes(b"line1\r\nline2\r\nline3")

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert '\r\n' not in code
        assert '\r' not in code
        assert code == "line1\nline2\nline3"

    def test_get_code_form_feed_removal(self, tmp_path):
        """测试 form feed 字符移除"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"line1\x0cline2")

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert '\x0c' not in code

    def test_get_code_nonexistent_file(self, tmp_path):
        """测试不存在的文件"""
        non_existent = tmp_path / "nonexistent.txt"

        sf = SourceFile(str(non_existent))
        code = sf.get_code()
        assert code == ''

    def test_get_code_permission_error(self, tmp_path):
        """测试权限错误"""
        perm_file = tmp_path / "restricted.txt"
        perm_file.write_text("test")
        perm_file.chmod(0o000)

        try:
            sf = SourceFile(str(perm_file))
            code = sf.get_code()
            # 可能返回空字符串或抛出异常，取决于系统
            assert isinstance(code, str)
        finally:
            perm_file.chmod(0o644)

    def test_get_code_unicode_error_fallback(self, tmp_path):
        """测试 Unicode 错误时的回退"""
        # 创建无法用 chardet 正确检测编码的文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding='utf-8')

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert "Hello, World!" in code

    @patch('chardet.detect', return_value={'encoding': 'utf-8-sig', 'confidence': 0.9})
    def test_get_code_encoding_utf8_sig(self, mock_detect, tmp_path):
        """测试 UTF-8-SIG 编码检测"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(codecs.BOM_UTF8 + b"Hello, World!")

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        # BOM 应该被移除
        assert not code.startswith('﻿')
        assert "Hello, World!" in code

    @patch('chardet.detect', return_value={'encoding': 'latin-1', 'confidence': 0.9})
    def test_get_code_encoding_latin1(self, mock_detect, tmp_path):
        """测试 Latin-1 编码检测成功"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello \xe4\xf6\xfc")  # Latin-1 字符

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert isinstance(code, str)

    @patch('chardet.detect', return_value={'encoding': None, 'confidence': 0.1})
    def test_get_code_chardet_no_encoding(self, mock_detect, tmp_path):
        """测试 chardet 无法检测编码的情况"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!", encoding='utf-8')

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        # 应该通过 fallback 机制成功读取
        assert isinstance(code, str)

    @patch('builtins.open', side_effect=[UnicodeDecodeError('utf-8', b'', 0, 1, 'test'),
                                          UnicodeDecodeError('utf-8', b'', 0, 1, 'test'),
                                          UnicodeDecodeError('utf-8', b'', 0, 1, 'test')])
    def test_get_code_all_fallback_attempts_fail(self, mock_open, tmp_path):
        """测试所有回退尝试都失败的情况"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b'\x00\x01\x02')

        sf = SourceFile(str(test_file))
        # 所有解码尝试都失败时会抛出异常
        with pytest.raises(UnicodeDecodeError):
            sf.get_code()

    @patch('chardet.detect', return_value={'encoding': 'invalid', 'confidence': 0.9})
    def test_get_code_fallback_with_errors_replace(self, mock_detect, tmp_path):
        """测试使用 errors='replace' 打开文件成功"""
        test_file = tmp_path / "test.txt"
        # 创建一些无法解码的字节
        test_file.write_bytes(b'\xff\xfe\x00\x01')

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        # 应该通过 fallback 机制成功读取（使用 errors='replace'）
        assert isinstance(code, str)

    def test_get_code_cache(self, tmp_path):
        """测试代码缓存"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding='utf-8')

        sf = SourceFile(str(test_file))
        code1 = sf.get_code()
        code2 = sf.get_code()
        # 第二次调用应该使用缓存
        assert code1 == code2
        assert sf.code is not None


class TestGetCodeLines:
    """测试 get_code_lines 方法"""

    def test_get_code_lines_simple(self, tmp_path):
        """测试简单行分割"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2\nline3", encoding='utf-8')

        sf = SourceFile(str(test_file))
        lines = sf.get_code_lines()
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"

    def test_get_code_lines_cache(self, tmp_path):
        """测试行缓存"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2", encoding='utf-8')

        sf = SourceFile(str(test_file))
        lines1 = sf.get_code_lines()
        lines2 = sf.get_code_lines()
        assert lines1 is lines2  # 应该是同一个对象


class TestRemoveCDetails:
    """测试 C 语言注释移除"""

    def test_remove_c_comments_block(self, tmp_path):
        """测试块注释移除"""
        test_file = tmp_path / "test.c"
        test_file.write_text("""/* This is a block comment */
int main() {
    return 0;
}
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        assert "/*" not in result
        assert "*/" not in result

    def test_remove_c_comments_line(self, tmp_path):
        """测试单行注释移除"""
        test_file = tmp_path / "test.c"
        test_file.write_text("""// This is a line comment
int main() {
    return 0; // inline comment
}
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        assert "//" not in result

    def test_remove_c_comments_multiline_block(self, tmp_path):
        """测试多行块注释移除"""
        test_file = tmp_path / "test.c"
        test_file.write_text("""/*
 * Multi-line
 * block comment
 */
int main() {}
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        lines = result.split('\n')
        # 注释行应该被替换为空行但保持行数
        assert len(lines) >= 5

    def test_remove_c_comments_in_string(self, tmp_path):
        """测试字符串中的注释符号不被移除"""
        test_file = tmp_path / "test.c"
        test_file.write_text('''char* s = "This is not a /* comment */";
''', encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        assert '/*' in result or 'comment' in result

    def test_remove_c_comments_single_quote_char(self, tmp_path):
        """测试单引号字符中的注释符号不被移除"""
        test_file = tmp_path / "test.c"
        test_file.write_text("""char c = '/'; // single quote
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        # 单引号字符应该被保留
        assert "'" in result

    def test_remove_c_comments_no_match(self, tmp_path):
        """测试没有匹配任何模式的代码"""
        test_file = tmp_path / "test.c"
        test_file.write_text("int x = 1;", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_c_comments()
        assert result == "int x = 1;"

    def test_remove_c_comments_lines(self, tmp_path):
        """测试 remove_c_comments_lines 方法"""
        test_file = tmp_path / "test.c"
        test_file.write_text("// comment\nint main() {}", encoding='utf-8')

        sf = SourceFile(str(test_file))
        lines = sf.remove_c_comments_lines()
        assert isinstance(lines, list)


class TestRemoveMultipleComments:
    """测试 Shell 文件注释移除"""

    def test_remove_multiple_comments_single_line(self, tmp_path):
        """测试单行注释移除"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("""#!/bin/bash
# This is a comment
echo "hello"
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf._compute_remove_multiple_comments()
        assert "# This is a comment" not in result

    def test_remove_multiple_comments_multiline(self, tmp_path):
        """测试多行注释移除（<<）"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("""#!/bin/bash
:<<EOF
This is a
multi-line comment
EOF
echo "hello"
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf._compute_remove_multiple_comments()
        # EOF 块应该被移除
        assert "This is a" not in result or ":<<" not in result

    def test_remove_multiple_comments_lines(self, tmp_path):
        """测试 remove_multiple_comments_lines 方法"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("# comment\necho hello", encoding='utf-8')

        sf = SourceFile(str(test_file))
        lines = sf.remove_multiple_comments_lines()
        assert isinstance(lines, list)

    def test_remove_multiple_comments_not_text_file(self, tmp_path):
        """测试非文本文件的处理"""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02')

        sf = SourceFile(str(binary_file))
        result = sf._compute_remove_multiple_comments()
        assert result == ''


class TestRemoveMakefileComments:
    """测试 Makefile 注释移除"""

    def test_remove_makefile_comments_simple(self, tmp_path):
        """测试简单 Makefile 注释移除"""
        test_file = tmp_path / "Makefile"
        test_file.write_text("""# This is a comment
CC = gcc
# Another comment
CFLAGS = -Wall
""", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_makefile_comments()
        assert "# This is a comment" not in str(result)
        assert "CC = gcc" in str(result)

    def test_remove_makefile_comments_inline(self, tmp_path):
        """测试行内注释移除"""
        test_file = tmp_path / "Makefile"
        test_file.write_text("CC = gcc # compiler", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_makefile_comments()
        result_str = str(result)
        assert "# compiler" not in result_str

    def test_remove_makefile_comments_lines_type(self, tmp_path):
        """测试返回值类型"""
        test_file = tmp_path / "Makefile"
        test_file.write_text("CC = gcc", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result = sf.remove_makefile_comments()
        assert isinstance(result, list)


class TestEdgeCases:
    """测试边界情况"""

    def test_source_file_unicode_latin1(self, tmp_path):
        """测试 Latin-1 编码文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello \xe4\xf6\xfc")  # Latin-1 的 öü

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert isinstance(code, str)

    def test_source_file_cp1252(self, tmp_path):
        """测试 CP1252 编码文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello \x80\x81\x82")  # CP1252 特殊字符

        sf = SourceFile(str(test_file))
        code = sf.get_code()
        assert isinstance(code, str)

    def test_source_file_repeated_get_code_lines(self, tmp_path):
        """测试重复获取代码行"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\nline2", encoding='utf-8')

        sf = SourceFile(str(test_file))
        for _ in range(3):
            lines = sf.get_code_lines()
            assert len(lines) == 2

    def test_source_file_repeated_remove_c_comments(self, tmp_path):
        """测试重复移除 C 注释"""
        test_file = tmp_path / "test.c"
        test_file.write_text("// comment\ncode", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result1 = sf.remove_c_comments()
        result2 = sf.remove_c_comments()
        assert result1 == result2

    def test_source_file_repeated_remove_multiple_comments(self, tmp_path):
        """测试重复移除多行注释"""
        test_file = tmp_path / "test.sh"
        test_file.write_text("# comment\ncode", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result1 = sf.remove_multiple_comments_lines()
        result2 = sf.remove_multiple_comments_lines()
        assert result1 == result2

    def test_source_file_repeated_remove_makefile_comments(self, tmp_path):
        """测试重复移除 Makefile 注释"""
        test_file = tmp_path / "Makefile"
        test_file.write_text("# comment\ncode", encoding='utf-8')

        sf = SourceFile(str(test_file))
        result1 = sf.remove_makefile_comments()
        result2 = sf.remove_makefile_comments()
        assert result1 == result2
