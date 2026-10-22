from .arguments import ClangArgumentResult, normalize_clang_arguments
from .clang_adapter import ClangCppAdapter
from .compilation_database import CompilationDatabaseReader, compilation_context_id
from .frontend import CppFrontend
from .tree_sitter_adapter import TreeSitterCppAdapter
from .vocabulary import CPP_EVIDENCE_KINDS, make_source_file_entity
from .workspace import CppWorkspaceCollector

__all__ = [
    "CPP_EVIDENCE_KINDS",
    "ClangArgumentResult",
    "ClangCppAdapter",
    "CompilationDatabaseReader",
    "CppFrontend",
    "CppWorkspaceCollector",
    "TreeSitterCppAdapter",
    "compilation_context_id",
    "make_source_file_entity",
    "normalize_clang_arguments",
]
