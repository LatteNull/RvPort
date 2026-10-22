from __future__ import annotations

import unittest
import json

from kb_scanner.projection.v2.renderers import render_html, render_json, render_log
from .support import report


class RendererTests(unittest.TestCase):
    def test_json_preserves_both_languages_html_only_uses_escaped_chinese(self):
        original = report()
        finding = original.findings[0]
        conclusion = finding.conclusion.model_copy(update={
            "suggestion": '请核查 <RISC-V> & "通用" 路径。',
            "suggestion_en": "ENGLISH_SENTINEL: review <generic> & target paths.",
        })
        updated = original.model_copy(update={"findings": (finding.model_copy(update={"conclusion": conclusion}),)})
        wire = json.loads(render_json(updated))
        self.assertEqual(conclusion.suggestion, wire["findings"][0]["conclusion"]["suggestion"])
        self.assertEqual(conclusion.suggestion_en, wire["findings"][0]["conclusion"]["suggestion_en"])
        html = render_html(updated).decode("utf-8")
        self.assertIn('charset="utf-8"', html)
        self.assertIn("请核查 &lt;RISC-V&gt; &amp; &quot;通用&quot; 路径。", html)
        self.assertNotIn("ENGLISH_SENTINEL", html)
        self.assertEqual(render_log(original), render_log(updated))

    def test_historical_html_and_json_do_not_invent_english_field(self):
        value = report()
        self.assertIn(value.findings[0].conclusion.suggestion, render_html(value).decode())
        self.assertNotIn("suggestion_en", json.loads(render_json(value))["findings"][0]["conclusion"])

    def test_html_and_log_share_report_semantics_and_escape_content(self):
        value = report()
        finding = value.findings[0]
        conclusion = finding.conclusion.model_copy(update={"title": "<unsafe>"})
        value = value.model_copy(update={"findings": (finding.model_copy(update={"conclusion": conclusion}),)})
        html = render_html(value).decode()
        log = render_log(value).decode()
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertIn(value.findings[0].id, log)
        self.assertIn("compiled=false linked=false testsExecuted=false", log)
        self.assertIn("Primary path", html)
