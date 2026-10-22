"""生成真实项目逐项差异，供人工审校；不写回历史账本。"""
import copy
import json
from pathlib import Path
import sys

from tests.audit_candidate_usage_reports import differences

NS = "org.rvport.kb-scanner.candidate-usage"


def strip(report):
    report = copy.deepcopy(report)
    for value in (report, *(f["fact"] for f in report["findings"])):
        extensions = value.get("extensions", {})
        extensions.pop(NS, None)
        if not extensions:
            value.pop("extensions", None)
    return report


def key(finding):
    location = finding["occurrences"][0]["location"]
    return finding["fact"]["symbol"], location["file"], location["span"]["start"]["line"], finding["conclusion"]["findingType"]


def audit(before_path, after_path, output):
    before, after = (json.loads(path.read_text()) for path in (before_path, after_path))
    old = json.loads(Path("tests/fixtures/candidate-semantic-admission/libarchive-review.json").read_text())
    historical = {(f["symbol"], f["file"], f["span"]["start"]["line"], f["findingType"]): f for f in old["findings"]}
    historical_ids = {f["id"]: f for f in old["findings"]}
    historical_ids.update({f["review"]["actualResult"]["newId"]: f for f in old["findings"]
        if "newId" in f["review"].get("actualResult", {})})
    before_by_id = {f["id"]: f for f in before["findings"]}
    rows = []
    for finding in after["findings"]:
        symbol, file, line, kind = key(finding)
        previous = historical_ids.get(finding["id"]) or historical.get((symbol, file, line, kind))
        if previous:
            line = previous["span"]["start"]["line"]
        roots = finding["fact"].get("extensions", {}).get(NS, {}).get("roots", ())
        rows.append({"findingId": finding["id"], "historicalId": previous["id"] if previous else None,
            "historicalGroup": previous["review"]["group"] if previous else None,
            "symbol": symbol, "file": file, "line": line,
            "usageStatus": sorted({root["status"] for root in roots}),
            "usageReasons": sorted({code for root in roots for code in root["reasonCodes"]}),
            "currentBaselineConclusionEqual": finding["conclusion"] == before_by_id.get(finding["id"], {}).get("conclusion")})
    missing = [f["id"] for f in old["findings"] if f["id"] not in {r["historicalId"] for r in rows}]
    retained_deduplication = []
    for old_id in tuple(missing):
        item = historical_ids[old_id]
        matching = [f for f in after["findings"] if key(f)[:3] == (item["symbol"], item["file"], item["span"]["start"]["line"])
            and f["conclusion"]["findingType"] == "x86_platform_macro_reference"]
        if item["review"]["implementationStatus"] == "deduplicated_same_fact" and matching and all(f["id"] in before_by_id for f in matching):
            retained_deduplication.append({"historicalId": old_id, "status": "历史已去重，本轮未新增排除",
                "confirmedFindingIds": [f["id"] for f in matching]})
            missing.remove(old_id)
    changes = differences(strip(before), strip(after))
    result = {"change": "implement-kb-scanner-candidate-usage-proofs", "reviewStatus": "待人工确认",
        "historicalCount": len(old["findings"]), "baselineCount": len(before["findings"]),
        "currentCount": len(rows), "unmatchedHistoricalIds": missing, "historicalDeduplications": retained_deduplication,
        "differencesOutsideUsageNamespace": changes, "usage": after.get("extensions", {}).get(NS), "findings": rows}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"usage", "findings"}}, ensure_ascii=False))
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k not in {"findingId", "usageReasons", "historicalId"}}, ensure_ascii=False))
    return 1 if changes or missing else 0


if __name__ == "__main__":
    raise SystemExit(audit(*(Path(value) for value in sys.argv[1:])))
