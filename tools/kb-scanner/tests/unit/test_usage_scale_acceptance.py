"""规模门禁不执行真实 parser 或扫描子进程。"""
from copy import deepcopy
import unittest

from tests.performance.usage_acceptance import ARTIFACTS, STAGES, accept_pair


def valid_pair():
    common = {"references": 10000, "density": "sparse", "seconds": 20,
              "exitCode": 0, "maxRssKiB": 500000, "expectedRoots": 96,
              "artifactsBytes": dict.fromkeys(ARTIFACTS, 100),
              "stages": [{"stage": key, "event": "end"}
                         for key in STAGES | {"candidate_usage_index_and_query"}]}
    return [{**deepcopy(common), "mode": "disabled", "findings": 96, "excludedCount": 0},
            {**deepcopy(common), "mode": "enabled", "findings": 0, "excludedCount": 96,
             "statistics": {"rootCount": 96, "scopeIndexes": 4, "recordCount": 644,
                            "visits": 12288, "cacheHits": 0}}]


class UsageScaleAcceptanceTests(unittest.TestCase):
    def test_added_cost_is_diagnostic_and_input_is_not_modified(self):
        pair = valid_pair()
        pair[1]["seconds"] = 25
        saved = deepcopy(pair)
        result = accept_pair(pair, 10000, "sparse")
        self.assertTrue(result["passed"])
        self.assertEqual(result["costComparison"], {
            "deltaSeconds": 5, "deltaPercent": 25, "legacyRelativeGatePassed": False})
        self.assertEqual(pair, saved)

    def test_old_threshold_boundaries_remain_diagnostic(self):
        for before, after, expected in ((20, 22, True), (1, 2, True), (20, 19, True), (20, 23, False)):
            pair = valid_pair()
            pair[0]["seconds"], pair[1]["seconds"] = before, after
            result = accept_pair(pair, 10000, "sparse")
            self.assertTrue(result["passed"])
            self.assertEqual(result["costComparison"]["legacyRelativeGatePassed"], expected)

    def test_dense_budget_boundary_is_accepted_without_exclusions(self):
        pair = valid_pair()
        for item in pair:
            item.update(density="dense", expectedRoots=9600, findings=9600, excludedCount=0)
        pair[1]["statistics"].update(rootCount=9600, scopeIndexes=400, recordCount=100000, visits=1000000)
        self.assertTrue(accept_pair(pair, 10000, "dense")["passed"])

    def test_incomplete_pair_and_failed_child_cannot_pass(self):
        self.assertFalse(accept_pair([], 10000, "sparse")["passed"])
        for code in (-9, 124, 139, 1):
            result = accept_pair([{"exitCode": code}, {"exitCode": code}], 10000, "sparse")
            self.assertFalse(result["passed"])
            self.assertIsNone(result["costComparison"])

    def test_invalid_metrics_fail_closed(self):
        changes = [("mode", "disabled"), ("references", 20000), ("density", "dense"),
                   ("seconds", 300), ("seconds", 0), ("seconds", float("nan")),
                   ("maxRssKiB", 2097152), ("maxRssKiB", 0),
                   ("artifactsBytes", {}), ("artifactsBytes", dict.fromkeys(ARTIFACTS, 0)),
                   ("stages", []), ("expectedRoots", 0), ("excludedCount", 95), ("statistics", {})]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                pair = valid_pair()
                pair[1][key] = value
                self.assertFalse(accept_pair(pair, 10000, "sparse")["passed"])
        for key, value in (("rootCount", 95), ("scopeIndexes", 5), ("recordCount", 100001),
                           ("visits", 1000001), ("cacheHits", 97)):
            pair = valid_pair()
            pair[1]["statistics"][key] = value
            self.assertFalse(accept_pair(pair, 10000, "sparse")["passed"])


if __name__ == "__main__":
    unittest.main()
