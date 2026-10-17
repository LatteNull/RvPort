import os
import sys
from abc import ABC, abstractmethod

import ahocorasick

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solvers_mapping import solver_to_str
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG, CodeTooLong


def create_automaton(words):
    automaton = ahocorasick.Automaton()
    for idx, word in enumerate(words):
        automaton.add_word(word, (idx, word))
    automaton.make_automaton()
    return automaton


class Solver(ABC):

    @staticmethod
    def migration_class():
        return MigrationClass.TEXT

    @staticmethod
    @abstractmethod
    def matches_file(file_name):
        pass

    @classmethod
    @abstractmethod
    def solve(cls, source_file) -> ([], []):
        pass

    @classmethod
    def get_solver_type(cls):
        return solver_to_str(cls.__name__)

    @staticmethod
    @abstractmethod
    def append_or_replace():
        pass

    @staticmethod
    def extract_code(lines, start_lineno, end_lineno):
        number_lines = end_lineno - start_lineno + 1
        code_too_long = number_lines > NUMBER_LINES_TOO_LONG
        if code_too_long:
            return CodeTooLong.CODE_TOO_LONG, None
        mycode = "\n".join(lines[start_lineno - 1:end_lineno])
        return CodeTooLong.HAS_SOURCE_CODE, mycode
