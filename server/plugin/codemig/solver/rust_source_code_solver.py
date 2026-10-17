import sys
import os
import re
import json
from enum import Enum
from typing import override, List, Tuple, Optional
import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser, Node, Tree

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.public.public import ROOT_PATH
from plugin.codemig.solver.solver import Solver, create_automaton
from plugin.codemig.solver.inline_asm_solver import InlineAsmSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType

RUST_CORE_ARCH_LIST = ["aarch64", "arm", "arm_shared", "loongarch32", "loongarch64",
                       "loongarch_shared", "mips", "nvptx", "powerpc", "powerpc64",
                       "riscv32", "riscv64", "riscv_shared", "s390x", "wasm32", "x86", "x86_64"]
LOGGER = logger.init_log('codemig')


# AST 节点定义
class CfgExpr:
    pass


class Identifier(CfgExpr):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f'Identifier("{self.name}")'


class KeyValue(CfgExpr):
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value

    def __repr__(self):
        return f'KeyValue("{self.key}", "{self.value}")'


class Not(CfgExpr):
    def __init__(self, expr: CfgExpr):
        self.expr = expr

    def __repr__(self):
        return f'Not({self.expr})'


class Any(CfgExpr):
    def __init__(self, exprs: List[CfgExpr]):
        self.exprs = exprs

    def __repr__(self):
        return f'Any({self.exprs})'


class All(CfgExpr):
    def __init__(self, exprs: List[CfgExpr]):
        self.exprs = exprs

    def __repr__(self):
        return f'All({self.exprs})'


# 词法分析器（Tokenizer）
class Token:
    def __init__(self, type_: str, value: str, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f'Token({self.type}, "{self.value}")'


class Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = []
        self.tokenize()

    def tokenize(self):
        # 正则用于分词（注意：这里只用于词法, 不用于语法）
        token_spec = [
            ('STRING', r'"[^"]*"'),  # 字符串字面量
            ('IDENT', r'[a-zA-Z_][a-zA-Z0-9_]*'),  # 标识符
            ('EQUALS', r'='),
            ('COMMA', r','),
            ('LPAREN', r'\('),
            ('RPAREN', r'\)'),
            ('WHITESPACE', r'\s+'),
        ]
        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_spec)
        for mo in re.finditer(tok_regex, self.text):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'WHITESPACE':
                continue
            elif kind == 'STRING':
                value = value[1:-1]  # 去掉引号
            self.tokens.append(Token(kind, value, mo.start()))

    def peek(self, offset=0):
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return None

    def consume(self, expected_type: str):
        if self.peek() and self.peek().type == expected_type:
            token = self.tokens[self.pos]
            self.pos += 1
            return token
        else:
            raise SyntaxError(f"Expected {expected_type}, got {self.peek()} at position {self.pos}")


# 语法解析器
class BaseParser:
    def __init__(self, tokenizer: Tokenizer):
        self.tok = tokenizer

    def parse_expr(self) -> CfgExpr:
        # 尝试解析函数调用: any(...), all(...), not(...)
        if (self.tok.peek() and self.tok.peek().type == 'IDENT' and
                self.tok.peek(1) and self.tok.peek(1).type == 'LPAREN'):
            func_name = self.tok.peek().value
            if func_name in ('any', 'all', 'not'):
                self.tok.consume('IDENT')
                self.tok.consume('LPAREN')
                if func_name == 'not':
                    expr = self.parse_expr()
                    self.tok.consume('RPAREN')
                    return Not(expr)
                else:
                    exprs = []
                    if self.tok.peek() and self.tok.peek().type != 'RPAREN':
                        exprs.append(self.parse_expr())
                        while self.tok.peek() and self.tok.peek().type == 'COMMA':
                            self.tok.consume('COMMA')
                            if self.tok.peek() and self.tok.peek().type == 'RPAREN':
                                break
                            exprs.append(self.parse_expr())
                    self.tok.consume('RPAREN')
                    if func_name == 'any':
                        return Any(exprs)
                    else:  # all
                        return All(exprs)

        # 尝试解析 key = "value"
        if (self.tok.peek() and self.tok.peek().type == 'IDENT' and
                self.tok.peek(1) and self.tok.peek(1).type == 'EQUALS'):
            key = self.tok.consume('IDENT').value
            self.tok.consume('EQUALS')
            if self.tok.peek() and self.tok.peek().type == 'STRING':
                value = self.tok.consume('STRING').value
                return KeyValue(key, value)
            else:
                raise SyntaxError("Expected string after '='")

        # 否则解析为标识符
        if self.tok.peek() and self.tok.peek().type == 'IDENT':
            name = self.tok.consume('IDENT').value
            return Identifier(name)

        raise SyntaxError(f"Unexpected token: {self.tok.peek()}, text: {self.tok.text}")

    def parse(self) -> CfgExpr:
        expr = None
        try:
            expr = self.parse_expr()
        except SyntaxError as e:
            LOGGER.warning("Failed to parse error: %s", e)
        if self.tok.peek():
            LOGGER.warning(f"Unexpected token after expression: {self.tok.peek()}")
        return expr

    def check_positive(self, expr:CfgExpr, default:bool = True) -> bool:
        if isinstance(expr, KeyValue):
            if expr.key == "target_arch":
                if expr.value == "riscv64":
                    return True  # 只有 riscv64 不在 not 中才返回 True
                return False
            elif expr.key == "target_feature":
                return self.is_feature_support_riscv(expr.value)
            else:
                return default
        elif isinstance(expr, Identifier):
            return default
        elif isinstance(expr, Not):
            return not self.check_positive(expr.expr, not default)
        elif isinstance(expr, Any):
            return any(self.check_positive(e, False) for e in expr.exprs)
        elif isinstance(expr, All):
            return all(self.check_positive(e) for e in expr.exprs)
        else:
            return default

    def is_feature_support_riscv(self, feature: str) -> bool:
        for end, (idx, match) in AUTOMATON_FEATURE.iter(feature):
            if match:
                return False
        return True


def update_function_feature():
    fc_list = []
    ft_list = []
    fc_rv_list = []
    ft_rv_list = []
    json_path = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'solver',
                             'rust_arch_functions.json')
    if not os.path.exists(json_path):
        LOGGER.error("Configuration file not found: %s", json_path)
        return [], [], [], []
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        LOGGER.error("Error parsing JSON file %s: %s", json_path, e)
        return [], [], [], []
    except (FileNotFoundError, PermissionError) as e:
        LOGGER.error('Read file %s error: %s', json_path, e)
        return [], [], [], []

    for arch in json_data:
        if arch == "riscv64" or arch == "riscv_shared":
            for func in json_data[arch]:
                fc_rv_list.append(func)
            for feature in json_data[arch].values():
                if "," in feature:
                    ft_rv_list.extend([item.strip() for item in feature.split(",") if item.strip()])
                else:
                    ft_rv_list.append(feature)
        else:
            for func in json_data[arch]:
                fc_list.append(func)
            for feature in json_data[arch].values():
                if "," in feature:
                    ft_list.extend([item.strip() for item in feature.split(",") if item.strip()])
                else:
                    ft_list.append(feature)

    fc_list = set(fc_list)
    if "" in fc_list:
        fc_list.remove("")
    ft_list = set(ft_list)
    if "" in ft_list:
        ft_list.remove("")
    fc_rv_list = set(fc_rv_list)
    if "" in fc_rv_list:
        fc_rv_list.remove("")
    ft_rv_list = set(ft_rv_list)
    if "" in ft_rv_list:
        ft_rv_list.remove("")
    return fc_list, ft_list, fc_rv_list, ft_rv_list


FUNCTION_LIST, FEATURE_LIST, FUNCTION_RV_LIST, FEATURE_RV_LIST = update_function_feature()
AUTOMATON_FEATURE = create_automaton(FEATURE_LIST)

def update_struct():
    struct_list = []
    struct_rv_list = []
    json_path = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'solver',
                             'rust_arch_struct.json')
    if not os.path.exists(json_path):
        LOGGER.error("Configuration file not found: %s", json_path)
        return struct_list, struct_rv_list
    try:
        json_data = json.load(open(json_path, 'r', encoding='utf-8'))
    except json.JSONDecodeError as e:
        LOGGER.error("Error parsing JSON file %s: %s", json_path, str(e))
        return struct_list, struct_rv_list
    except (FileNotFoundError, PermissionError) as err:
        LOGGER.error('Read file %s error: %s', json_path, err)
        return struct_list, struct_rv_list

    for arch in json_data:
        if arch == "riscv64" or arch == "riscv_shared":
            struct_rv_list.extend(json_data[arch])
            continue
        struct_list.extend(json_data[arch])
    struct_list = set(struct_list)
    if "" in struct_list:
        struct_list.remove("")
    struct_rv_list = set(struct_rv_list)
    if "" in struct_rv_list:
        struct_rv_list.remove("")

    return struct_list, struct_rv_list


STRUCT_LIST, STRUCT_RV_LIST = update_struct()


PATTERNS_UASM = "use architecture-specific module"
PATTERNS_FUNCTION = "call architecture-specific function"
PATTERNS_TYPE = "call architecture-specific type"
PATTERNS_LINK = "link to external library"
PATTERNS_ARCH = "target arch"
PATTERNS_FEATURE = "target feature"


class RustSourceCodeSolver(Solver):
    def __init__(self):
        LOGGER.debug("solver init")

    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith(".rs")

    @classmethod
    @override
    def solve(cls, source_file):
        results = []
        results_rv = []
        try:
            parser = RustCodeParser(source_file.get_code())
            results, results_rv = parser.analyze()
        except ValueError as e:
            LOGGER.error(f"Error parsing Rust code with tree-sitter: {e}")

        return results, results_rv

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT


class RustCodeParser:
    advices = {
        PATTERNS_UASM:("该文件中使用了架构相关的函数, 请添加支持riscv架构的函数。"),
        PATTERNS_FUNCTION:("此处调用了架构相关的函数, 请添加对riscv架构的支持。"),
        PATTERNS_TYPE:("此处调用了架构相关的类型, 请添加对riscv架构的支持。"),
        PATTERNS_LINK:("请确认该外部库是否支持riscv架构, 若不支持, 请替换为支持riscv架构的库。"),
        PATTERNS_ARCH:("此处对架构进行判断, 请添加对riscv架构的支持。"),
        PATTERNS_FEATURE:("此处使用了架构相关的特性, 请添加支持riscv架构的特性。"),
    }

    def __init__(self, source_code):
        self.source_code = source_code
        self.language = Language(tsrust.language())
        self.parser = Parser(self.language)
        self.results = []
        self.results_rv = []
        self.use_no_arch_fn_list = []

    def analyze(self) -> Tuple[List, List]:
        """分析代码模式：use 语句、函数调用、类型、外部库"""
        self.results = []
        self.results_rv = []
        self.use_no_arch_fn_list = []
        tree = self.parser.parse(bytes(self.source_code, 'utf-8'))
        self.traverse_tree(tree)
        return self.results, self.results_rv

    def traverse_tree(self, tree: Tree):
        """
        遍历 tree-sitter 语法树, 查找 #[cfg()] 结构及其影响范围
        """
        TOKEN_TREE_NON_SPECIAL_PUNCTUATION = [
        '+', '-', '*', '/', '%', '^', '!', '&', '|', '&&', '||', '<<',
        '>>', '+=', '-=', '*=', '/=', '%=', '^=', '&=', '|=', '<<=',
        '>>=', '=', '==', '!=', '>', '<', '>=', '<=', '@', '_', '.',
        '..', '...', '..=', ',', ';', ':', '::', '->', '=>', '#', '?',
        ]
        type_pass_list = ['line_comment', 'string_literal',
                        'function_signature_item', 'let']
        type_pass_list.extend(TOKEN_TREE_NON_SPECIAL_PUNCTUATION)

        cursor = tree.walk()
        visited_children = False
        affected_node_end_line = -1
        while True:
            if not visited_children:
                node = cursor.node
                to_next_sibling = True
                # affected_node_end_line 如果节点在 affected_node 范围内, 则不继续遍历
                if node.type in type_pass_list or node.end_point.row <= affected_node_end_line:
                # if node.type in type_pass_list:
                    pass
                elif node.type == 'use_declaration':
                    self.traverse_use_declaration(node)
                elif node.type == 'call_expression':
                    to_next_sibling = self.traverse_call_expression(node)
                elif node.type == 'macro_invocation' or node.type == 'macro_definition':
                    self.traverse_macro_invocation(node)
                # 处理 attribute_item 节点（#[cfg()] 结构）
                elif node.type == 'attribute_item':
                    to_next_sibling, affected_node = self.traverse_attribute_item(node)
                    affected_node_end_line = affected_node.end_point.row
                elif node.type == 'type_identifier':
                    self.traverse_type_identifier(node)
                else:
                    to_next_sibling = False

                # 如果处理了当前节点, 继续遍历下一个兄弟节点
                if to_next_sibling:
                    if cursor.goto_next_sibling():
                        visited_children = False
                    elif not cursor.goto_parent():
                        break
                    else:
                        visited_children = True
                # 如果没有处理, 继续遍历子节点
                elif not cursor.goto_first_child():
                    visited_children = True
            else:
                # 已经访问过子节点, 尝试访问下一个兄弟节点
                if cursor.goto_next_sibling():
                    visited_children = False
                elif not cursor.goto_parent():
                    break
                else:
                    visited_children = True

    def _remove_comments(self, node: Node) -> str:
        """
        通过遍历 tree-sitter node 移除注释
        - 行注释:line_comment 节点(// ...)
        - 块注释:block_comment 节点(/* ... */)
        """
        if not node:
            return ""
        result_parts = []
        def traverse_node(n: Node):
            """递归遍历节点，跳过注释节点"""
            # 跳过注释节点
            if n.type in ('line_comment', 'block_comment'):
                return
            # 如果是叶子节点（没有子节点），添加其文本
            if n.child_count == 0:
                # 只添加非注释的文本
                text = n.text.decode('utf-8')
                result_parts.append(text)
                return
            # 遍历所有子节点（包括匿名节点）
            for child in n.children:
                traverse_node(child)
        # 遍历节点
        traverse_node(node)
        return ''.join(result_parts)

    # 返回：是否需要继续遍历子节点
    def traverse_attribute_item(self, node: Node) -> Tuple[bool, Node]:
        """
        处理 attribute_item 节点, 识别 #[cfg()] 结构并确定其影响范围
        Args:
            node: attribute_item 节点
            cursor: tree-sitter 游标
        """
        text = self._remove_comments(node)

        link_match = re.search(r'\[\s*link\s*\(\s*name\s*=\s*"(.*)"', text, re.DOTALL)
        if link_match:
            advice = self.advices.get(PATTERNS_LINK)
            self.results.append((node.start_point.row + 1, node.end_point.row + 1,
            f'匹配到{text}, {advice}', CodeTooLong.HAS_SOURCE_CODE, text))
            return True, node

        cfg_match = re.search(r'#\[cfg\((.*?)\)\s*\]', text, re.DOTALL)
        if not cfg_match:
            return True, node

        if "target_arch" in text:
            advice = self.advices.get(PATTERNS_ARCH)
        elif "target_feature" in text:
            advice = self.advices.get(PATTERNS_FEATURE)
        else:
            return True, node

        cfg_expr = cfg_match.group(1).strip()
        cfg_start_line = node.start_point[0] + 1
        affected_node = self._find_cfg_affected_node(node)

        tokenizer = Tokenizer(cfg_expr)
        parser = BaseParser(tokenizer)
        ast = parser.parse()
        if ast is None:
            LOGGER.warning("Failed to parse cfg expression: %s", cfg_expr)
            return True, node
        bsupport_riscv = parser.check_positive(ast, False)
        if bsupport_riscv:
            self.results_rv.append((cfg_start_line, affected_node.end_point.row + 1,
                            f'匹配到{cfg_expr}, 已支持riscv架构',
                            CodeTooLong.HAS_SOURCE_CODE, text))
        else:
            self.results.append((cfg_start_line, affected_node.end_point.row + 1,
                            f'匹配到{cfg_expr}, {advice}',
                            CodeTooLong.HAS_SOURCE_CODE, text))
        # 支持riscv架构, 需要继续遍历子节点
        return not bsupport_riscv, affected_node

    def _is_cfg_attrbite_item(self, node: Node) -> bool:
        if node.child_count < 1:
            return False
        for child in node.children:
            if child.type == 'attribute' and child.child_count > 0:
                for grandchild in child.children:
                    if grandchild.type == 'identifier':
                        if grandchild.text.decode('utf-8') == 'cfg':
                            return True
        return False

    def _find_cfg_affected_node(self, cfg_node: Node) -> Node:
        """
        #[cfg()] 可以修饰多种 Rust 项：
        - function_item (函数)
        - struct_item (结构体)
        - enum_item (枚举)
        - impl_item (impl 块)
        - mod_item (模块)
        - trait_item (trait)
        - type_item (类型别名)
        - const_item (常量)
        - static_item (静态变量)
        """
        valid_item_types = [
            'function_item', 'struct_item', 'enum_item', 'impl_item',
            'mod_item', 'trait_item', 'type_item', 'const_item',
            'static_item', 'union_item', 'use_declaration', 'macro_definition', 'let_declaration',
            'expression_statement'
        ]
        invalid_item_types = [
            'line_comment', 'block_comment'
        ]
        if cfg_node.type != 'attribute_item':
            return cfg_node

        next_node = cfg_node.next_named_sibling
        while next_node:
            if next_node.type == 'attribute_item': 
                if self._is_cfg_attrbite_item(next_node):
                    break
                else:
                    next_node = next_node.next_named_sibling
                    continue
            if next_node.type in invalid_item_types:
                next_node = next_node.next_named_sibling
                continue
            return next_node
        # 如果找不到修饰的项, 返回 #[cfg()] 本身的行号
        return cfg_node

    def _extract_arch_and_functions_from_use(self, node: Node) -> Tuple[Optional[str], List[str]]:
        """
        从 use_declaration 节点中提取架构类型和函数名列表
        识别 use core::arch::xxx::fn 格式, 获取 xxx 架构类型和 fn 函数名
        Returns:
            (arch, functions): 架构类型（如 'x86_64'）和函数名列表（可能是空列表表示通配符 *）
        """
        arch = None
        functions = []
        # 获取 use_declaration 的 path 子节点
        path_nodes = node.children_by_field_name("path")
        if not path_nodes:
            # 如果没有 path 字段, 尝试从子节点中查找
            for child in node.named_children:
                if child.type in ('scoped_identifier', 'path_expression', 'use_list', 'use_wildcard'):
                    path_nodes = [child]
                    break
        if not path_nodes:
            return None, []

        path_node = path_nodes[0]
        path_text = path_node.text.decode('utf-8')
        # 检查是否是 core::arch::xxx 或 std::arch::xxx 格式
        arch_pattern = r'^(?:core|std)::arch::([^:]+)'
        arch_match = re.match(arch_pattern, path_text)
        if arch_match:
            # 这是一个简单的路径, 如 use core::arch::x86_64::*; 或 use core::arch::x86_64::fn;
            arch = arch_match.group(1)
            # 尝试提取函数名（最后一个标识符）
            parts = path_text.split('::')
            if len(parts) > 3:
                # core::arch::xxx::fn 或 core::arch::xxx::*
                potential_fn = parts[-1]
                if potential_fn and potential_fn != '*':
                    # 有具体的函数名
                    functions.append(potential_fn)
                # 如果是 *, 函数列表保持为空, 表示通配符导入
        else:
            # 可能是更复杂的路径, 尝试从 AST 节点解析
            if path_node.type == 'scoped_identifier':
                # 解析 scoped_identifier, 提取路径部分
                identifiers = []
                for child in path_node.children:
                    if child.type == 'identifier':
                        identifiers.append(child.text.decode('utf-8'))
                    elif child.type == 'scoped_identifier':
                        # 递归处理嵌套的 scoped_identifier
                        sub_arch, sub_functions = self._extract_arch_and_functions_from_use_scoped(child)
                        if sub_arch:
                            arch = sub_arch
                            functions.extend(sub_functions)
                        return arch, functions

                # 检查是否是 core::arch::xxx::fn 格式
                if len(identifiers) >= 3:
                    if identifiers[0] in ('core', 'std') and identifiers[1] == 'arch':
                        arch = identifiers[2]
                        if len(identifiers) > 3:
                            # 有函数名
                            functions.extend(identifiers[3:])

        # 检查是否有 use_list（如 use core::arch::x86_64::{fn1, fn2};）
        use_list_nodes = node.children_by_field_name("use_list")
        if use_list_nodes:
            use_list_node = use_list_nodes[0]
            # 从 use_list 中提取函数名
            for child in use_list_node.named_children:
                if child.type == 'identifier':
                    functions.append(child.text.decode('utf-8'))
                elif child.type == 'scoped_use_list':
                    # 递归处理嵌套列表
                    for grandchild in child.named_children:
                        if grandchild.type == 'identifier':
                            functions.append(grandchild.text.decode('utf-8'))

        # 如果仍然没有找到架构, 尝试从完整文本中提取
        if arch is None:
            text = node.text.decode('utf-8')
            pattern = r'(?:core|std)::arch::([^:\s;{]+)'
            match = re.search(pattern, text)
            if match:
                arch = match.group(1)

        return arch, functions
    
    def _extract_arch_and_functions_from_use_scoped(self, node: Node) -> Tuple[Optional[str], List[str]]:
        """
        从 scoped_identifier 节点中提取架构和函数信息（辅助函数）
        """
        identifiers = []
        for child in node.children:
            if child.type == 'identifier':
                identifiers.append(child.text.decode('utf-8'))

        if len(identifiers) >= 3:
            if identifiers[0] in ('core', 'std') and identifiers[1] == 'arch':
                arch = identifiers[2]
                functions = identifiers[3:] if len(identifiers) > 3 else []
                return arch, functions

        return None, []

    def _extract_function_names_from_use(self, node: Node) -> List[str]:
        """
        从任意 use_declaration 节点中提取函数名列表（不限制架构）
        用于识别如 use std::iter::zip; 这种非架构相关的 use 语句中的函数
        """
        functions = []
        # 获取 use_declaration 的 path 子节点
        path_nodes = node.children_by_field_name("path")
        if not path_nodes:
            # 如果没有 path 字段, 尝试从子节点中查找
            for child in node.named_children:
                if child.type in ('scoped_identifier', 'path_expression', 'use_list'):
                    path_nodes = [child]
                    break

        if path_nodes:
            path_node = path_nodes[0]
            path_text = path_node.text.decode('utf-8')

            # 如果是 scoped_identifier, 提取最后一个标识符作为函数名
            if path_node.type == 'scoped_identifier':
                identifiers = []
                for child in path_node.children:
                    if child.type == 'identifier':
                        identifiers.append(child.text.decode('utf-8'))
                if identifiers:
                    # 最后一个标识符通常是函数名
                    functions.append(identifiers[-1])
            else:
                # 从路径文本中提取最后一个标识符
                parts = path_text.split('::')
                if parts:
                    last_part = parts[-1].strip()
                    if last_part and last_part != '*':
                        functions.append(last_part)

        # 检查是否有 use_list（如 use std::iter::{zip, map};）
        use_list_nodes = node.children_by_field_name("use_list")
        if use_list_nodes:
            use_list_node = use_list_nodes[0]
            # 从 use_list 中提取函数名
            for child in use_list_node.named_children:
                if child.type == 'identifier':
                    functions.append(child.text.decode('utf-8'))
                elif child.type == 'scoped_use_list':
                    # 递归处理嵌套列表
                    for grandchild in child.named_children:
                        if grandchild.type == 'identifier':
                            functions.append(grandchild.text.decode('utf-8'))

        # 如果还没有找到函数名, 尝试从完整文本中提取
        if not functions:
            text = node.text.decode('utf-8')
            # 匹配 use xxx::yyy::zzz; 格式, 提取最后一个标识符（最后一个 :: 后面的部分）
            # 例如：use std::iter::zip; -> zip
            pattern = r'use\s+(?:[^:]+::)+([a-zA-Z_][a-zA-Z0-9_]*)\s*;'
            match = re.search(pattern, text)
            if match:
                functions.append(match.group(1))

        return functions

    # 返回：是否去下一个兄弟节点
    def traverse_use_declaration(self, node: Node) -> bool:
        """
        处理 use_declaration 节点, 识别 use 语句
        """
        text = node.text.decode('utf-8')
        start_line = node.start_point.row + 1
        end_line = node.end_point.row + 1

        # 从 AST 节点中提取架构类型和函数名
        arch, functions = self._extract_arch_and_functions_from_use(node)
        # 如果是架构相关的 use 语句
        if arch is not None:
            # 验证架构是否在有效列表中
            if arch not in RUST_CORE_ARCH_LIST:
                return True
            # 判断架构类型
            if arch == "riscv64" or arch == "riscv_shared":
                self.results_rv.append((start_line, end_line,
                    f'匹配到 {text}, 已支持riscv架构',
                    CodeTooLong.HAS_SOURCE_CODE, text))
            else:
                # 其他架构
                advice = self.advices.get(PATTERNS_UASM)
                self.results.append((start_line, end_line,
                    f'匹配到{text}, {advice}',
                    CodeTooLong.HAS_SOURCE_CODE, text))
        else:
            # 非架构相关的 use 语句（如 use std::iter::zip;）
            # 仍然需要提取函数名, 以便在函数调用检查时跳过
            all_functions = self._extract_function_names_from_use(node)
            self.use_no_arch_fn_list.extend(all_functions)

        return True

    def traverse_call_expression(self, node: Node) -> bool:
        """
        处理 call_expression 节点, 识别函数并确定其影响范围
        判断是否是 std::arch::x86_64::fn 的调用 或者 函数名是否在指定列表中
        Args:
            node: call_expression 节点
        """
        arch = None
        function_name = None
        text = node.text.decode('utf-8')
        # 直接从文本中提取路径和函数名（更可靠的方法）
        # 检查是否是 std::arch::xxx::fn 或 core::arch::xxx::fn 格式
        arch_pattern = r'(?:std|core)::arch::([^:]+)::([a-zA-Z_][a-zA-Z0-9_]*)'
        arch_match = re.search(arch_pattern, text)
        if arch_match:
            arch = arch_match.group(1)
            function_name = arch_match.group(2)
            if arch not in RUST_CORE_ARCH_LIST:
                return False
            elif arch == "riscv64" or arch == "riscv_shared":
                self.results_rv.append((node.start_point.row + 1, node.end_point.row + 1,
                f'匹配到{arch_match.group()}, 已支持riscv架构', CodeTooLong.HAS_SOURCE_CODE, text))
            else:
                advice = self.advices.get(PATTERNS_FUNCTION)
                self.results.append((node.start_point.row + 1, node.end_point.row + 1,
                f'匹配到{arch_match.group()}, {advice}', CodeTooLong.HAS_SOURCE_CODE, text))
            return True

        function_nodes = node.children_by_field_name("function")
        for every_node in function_nodes:
            function_name = every_node.text.decode('utf-8')
            if function_name in self.use_no_arch_fn_list:
                return False
            elif function_name in FUNCTION_LIST:
                advice = self.advices.get(PATTERNS_FUNCTION)
                self.results.append((node.start_point.row + 1, node.end_point.row + 1,
                f'匹配到{function_name}, {advice}', CodeTooLong.HAS_SOURCE_CODE, text))
                return True
            elif function_name in FUNCTION_RV_LIST:
                self.results_rv.append((node.start_point.row + 1, node.end_point.row + 1,
                f'匹配到{function_name}, 已支持riscv架构', CodeTooLong.HAS_SOURCE_CODE, text))
                return True
            return False

    def traverse_macro_invocation(self, node: Node) -> bool:
        """
        处理 macro_invocation 节点, 识别宏并确定其影响范围
        Args:
            node: macro_invocation 节点
        """
        text = node.text.decode('utf-8')
        asm_pattern = r'\b(?:asm|global_asm|naked_asm)!\s*\((.*?)\)'
        for match in re.finditer(asm_pattern, text, flags = re.DOTALL):
            source_file = SourceFile("")
            source_file.code = text
            solver_results, solver_results_rv = InlineAsmSolver.solve(source_file)
            for result in solver_results:
                result[0] = result[0] + node.start_point.row
                result[1] = result[1] + node.start_point.row
            LOGGER.debug("inline asm [%s] results [%s]", source_file.code, solver_results)
            self.results.extend(solver_results)
            for result in solver_results_rv:
                result[0] = result[0] + node.start_point.row
                result[1] = result[1] + node.start_point.row
            self.results_rv.extend(solver_results_rv)
            return True

        lib_pattern = r'"cargo:rustc-link-lib=(.*)"'
        for match in re.finditer(lib_pattern, text, flags = re.DOTALL):
            lib_name = match.group(1)
            advice = self.advices.get(PATTERNS_LINK)
            self.results.append((node.start_point.row + 1, node.end_point.row + 1,
            f'匹配到{match.group()}, {advice}', CodeTooLong.HAS_SOURCE_CODE, text))
            return True

    def traverse_type_identifier(self, node: Node) -> bool:
        """
        处理 type_identifier 节点, 识别类型并确定其影响范围
        Args:
            node: type_identifier 节点
        """
        text = node.text.decode('utf-8')
        if text in STRUCT_LIST:
            advice = self.advices.get(PATTERNS_TYPE)
            info = (node.start_point.row + 1, node.end_point.row + 1,
            f'匹配到{text}, {advice}', CodeTooLong.HAS_SOURCE_CODE, text)
            if info not in self.results:
                self.results.append(info)
        elif text in STRUCT_RV_LIST:
            info = (node.start_point.row + 1, node.end_point.row + 1,
            f'匹配到{text}, 已支持riscv架构', CodeTooLong.HAS_SOURCE_CODE, text)
            if info not in self.results_rv:
                self.results_rv.append(info)
        return True
