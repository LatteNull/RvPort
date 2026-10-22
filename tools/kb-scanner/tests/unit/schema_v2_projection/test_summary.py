from __future__ import annotations

import unittest

from kb_scanner.core import Assessment, AssessmentSnapshot, WorkspaceSnapshot, stable_id
from kb_scanner.projection.v2.summary import V2SummaryReducer
from .support import report


class SummaryTests(unittest.TestCase):
    def test_reduces_only_v2_findings(self):
        value = report()
        result = V2SummaryReducer().reduce(WorkspaceSnapshot(__import__("pathlib").Path.cwd(), ("a.c",)), value.findings, AssessmentSnapshot(), input_complete=True)
        self.assertEqual(1, result.findings)
        self.assertEqual(1, result.blocking)
        self.assertEqual("provisional", result.readiness)

    def test_zero_findings_and_incomplete_input_never_claim_ready(self):
        workspace = WorkspaceSnapshot(__import__("pathlib").Path.cwd(), ())
        result = V2SummaryReducer().reduce(workspace, (), AssessmentSnapshot(), input_complete=False)
        self.assertEqual("unknown", result.readiness)
        self.assertIsNone(result.portabilityGaps)
        self.assertEqual(("missing_input",), result.reasonCodes)

    def test_project_assessment_states_drive_readiness(self):
        workspace = WorkspaceSnapshot(__import__("pathlib").Path.cwd(), ())
        def assessments(state):
            return AssessmentSnapshot((Assessment(stable_id("assessment", state), "project_migration_state", state),))
        reducer = V2SummaryReducer()
        self.assertEqual("x86_only", reducer.reduce(workspace, (), assessments("riscv_blocked"), input_complete=True).readiness)
        self.assertEqual("ready", reducer.reduce(workspace, (), assessments("ready"), input_complete=True).readiness)
        self.assertEqual("provisional", reducer.reduce(workspace, (), assessments("needs_review"), input_complete=True).readiness)
