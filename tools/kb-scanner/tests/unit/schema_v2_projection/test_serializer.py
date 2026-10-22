from __future__ import annotations

import json
import hashlib
import unittest

from kb_scanner.projection.v2.renderers import render_json, render_html, render_html_chunks
from .support import report


class SerializerTests(unittest.TestCase):
    def test_chunked_html_preserves_prechange_artifact_hashes(self):
        value = report()
        hashes = {0: '14f7e6c249556524c52508528164f17095e585357626e807d5c5a80e3036fb29',
                  1: '4d31f33c438cf4108f0822cbbb01c9f0ce063a52143bd961ca9a1686dc6c4764',
                  3: 'fe8cbee9f20e4d68dcb421f46f575f10044889b5f98cb915c145970fa8d47013'}
        for count, expected in hashes.items():
            updated = value.model_copy(update={'findings': value.findings * count})
            chunks = list(render_html_chunks(updated))
            self.assertEqual(count + 2, len(chunks))
            self.assertEqual(expected, hashlib.sha256(b''.join(chunks)).hexdigest())
            self.assertEqual(b''.join(chunks), render_html(updated))

    def test_incremental_findings_match_original_wire_bytes_including_extensions(self):
        from unittest.mock import patch
        value = report()
        for count in (0, 1, 3):
            updated = value.model_copy(update={'findings': value.findings * count,
                'extensions': {'org.rvport.kb-scanner.test': {'null': None, '中文': '测试', 'items': [2, 1]}}})
            expected = (json.dumps(updated.model_dump(mode='json', exclude_none=True),
                ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
            original = type(updated).model_dump
            def guarded(model, *args, **kwargs):
                self.assertEqual({'findings'}, kwargs.get('exclude'))
                return original(model, *args, **kwargs)
            with patch.object(type(updated), 'model_dump', guarded):
                self.assertEqual(expected, render_json(updated))

    def test_json_is_compact_unicode_deterministic_and_newline_terminated(self):
        value = report()
        first = render_json(value)
        second = render_json(value)
        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertNotIn(b"\\u", first)
        self.assertEqual("2.0", json.loads(first)["schemaVersion"])
        self.assertNotIn(b'"trace"', first)
