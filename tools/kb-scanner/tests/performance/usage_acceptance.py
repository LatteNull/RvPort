"""用途规模验收：功能成本对照与绝对资源/完整性门禁分离。"""
import math


STAGES = {"workspace_collector", "knowledge_provider", "frontend", "normalizer",
          "analyzer", "detector", "classifier", "assessor", "report_projector",
          "V2FindingMapper", "V2ReferentialIntegrityValidator", "AtomicArtifactPublisher"}
ARTIFACTS = {"scan-result.json", "scan-report.html", "scan.log"}


def accept_pair(pair, references, density):
    """拒绝缺失/错误指标；旧 10% 且 1 秒门槛只保留为诊断。"""
    failures = []
    functions = references // 25
    scopes = functions if density == "dense" else (functions + 99) // 100
    roots = 24 * scopes
    if len(pair) != 2:
        return {"passed": False, "failures": ["开关对照不完整"], "costComparison": None}
    for mode, item in zip(("disabled", "enabled"), pair):
        if item.get("exitCode") != 0:
            failures.append(f"{mode}: 子进程失败或超时")
            continue
        if (item.get("mode"), item.get("references"), item.get("density")) != (mode, references, density):
            failures.append(f"{mode}: 样本身份不符")
        seconds, rss = item.get("seconds", -1), item.get("maxRssKiB", -1)
        if not math.isfinite(seconds) or not 0 < seconds < 300 or not 0 < rss < 2097152:
            failures.append(f"{mode}: 超出时间/内存边界或缺失指标")
        artifacts = item.get("artifactsBytes", {})
        if set(artifacts) != ARTIFACTS or not all(value > 0 for value in artifacts.values()):
            failures.append(f"{mode}: 三工件不完整")
        ends = {event["stage"] for event in item.get("stages", ()) if event.get("event") == "end"}
        required = STAGES | ({"candidate_usage_index_and_query"} if mode == "enabled" else set())
        if not required <= ends:
            failures.append(f"{mode}: 阶段计时不完整")
        if item.get("expectedRoots") != roots or item.get("findings", 0) + item.get("excludedCount", 0) != roots:
            failures.append(f"{mode}: 候选完整性不符")
    after = pair[1]
    stats = after.get("statistics", {})
    bounds = {"rootCount": (roots, roots), "scopeIndexes": (0, scopes),
              "recordCount": (0, 100000), "visits": (0, 1000000), "cacheHits": (0, roots)}
    if any(not low <= stats.get(key, -1) <= high for key, (low, high) in bounds.items()):
        failures.append("用途统计缺失、重复作用域索引或访问/记录超预算")
    before_seconds, after_seconds = pair[0].get("seconds", 0), after.get("seconds", 0)
    cost = None
    if before_seconds > 0 and after_seconds > 0:
        delta = after_seconds - before_seconds
        cost = {"deltaSeconds": delta, "deltaPercent": 100 * delta / before_seconds,
                "legacyRelativeGatePassed": not (delta > 1 and delta > before_seconds * 0.1)}
    return {"passed": not failures, "failures": failures, "costComparison": cost}
