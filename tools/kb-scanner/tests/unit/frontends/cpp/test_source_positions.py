from __future__ import annotations

import unittest
from unittest.mock import patch

from kb_scanner.frontends.cpp.source_positions import SourceByteIndex


class SourceByteIndexTests(unittest.TestCase):
    def test_scalar_coordinates_equal_validated_locations_without_constructing_dtos(self):
        for source in (b'', b'a\n\nbc\n', '// 中文\r\nabc\r\n'.encode()):
            index = SourceByteIndex.build('a.cpp', source)
            for start in range(len(source)+1):
                for end in range(start, len(source)+1):
                    span = index.span(start, end)
                    with patch('kb_scanner.frontends.cpp.source_positions.SourceLocation',
                               side_effect=AssertionError('scalar span must not construct DTO')):
                        self.assertEqual((span.start.line, span.start.column, span.end.line, span.end.column),
                                         index.coordinate_span(start, end))
        index = SourceByteIndex.build('a.cpp', b'abc')
        for start, end in ((True, 2), (0, False), ('0', 1), (0, 1.5)):
            with self.assertRaises(TypeError):
                index.coordinate_span(start, end)
        for start, end in ((-1, 0), (0, 4), (2, 1)):
            with self.assertRaises(ValueError):
                index.coordinate_span(start, end)

    def test_empty_source_and_eof_are_valid(self) -> None:
        index = SourceByteIndex.build("empty.c", b"")
        self.assertEqual((0,), index.line_starts)
        self.assertEqual((1, 1), (index.location(0).line, index.location(0).column))
        span = index.span(0, 0)
        self.assertEqual(span.start, span.end)

    def test_lf_empty_lines_and_eof_after_newline(self) -> None:
        index = SourceByteIndex.build("lf.c", b"a\n\nbc\n")
        expected = {
            0: (1, 1),
            1: (1, 2),
            2: (2, 1),
            3: (3, 1),
            5: (3, 3),
            6: (4, 1),
        }
        for offset, location in expected.items():
            actual = index.location(offset)
            self.assertEqual(location, (actual.line, actual.column))

    def test_crlf_and_utf8_columns_are_byte_based(self) -> None:
        source = "é\r\n中x".encode("utf-8")
        index = SourceByteIndex.build("utf8.c", source)
        self.assertEqual((1, 3), (index.location(2).line, index.location(2).column))
        second_line = source.index("中".encode("utf-8"))
        self.assertEqual((2, 1), (index.location(second_line).line, index.location(second_line).column))
        after_multibyte = second_line + len("中".encode("utf-8"))
        self.assertEqual((2, 4), (index.location(after_multibyte).line, index.location(after_multibyte).column))

    def test_long_line_and_multiline_span(self) -> None:
        source = b"a\n" + (b"x" * 4096) + b"\nz"
        index = SourceByteIndex.build("long.c", source)
        span = index.span(10, 4100)
        self.assertEqual((2, 9), (span.start.line, span.start.column))
        self.assertEqual((3, 2), (span.end.line, span.end.column))

    def test_invalid_offsets_and_ranges_are_rejected(self) -> None:
        index = SourceByteIndex.build("bad.c", b"abc")
        for value in (-1, 4):
            with self.assertRaises(ValueError):
                index.location(value)
        for value in (True, 1.5, "1"):
            with self.assertRaises(TypeError):
                index.location(value)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            index.span(2, 1)
        with self.assertRaises(ValueError):
            index.span(0, 4)
        with self.assertRaises(TypeError):
            SourceByteIndex.build("bad.c", bytearray(b"x"))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
