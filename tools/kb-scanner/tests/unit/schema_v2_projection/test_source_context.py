from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from kb_scanner.core import SourceLocation, SourceSpan
from kb_scanner.core.location import normalize_project_path
from kb_scanner.projection.v2.context import SourceContextProjector


class SourceContextTests(unittest.TestCase):
    def test_normalized_paths_and_immutable_budgets_are_scan_local(self):
        projector = SourceContextProjector(Path('/project'), reader=lambda _: 'abcde\n' * 100)
        with patch('kb_scanner.projection.v2.context.normalize_project_path', wraps=normalize_project_path) as normalize:
            first = projector.project(self.span())
            second = projector.project(self.span(41))
            normalize.assert_called_once_with('a.c')
            fresh = SourceContextProjector(Path('/project'), reader=lambda _: 'abcde\n' * 100).project(self.span())
            self.assertEqual(2, normalize.call_count)
        self.assertEqual(first.model_dump(), fresh.model_dump())
        self.assertIs(first.context.budget, second.context.budget)
        self.assertIsNot(first.context.budget, fresh.context.budget)
        self.assertFalse(first.context.budget.truncated)
        self.assertTrue(projector._budget(True).truncated)
        self.assertIsNot(first.context.budget, projector._budget(True))
        with self.assertRaises(ValueError):
            first.context.budget.truncated = True

    def test_overlapping_windows_share_lines_but_not_highlights_or_snapshots(self):
        reader = lambda path: ("other" if path.name == "b.c" else "abcde") + "\n"
        projector = SourceContextProjector(Path('/project'), reader=reader)
        first = projector.project(self.span(1, column=1, end_column=2))
        second = projector.project(self.span(1, column=2, end_column=3))
        self.assertIs(first.context.lines[0], second.context.lines[0])
        self.assertNotEqual(first.context.highlights, second.context.highlights)
        other = projector.project(SourceSpan(SourceLocation('b.c', 1, 1), SourceLocation('b.c', 1, 2)))
        self.assertEqual('other', other.context.lines[0].text)
        self.assertIsNot(first.context.lines[0], other.context.lines[0])
        fresh = SourceContextProjector(Path('/project'), reader=reader).project(self.span(1, column=1, end_column=2))
        self.assertEqual(first.model_dump(), fresh.model_dump())
        self.assertIsNot(first.context.lines[0], fresh.context.lines[0])

    def test_path_resolution_and_escape_are_cached_only_for_current_snapshot(self):
        reader = Mock(return_value="abcde\n" * 100)
        projector = SourceContextProjector(Path('/project'), reader=reader)
        with patch.object(Path, 'resolve', return_value=Path('/project/a.c')) as resolve:
            projector.project(self.span())
            projector.project(self.span(41))
            resolve.assert_called_once()
        reader.assert_called_once()
        blocked = SourceContextProjector(Path('/project'), reader=Mock(side_effect=AssertionError('outside')))
        with patch.object(Path, 'resolve', return_value=Path('/outside/a.c')) as resolve:
            self.assertEqual('unavailable', blocked.project(self.span()).context.status)
            self.assertEqual('unavailable', blocked.project(self.span(41)).context.status)
            resolve.assert_called_once()
        blocked._reader.assert_not_called()

    @staticmethod
    def span(start=40, end=None, column=2, end_column=4):
        return SourceSpan(SourceLocation("a.c", start, column), SourceLocation("a.c", end or start, end_column))

    def test_default_single_and_multiline_windows_preserve_exact_highlights(self):
        reader = Mock(return_value="abcde\r\n" * 100)
        projector = SourceContextProjector(Path("/project"), reader=reader)
        single = projector.project(self.span())
        self.assertEqual(list(range(20, 61)), [line.line for line in single.context.lines])
        self.assertEqual((40, 2, 4), tuple(single.context.highlights[0].model_dump().values()))
        multi = projector.project(self.span(end=43))
        self.assertEqual(list(range(20, 64)), [line.line for line in multi.context.lines])
        self.assertEqual([40, 41, 42, 43], [h.line for h in multi.context.highlights])
        self.assertEqual((20, 20, 256, 65536, False), tuple(multi.context.budget.model_dump().values()))
        self.assertIs(single, projector.project(self.span()))
        reader.assert_called_once()

    def test_line_and_character_budgets_prioritize_hits_then_balance_neighbors(self):
        for options in ({"max_lines": 5}, {"max_characters": 25}):
            with self.subTest(options=options):
                context = SourceContextProjector(Path("/p"), reader=lambda _: "abcde\n" * 100, **options).project(self.span()).context
                self.assertEqual([38, 39, 40, 41, 42], [line.line for line in context.lines])
                self.assertEqual([40], [h.line for h in context.highlights])
                self.assertEqual("partial", context.status)
                self.assertEqual(("context_budget_exceeded",), context.reasonCodes)

    def test_oversized_hit_is_bounded_without_fabricated_columns(self):
        projector = SourceContextProjector(Path("/p"), reader=lambda _: "small\n" + "x" * 70000 + "\nsmall")
        source = projector.project(self.span(2, column=69999, end_column=70001))
        self.assertEqual([1, 3], [line.line for line in source.context.lines])
        self.assertEqual((), source.context.highlights)
        self.assertEqual(69999, source.span.start.column)
        self.assertEqual("partial", source.context.status)
        self.assertTrue(source.context.budget.truncated)
        all_hit = SourceContextProjector(Path("/p"), reader=lambda _: "x" * 70000).project(self.span(1))
        self.assertEqual((), all_hit.context.lines)
        self.assertEqual("partial", all_hit.context.status)

    def test_multiline_hit_over_budget_and_invalid_source_coordinates(self):
        projector = SourceContextProjector(Path("/p"), max_lines=2, reader=lambda _: "abcde\n" * 5)
        result = projector.project(self.span(2, end=4))
        self.assertEqual([2, 3], [line.line for line in result.context.lines])
        self.assertEqual(4, result.span.end.line)
        self.assertTrue(result.context.budget.truncated)
        for text, span in (("", self.span(1)), ("\n", self.span(1)), ("abc", self.span(1, column=9, end_column=10)),
                           ("abc", self.span(1, end=2))):
            with self.subTest(text=text, span=span):
                result = SourceContextProjector(Path("/p"), reader=lambda _: text).project(span)
                self.assertIn(result.context.status, {"partial", "unavailable"})
                self.assertEqual(("context_unavailable",), result.context.reasonCodes)

    def test_unknown_columns_caps_and_empty_windows(self):
        projector = SourceContextProjector(Path("/p"), before=0, after=0, max_lines=999, max_characters=999999, reader=lambda _: "abc\ndef")
        source = projector.project(self.span(1, end=2, column=None, end_column=None))
        self.assertEqual([(1, 1, 4), (2, 1, 4)], [(h.line, h.startColumn, h.endColumn) for h in source.context.highlights])
        self.assertEqual((256, 65536), (source.context.budget.maxLines, source.context.budget.maxCharacters))
        for options in ({"before": -1}, {"after": -1}, {"max_lines": 0}, {"max_characters": 0}):
            with self.assertRaises(ValueError):
                SourceContextProjector(Path("/p"), **options)

    def test_exclusive_end_at_next_line_or_eof_does_not_invent_a_highlight(self):
        for text in ("#define X 1\n", "#define X 1\n\n"):
            source = SourceContextProjector(Path("/p"), reader=lambda _: text).project(self.span(1, end=2, column=1, end_column=1))
            self.assertEqual("complete", source.context.status)
            self.assertEqual([1], [h.line for h in source.context.highlights])
            self.assertEqual(2, source.span.end.line)

    def test_reader_and_split_cache_are_scan_local_and_failures_cached(self):
        value = Mock()
        value.splitlines.return_value = ["abcde"] * 100
        reader = Mock(return_value=value)
        projector = SourceContextProjector(Path("/p"), reader=reader)
        projector.project(self.span())
        projector.project(self.span(41))
        projector.project(self.span())
        reader.assert_called_once()
        value.splitlines.assert_called_once()
        SourceContextProjector(Path("/p"), reader=reader).project(self.span())
        self.assertEqual(2, reader.call_count)
        for error in (OSError(), UnicodeError()):
            reader = Mock(side_effect=error)
            projector = SourceContextProjector(Path("/p"), reader=reader)
            self.assertEqual("unavailable", projector.project(self.span()).context.status)
            self.assertEqual("unavailable", projector.project(self.span(41)).context.status)
            reader.assert_called_once()

    def test_resolved_escape_does_not_read_source(self):
        projector = SourceContextProjector(Path("/project"), reader=Mock(side_effect=AssertionError("outside root")))
        with patch.object(Path, "resolve", return_value=Path("/elsewhere/a.c")):
            result = projector.project(self.span())
        self.assertEqual("unavailable", result.context.status)
        projector._reader.assert_not_called()

    def test_projects_real_unicode_lines_and_caches_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.c").write_text("一\ntwo\n命中 token\nfour\nfive\n", encoding="utf-8")
            reads = []
            reader = lambda path: reads.append(path) or path.read_text(encoding="utf-8")
            projector = SourceContextProjector(root, reader=reader)
            span = SourceSpan(SourceLocation("a.c", 3, 4), SourceLocation("a.c", 3, 9))
            first = projector.project(span)
            second = projector.project(span)
            self.assertEqual("complete", first.context.status)
            self.assertEqual((4, 9), (first.context.highlights[0].startColumn, first.context.highlights[0].endColumn))
            self.assertEqual(first, second)
            self.assertEqual(1, len(reads))

    def test_missing_decode_and_budget_return_explicit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            span = SourceSpan(SourceLocation("missing.c", 1, 1), SourceLocation("missing.c", 1, 2))
            self.assertEqual("unavailable", SourceContextProjector(root).project(span).context.status)
            failing = SourceContextProjector(root, reader=lambda _: (_ for _ in ()).throw(UnicodeError()))
            self.assertEqual("unavailable", failing.project(span).context.status)
            (root / "long.c").write_text("123456789\n" * 10, encoding="utf-8")
            long_span = SourceSpan(SourceLocation("long.c", 5, 1), SourceLocation("long.c", 5, 3))
            context = SourceContextProjector(root, max_lines=3, max_characters=12).project(long_span).context
            self.assertEqual("partial", context.status)
            self.assertTrue(context.budget.truncated)

    def test_file_end_and_out_of_range_are_handled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.c").write_text("x\ny", encoding="utf-8")
            projector = SourceContextProjector(root)
            end = projector.project(SourceSpan(SourceLocation("a.c", 2, 1), SourceLocation("a.c", 2, 2)))
            self.assertEqual([1, 2], [line.line for line in end.context.lines])
            missing = projector.project(SourceSpan(SourceLocation("a.c", 9, 1), SourceLocation("a.c", 9, 2)))
            self.assertEqual("unavailable", missing.context.status)
