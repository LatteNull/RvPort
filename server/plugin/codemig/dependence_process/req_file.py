import sys

import tomlkit
from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement
from tomlkit.toml_file import TOMLFile

import argparse
import codecs
import locale
import os
import re
import shlex
import urllib
from argparse import Namespace, ArgumentParser
from dataclasses import dataclass
from typing import Callable, Any, NewType, cast, NoReturn, Tuple, Optional, Generator, Iterable

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from plugin.codemig.dependence_process.models import DependenceTask

LOGGER = logger.init_log('codemig')

LineParser = Callable[[str], tuple[str, Namespace]]
SCHEME_RE = re.compile(r"^(http|https|file):", re.I)
COMMENT_RE = re.compile(r"(^|\s+)#.*$")
BOMS: list[tuple[bytes, str]] = [
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF32, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF16, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
]
PEP263_ENCODING_RE = re.compile(rb"coding[:=]\s*([-\w.]+)")
DEFAULT_ENCODING = "utf-8"
ReqFileLines = Iterable[tuple[int, str]]
ENV_VAR_RE = re.compile(r"(?P<var>\$\{(?P<name>[A-Z0-9_]+)\})")


class PyPI:
    simple_url = "https://pypi.org/simple/"


def index_url(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-i",
        "--index-url",
        "--pypi-url",
        dest="index_url",
        metavar="URL",
        default=PyPI.simple_url
    )


def extra_index_url(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--extra-index-url",
        dest="extra_index_urls",
        metavar="URL",
        action="append",
        default=[]
    )


def no_index(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--no-index",
        dest="no_index",
        action="store_true",
        default=False
    )


def constraints(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--constraint",
        dest="constraints",
        action="append",
        default=[],
        metavar="file"
    )


def requirements(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-r",
        "--requirement",
        dest="requirements",
        action="append",
        default=[],
        metavar="file"
    )


def editable(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-e",
        "--editable",
        dest="editables",
        action="append",
        default=[],
        metavar="path/url"
    )


def find_links(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-f",
        "--find-links",
        dest="find_links",
        action="append",
        default=[],
        metavar="url"
    )


def prefer_binary(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--prefer-binary",
        dest="prefer_binary",
        action="store_true",
        default=False
    )


def require_hashes(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--require-hashes",
        dest="require_hashes",
        action="store_true",
        default=False
    )


def pre(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--pre",
        action="store_true",
        default=False
    )


def trusted_host(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--trusted-host",
        dest="trusted_hosts",
        action="append",
        metavar="HOSTNAME",
        default=[]
    )


ALWAYS_ENABLED_FEATURES = [
    "truststore",  # always on since 24.2
    "no-binary-enable-wheel-cache",  # always on since 23.1
]


def use_new_feature(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--use-feature",
        dest="features_enabled",
        metavar="feature",
        action="append",
        default=[],
        choices=["fast-deps", ] + ALWAYS_ENABLED_FEATURES
    )


def global_options(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--global-option",
        dest="global_options",
        action="append",
        metavar="options"
    )


STRONG_HASHES = ["sha256", "sha384", "sha512"]


def _handle_merge_hash(args: Namespace, value: str) -> None:
    """Given a value spelled "algo:digest", append the digest to a list
    pointed to in a dict by the algo name."""
    if not hasattr(args, 'hashes') or args.hashes is None:
        args.hashes = {}

    try:
        algo, digest = value.split(":", 1)
    except ValueError:
        raise argparse.ArgumentError(
            None,
            f"Arguments to --hash must be a hash name followed by a value, "
            f"like --hash=sha256:abcde..."
        )
    if algo not in STRONG_HASHES:
        raise argparse.ArgumentError(
            None,
            f"Allowed hash algorithms for --hash are {', '.join(STRONG_HASHES)}."
        )
    args.hashes.setdefault(algo, []).append(digest)


def hash_option(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--hash",
        dest="hashes",
        action="append",  # 使用 append action 而不是 callback
        type=str
    )


def _handle_config_settings(args: Namespace, value: str) -> None:
    """处理 --config-settings 参数"""
    key, sep, val = value.partition("=")
    if sep != "=":
        raise argparse.ArgumentError(None,
                                     f"Arguments to --config-settings must be of the form KEY=VAL")
    if not hasattr(args, 'config_settings') or args.config_settings is None:
        args.config_settings = {}

    if key in args.config_settings:
        if isinstance(args.config_settings[key], list):
            args.config_settings[key].append(val)
        else:
            args.config_settings[key] = [args.config_settings[key], val]
    else:
        args.config_settings[key] = val


def config_settings(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-C", "--config-settings",
        dest="config_settings",
        type=str,
        action="append",  # 使用 append action
        metavar="settings"
    )


SUPPORTED_OPTIONS: list[Callable[[ArgumentParser], None]] = [
    index_url,
    extra_index_url,
    no_index,
    constraints,
    requirements,
    editable,
    find_links,
    # no_binary,
    # only_binary,
    prefer_binary,
    require_hashes,
    pre,
    trusted_host,
    use_new_feature,
]

# options to be passed to requirements
SUPPORTED_OPTIONS_REQ: list[Callable[[ArgumentParser], None]] = [
    global_options,
    hash,
    config_settings,
]


@dataclass(frozen=True, slots=True)
class ParsedRequirement:
    requirement: str
    is_editable: bool
    comes_from: str
    constraint: bool
    options: dict[str, Any]
    line_source: str


NormalizedName = NewType("NormalizedName", str)
# Core metadata spec for `Name`
_validate_regex = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.IGNORECASE)
_canonicalize_regex = re.compile(r"[-_.]+")


def canonicalize_name(name: str, *, validate: bool = False) -> NormalizedName:
    if validate and not _validate_regex.match(name):
        raise InvalidName(f"name is invalid: {name!r}")
    # This is taken from PEP 503.
    value = _canonicalize_regex.sub("-", name).lower()
    return cast(NormalizedName, value)


class PipError(Exception):
    """The base pip error."""


class InstallationError(PipError):
    """General exception during installation"""


class RequirementsFileParseError(InstallationError):
    """Raised when a general error occurs parsing a requirements file line."""


class OptionParsingError(Exception):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg


class InvalidName(ValueError):
    """
    An invalid distribution name; users should refer to the packaging user guide.
    """


class CommandError(PipError):
    """Raised when there is an error in command-line arguments"""


@dataclass(frozen=True)
class ParsedLine:
    __slots__ = ("filename", "lineno", "args", "opts", "constraint")

    filename: str
    lineno: int
    args: str
    opts: Namespace
    constraint: bool

    @property
    def is_editable(self) -> bool:
        return bool(self.opts.editables)

    @property
    def requirement(self) -> str:
        if self.args:
            return self.args
        elif self.is_editable:
            # We don't support multiple -e on one line
            return self.opts.editables[0]
        return None


class RequirementsFileParser:
    def __init__(self, line_parser: LineParser):
        self._line_parser = line_parser

    def parse(self, filename: str, constraint: bool) -> Generator[ParsedLine, None, None]:
        """Parse a given file, yielding parsed lines."""
        initial_parsed_files = {os.path.abspath(filename): None}
        yield from self._parse_and_recurse(filename, constraint, [initial_parsed_files])

    def _parse_and_recurse(
            self,
            filename: str,
            constraint: bool,
            parsed_files_stack: list[dict[str, str]],
    ) -> Generator[ParsedLine, None, None]:
        for line in self._parse_file(filename, constraint):
            # Handle nested requirements files
            if self._is_nested_requirement_line(line):
                yield from self._process_nested_requirement(line, filename, parsed_files_stack)
            else:
                yield line

    @staticmethod
    def _is_nested_requirement_line(line: ParsedLine) -> bool:
        """Check if line contains a nested requirements file reference."""
        return line.requirement is None and (line.opts.requirements or line.opts.constraints)

    def _process_nested_requirement(
            self,
            line: ParsedLine,
            parent_filename: str,
            parsed_files_stack: list[dict[str, str | None]],
    ) -> Generator[ParsedLine, None, None]:
        """Process a nested requirements file reference."""
        # Determine nested file path and constraint type
        if line.opts.requirements:
            req_path = line.opts.requirements[0]
            nested_constraint = False
        else:
            req_path = line.opts.constraints[0]
            nested_constraint = True

        # Resolve the nested file path
        resolved_path = self._resolve_nested_path(req_path, parent_filename)

        # Check for recursive references
        self._check_recursive_reference(resolved_path, parent_filename, parsed_files_stack)

        # Parse the nested file recursively
        new_parsed_files = self._create_new_parsed_files(
            resolved_path, parent_filename, parsed_files_stack
        )
        yield from self._parse_and_recurse(
            resolved_path, nested_constraint, [new_parsed_files, *parsed_files_stack]
        )

    @staticmethod
    def _resolve_nested_path(req_path: str, parent_filename: str) -> str:
        """Resolve the path of a nested requirements file."""
        # Handle URL-based parent file
        if SCHEME_RE.search(parent_filename):
            return urllib.parse.urljoin(parent_filename, req_path)

        # Handle local file paths
        if not SCHEME_RE.search(req_path):
            parent_dir = os.path.dirname(parent_filename)
            return os.path.abspath(os.path.join(parent_dir, req_path))

        return req_path

    @staticmethod
    def _check_recursive_reference(
            req_path: str,
            current_filename: str,
            parsed_files_stack: list[dict[str, str | None]],
    ):
        """Check for recursive file references and raise error if found."""
        current_parsed_files = parsed_files_stack[0]

        if req_path in current_parsed_files:
            initial_file = current_parsed_files[req_path]
            tail = f" and again in {initial_file}" if initial_file is not None else ""
            raise RequirementsFileParseError(
                f"{req_path} recursively references itself in {current_filename}{tail}"
            )

    @staticmethod
    def _create_new_parsed_files(
            req_path: str,
            included_from: str,
            parsed_files_stack: list[dict[str, str | None]],
    ) -> dict[str, str | None]:
        """Create a new parsed files tracking dictionary."""
        current_parsed_files = parsed_files_stack[0]
        new_parsed_files = current_parsed_files.copy()
        new_parsed_files[req_path] = included_from
        return new_parsed_files

    def _parse_file(self, filename: str, constraint: bool) -> Generator[ParsedLine, None, None]:
        _, content = get_file_content(filename)

        lines_enum = preprocess(content)

        for line_number, line in lines_enum:
            try:
                args_str, opts = self._line_parser(line)
            except OptionParsingError as e:
                # add offending line
                msg = f"Invalid requirement: {line}\n{e.msg}"
                raise RequirementsFileParseError(msg)

            yield ParsedLine(filename, line_number, args_str, opts, constraint)


def get_file_content(url: str) -> tuple[str, str]:
    """Gets the content of a file; it may be a filename, file: URL, or
    http: URL.  Returns (location, content).  Content is unicode.
    Respects # -*- coding: declarations on the retrieved files.

    :param url:         File path or url.
    :param session:     PipSession instance.
    """
    scheme = urllib.parse.urlsplit(url).scheme
    # Pip has special support for file:// URLs (LocalFSAdapter).
    if scheme in ["http", "https", "file"]:
        # Delay importing heavy network modules until absolutely necessary.
        LOGGER.error(f'not support ulr scheme in {url}')
        return url, ''

    # Assume this is a bare path.
    try:
        with open(url, "rb") as f:
            raw_content = f.read()
    except OSError as exc:
        raise InstallationError(f"Could not open requirements file: {exc}")

    content = _decode_req_file(raw_content, url)

    return url, content


def _decode_req_file(data: bytes, url: str) -> str:
    for bom, encoding in BOMS:
        if data.startswith(bom):
            return data[len(bom):].decode(encoding)

    for line in data.split(b"\n")[:2]:
        if line[0:1] == b"#":
            result = PEP263_ENCODING_RE.search(line)
            if result is not None:
                encoding = result.groups()[0].decode("ascii")
                return data.decode(encoding)

    try:
        return data.decode(DEFAULT_ENCODING)
    except UnicodeDecodeError:
        locale_encoding = locale.getpreferredencoding(False) or sys.getdefaultencoding()
        LOGGER.warning(
            "unable to decode data from %s with default encoding %s, "
            "falling back to encoding from locale: %s. "
            "If this is intentional you should specify the encoding with a "
            "PEP-263 style comment, e.g. '# -*- coding: %s -*-'",
            url,
            DEFAULT_ENCODING,
            locale_encoding,
            locale_encoding,
        )
        return data.decode(locale_encoding)


def preprocess(content: str) -> ReqFileLines:
    """Split, filter, and join lines, and return a line iterator

    :param content: the content of the requirements file
    """
    lines_enum: ReqFileLines = enumerate(content.splitlines(), start=1)
    lines_enum = join_lines(lines_enum)
    lines_enum = ignore_comments(lines_enum)
    lines_enum = expand_env_variables(lines_enum)
    return lines_enum


def join_lines(lines_enum: ReqFileLines) -> ReqFileLines:
    """Joins a line ending in '\' with the previous line (except when following
    comments).  The joined line takes on the index of the first line.
    """
    buffer = []
    start_line_no = None

    for line_number, line in lines_enum:
        # 快速检查：不以反斜杠结尾或是注释
        comment = line.lstrip().startswith("#")
        if not line.endswith("\\") or comment:
            if comment:
                line = " " + line
            if buffer:
                buffer.append(line)
                yield start_line_no, "".join(buffer)
                buffer = []
            else:
                yield line_number, line
        else:
            # 续行处理
            if not buffer:
                start_line_no = line_number
            buffer.append(line[:-1])  # 直接切片，比 rstrip 快

    if buffer:
        yield start_line_no, "".join(buffer)


def ignore_comments(lines_enum: ReqFileLines) -> ReqFileLines:
    for line_number, line in lines_enum:
        line = COMMENT_RE.sub("", line)
        line = line.strip()
        if line:
            yield line_number, line


def expand_env_variables(lines_enum: ReqFileLines) -> ReqFileLines:
    for line_number, line in lines_enum:
        for env_var, var_name in ENV_VAR_RE.findall(line):
            value = os.getenv(var_name)
            if not value:
                continue
            line = line.replace(env_var, value)

        yield line_number, line


def get_line_parser() -> LineParser:
    def parse_line(line: str) -> tuple[str, Namespace]:
        # Build new parser for each line since it accumulates appendable
        # options.
        parser = init_parser()
        # 设置默认值
        args = parser.parse_args([])
        args.index_url = None

        args_str, options_str = split_line_options(line)

        try:
            options = shlex.split(options_str)
        except ValueError as e:
            raise OptionParsingError(f"Could not split options: {options_str}") from e

        parsed_args, _ = parser.parse_known_args(options)
        # 合并参数
        for key, value in vars(parsed_args).items():
            if value is not None and value != [] and value != {}:
                setattr(args, key, value)
        # 后处理参数
        post_process_args(args)
        return args_str, args

    return parse_line


def split_line_options(line: str) -> tuple[str, str]:
    # Break up the line into an args and options string.
    tokens = line.split(" ")

    # Find the first option token (starts with - or --)
    for i, token in enumerate(tokens):
        if token.startswith(("-", "--")):
            args_tokens = tokens[:i]
            options_tokens = tokens[i:]
            return " ".join(args_tokens), " ".join(options_tokens)

    # No options found, everything is args
    return " ".join(tokens), ""


SUPPORTED_OPTIONS_EDITABLE_REQ = [config_settings, ]
SUPPORTED_OPTIONS_REQ_DEST = ['global_options', 'hashes', 'config_settings']
SUPPORTED_OPTIONS_EDITABLE_REQ_DEST = ['config_settings']


def handle_requirement_line(
        line: ParsedLine,
        options: Namespace | None = None,
) -> ParsedRequirement:
    # preserve for the nested code path
    line_comes_from = f"{"-c" if line.constraint else "-r"} {line.filename} (line {line.lineno})"

    assert line.requirement is not None

    # get the options that apply to requirements
    if line.is_editable:
        supported_dest = SUPPORTED_OPTIONS_EDITABLE_REQ_DEST
    else:
        supported_dest = SUPPORTED_OPTIONS_REQ_DEST
    req_options = {}
    for dest in supported_dest:
        if dest in line.opts.__dict__ and line.opts.__dict__[dest]:
            req_options[dest] = line.opts.__dict__[dest]

    line_source = f"line {line.lineno} of {line.filename}"
    return ParsedRequirement(
        requirement=line.requirement,
        is_editable=line.is_editable,
        comes_from=line_comes_from,
        constraint=line.constraint,
        options=req_options,
        line_source=line_source,
    )


def handle_option_line(
        opts: Namespace,
        filename: str,
        lineno: int,
        options: Namespace | None = None,
) -> None:
    if hasattr(opts, 'hashes') and opts.hashes:
        LOGGER.warning(
            "%s line %s has --hash but no requirement, and will be ignored.",
            filename,
            lineno,
        )

    if options:
        # percolate options upward
        if hasattr(opts, 'require_hashes') and opts.require_hashes:
            options.require_hashes = opts.require_hashes
        if hasattr(opts, 'features_enabled') and opts.features_enabled:
            if not hasattr(options, 'features_enabled'):
                options.features_enabled = []
            options.features_enabled.extend(
                f for f in opts.features_enabled
                if f not in options.features_enabled
            )


def handle_line(
        line: ParsedLine,
        options: Namespace | None = None,
) -> ParsedRequirement:
    if line.requirement is not None:
        parsed_req = handle_requirement_line(line, options)
        return parsed_req
    else:
        handle_option_line(
            line.opts,
            line.filename,
            line.lineno,
            options,
        )
        return None


def post_process_args(args: Namespace) -> None:
    """后处理参数，处理需要特殊逻辑的参数"""
    # 处理 --hash 参数
    if hasattr(args, 'hashes') and args.hashes:
        hashes_list = args.hashes  # 保存原始列表
        hashes_dict = {}
        args.hashes = hashes_dict  # 先设置为字典，以便 _handle_merge_hash 可以正常工作
        for hash_spec in hashes_list:
            _handle_merge_hash(args, hash_spec)

    # 处理 --config-settings 参数
    if hasattr(args, 'config_settings') and args.config_settings:
        config_list = args.config_settings  # 保存原始列表
        config_dict = {}
        args.config_settings = config_dict  # 先设置为字典，以便 _handle_config_settings 可以正常工作
        for setting in config_list:
            _handle_config_settings(args, setting)


def parse_requirements(
        filename: str,
        constraint: bool = False,
) -> Generator[ParsedRequirement, None, None]:
    """Parse a requirements file and yield ParsedRequirement instances.

    :param filename:    Path or url of requirements file.
    :param session:     PipSession instance.
    :param finder:      Instance of pip.index.PackageFinder.
    :param options:     cli options.
    :param constraint:  If true, parsing a constraint file rather than
        requirements file.
    """
    line_parser = get_line_parser()
    parser = RequirementsFileParser(line_parser)

    for parsed_line in parser.parse(filename, constraint):
        parsed_req = handle_line(parsed_line)
        if parsed_req is not None:
            yield parsed_req


def init_parser() -> ArgumentParser:
    # Return a parser for parsing requirement lines
    parser = ArgumentParser(add_help=False)
    options = SUPPORTED_OPTIONS + SUPPORTED_OPTIONS_REQ
    for option in options:
        option(parser)

    # By default optparse sys.exits on parsing errors. We want to wrap
    # that in our own exception.
    def parser_exit(self: Any, msg: str) -> NoReturn:
        # raise OptionParsingError(msg)
        pass

    parser.exit = parser_exit

    return parser


class RequirementParser:
    @staticmethod
    def parse_requirements(file_path):
        """解析requirements文件获取包和版本"""
        packages = set()
        try:
            requires = parse_requirements(file_path)
            for item in requires:
                try:
                    if item.requirement.startswith('git+http') or item.requirement.startswith(
                            'hg+http'):
                        continue
                    req = Requirement(item.requirement)
                    package_name = req.name
                    packages.add((package_name, str(item.requirement)))
                except InvalidRequirement as e:
                    LOGGER.info(f"解析{file_path}出错: {e}")
        except Exception as e:
            LOGGER.error(f"解析{file_path}出错: {e}", exc_info=True)
        return packages


class PyProjectParser:
    @staticmethod
    def _parse_version_parts(version: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        解析版本号字符串，返回主版本、次版本、修订版本

        Args:
            version: 版本号字符串，如 "1.5.3", "2.0", "3"

        Returns:
            (major, minor, patch) 三元组
        """
        parts = version.split('.')
        major = parts[0] if len(parts) > 0 else "0"
        minor = parts[1] if len(parts) > 1 else None
        patch = parts[2] if len(parts) > 2 else None
        return major, minor, patch

    @staticmethod
    def _convert_version_specifier(version_spec: str) -> str:
        """
        将 Poetry/PDM 风格的版本说明符转换为 requirements.txt 格式

        Args:
            version_spec: 版本说明符字符串，如 "^1.5.3", "~2.0.0", ">=1.0.0"

        Returns:
            requirements.txt 格式的版本说明符
        """
        # 移除前后空格
        version_spec = version_spec.strip()

        # 处理通配符版本
        if version_spec == "*":
            return ""

        # 处理精确版本匹配
        if version_spec.startswith("=="):
            # 处理 ==1.5.* 的情况
            if version_spec.endswith(".*"):
                base_version = version_spec[2:-2]
                major, minor, _ = PyProjectParser._parse_version_parts(base_version)
                if minor is not None:
                    return f">={base_version}.0, <{major}.{int(minor) + 1}.0"
                else:
                    return f">={major}.0.0, <{int(major) + 1}.0.0"
            return version_spec

        # 处理插入符 ^ 操作符
        if version_spec.startswith("^"):
            version = version_spec[1:]
            major, minor, patch = PyProjectParser._parse_version_parts(version)
            if major == "0":
                # 0.x.x 版本：^0.2.3 -> >=0.2.3, <0.3.0
                return f">={version}, <0.{int(minor) + 1}.0"
            else:
                # x.x.x 版本：^1.2.3 -> >=1.2.3, <2.0.0
                return f">={version}, <{int(major) + 1}.0.0"

        # 处理波浪号 ~ 操作符
        if version_spec.startswith("~"):
            version = version_spec[1:]
            major, minor, patch = PyProjectParser._parse_version_parts(version)
            if patch is not None:
                # ~1.2.3 -> >=1.2.3, <1.3.0
                return f">={version}, <{major}.{int(minor) + 1}.0"
            else:
                # ~1.2 -> >=1.2.0, <1.3.0
                return f">={major}.{minor}.0, <{major}.{int(minor) + 1}.0"

        # 处理其他操作符（>=, <=, >, <, !=）或直接版本号
        # 这些在 requirements.txt 中基本一致
        return version_spec

    @staticmethod
    def _convert_dependency_line(dependency_line: str) -> str:
        """
        转换完整的依赖行，如 "requests ^1.5.3" -> "requests>=1.5.3, <2.0.0"

        Args:
            dependency_line: 依赖行字符串

        Returns:
            转换后的依赖行
        """
        # 使用正则表达式分割包名和版本说明符
        match = re.match(r'^([^#\s].*)?$', dependency_line.strip())

        if not match:
            return dependency_line

        version_spec = match.group(1)

        if not version_spec or version_spec.strip() == "":
            return dependency_line

        converted_spec = PyProjectParser._convert_version_specifier(version_spec.strip())

        return converted_spec

    @staticmethod
    def parse_pyproject(file_path):
        packages = []
        dependencies = []
        data = None
        try:
            # 读取 pyproject.toml
            with open(file_path, 'r') as f:
                try:
                    toml_file = TOMLFile(file_path)
                    data = toml_file.read()
                except tomlkit.exceptions.ParseError as e:
                    LOGGER.error(f"TOML 解析失败（{file_path}）: {e}")
            if data is None:
                return packages
            # 解析依赖 - 支持不同格式

            # PEP 621 格式 (标准) and PDM 格式
            if 'project' in data and 'dependencies' in data['project']:
                dependencies = data['project']['dependencies']
            if 'dependency-groups' in data:
                for key, value in data['dependency-groups'].items():
                    dependencies.extend([v for v in value if isinstance(v, str)])
            if 'project' in data and 'optional-dependencies' in data['project']:
                for key, value in data['project']['optional-dependencies'].items():
                    dependencies.extend(value)
            # Poetry 格式
            if 'tool' in data and 'poetry' in data['tool'] and 'dependencies' in data['tool'][
                'poetry']:
                PyProjectParser.get_dependece(dependencies, data['tool']['poetry']['dependencies'])
            if 'tool' in data and 'poetry' in data['tool'] and 'group' in data['tool']['poetry']:
                tree = data['tool']['poetry']['group']
                for key, value in tree.items():
                    if 'dependencies' in value:
                        PyProjectParser.get_dependece(dependencies,
                                                      data['tool']['poetry']['group'][key][
                                                          'dependencies'])

        except Exception as e:
            LOGGER.error(f"解析{file_path}文件出错: {e}")

        for dep in dependencies:
            try:
                req = Requirement(dep)
                package_name = req.name
                packages.append((package_name, package_name + str(req.specifier)))
                # # 获取版本约束
                # version_spec = next(iter(req.specifier), None)
                # version = version_spec.version if version_spec else ''
                # packages.append((package_name, package_name+version))
            except Exception as e:
                LOGGER.error(f"处理依赖 '{dep}' 时出错: {str(e)}")
        return packages

    @staticmethod
    def get_dependece(dependencies, deps):
        for name, spec in deps.items():
            if name.lower() == 'python':  # 跳过 Python 版本限制
                continue
            if isinstance(spec, str):
                spec = PyProjectParser._convert_dependency_line(spec)
                dependencies.append(f"{name}{spec}")
            else:
                dependencies.append(name)


def combine_pkg(req, toml):
    pkg = req | toml
    pkg_dict = {}
    for p, spec in pkg:
        if p not in pkg_dict:
            pkg_dict[p] = [spec]
        else:
            pkg_dict[p].append(spec)
    packages = [(p, "\n".join(specs)) for p, specs in pkg_dict.items() if
                p not in ['setuptools', 'python', 'pytest', 'pytest-cov', 'pip', 'wheel']]
    return packages


def parse_python_req(source_path, task_id, user_id, dir_id):
    packages_req = set()
    packages_toml = set()
    try:
        for root, dirs, files in os.walk(source_path, topdown=True):
            for file_name in files:
                if re.fullmatch(r'^(requirements.*|.*requirements)\.txt$', file_name):
                    file_path = os.path.join(root, file_name)
                    packages_req.update(RequirementParser.parse_requirements(file_path))
                elif file_name == 'pyproject.toml':
                    file_path = os.path.join(root, file_name)
                    packages_toml.update(PyProjectParser.parse_pyproject(file_path))
        # packages = packages_req | packages_toml
        packages = combine_pkg(packages_req, packages_toml)
        insert_task = [(task_id, dir_id, p, v) for (p, v) in packages]

        success, count = DependenceTask.bulk_insert_tasks(insert_task)
        if success:
            return True, count, insert_task
        else:
            return False, f'insert python dependency task error', None
    except (PermissionError, OSError, IOError, AttributeError, FileNotFoundError,
            KeyError, IndexError) as e:
        LOGGER.error(f'{task_id} error', exc_info=True)
        return False, f'parse python dependency error: {str(e)}', None
