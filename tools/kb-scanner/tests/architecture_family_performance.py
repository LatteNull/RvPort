"""Repeatable container-only measurements and source report differential."""
import argparse
import json
from pathlib import Path
import time
import tracemalloc
from unittest.mock import patch

from kb_scanner.core import ScanRequest, StageResult
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.analyzers.architecture_family.grouping import FamilyBudget, discover
from kb_scanner.projection.v2.families import NAMESPACE
from tests.unit.test_architecture_family import sources

ROOT = Path(__file__).resolve().parents[1]


def measure(output):
    records = []
    for size in (10000, 20000):
        entities = sources(*(f"src/f{i}_{role}.cpp" for i in range(size//2) for role in ("x86", "generic")))
        tracemalloc.start()
        start = time.perf_counter()
        catalog = discover(entities, FamilyBudget())
        seconds = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert catalog["bucketOperations"] == size
        assert catalog["familyCount"] == size//2
        records.append({"paths":size, "seconds":seconds, "peakBytes":peak, "bucketOperations":catalog["bucketOperations"]})
    project_records = []
    projects = {"demo": ROOT/"tests/fixtures/cmake-demo-test1",
                "family-demo": ROOT/"tests/fixtures/architecture-family-demo"}
    for name, path in projects.items():
        assert path.is_dir(), path
        reports, timings = [], []
        family_time = [0.0]
        from kb_scanner.analyzers.architecture_family import ArchitectureFamilyAnalyzer
        original = ArchitectureFamilyAnalyzer.analyze
        def timed(self, *args):
            start = time.perf_counter()
            result = original(self, *args)
            family_time[0] += time.perf_counter() - start
            return result
        for enabled in (False, True):
            target = output/f"{name}-{'family' if enabled else 'baseline'}"
            with patch.object(ArchitectureFamilyAnalyzer, "analyze", timed if enabled else lambda self,c,f,k,b: StageResult(b)):
                start = time.perf_counter()
                result = create_default_application().run(ScanRequest(str(path),str(ROOT/"rulesets/riscv-porting"),str(target)))
                timings.append(time.perf_counter()-start)
            assert result.exit_code == 0, result.diagnostics
            reports.append(json.loads((target/"scan-result.json").read_text()))
        family_count = reports[1].get("extensions",{}).get(NAMESPACE,{}).get("familyCount",0)
        for report in reports:
            report.pop("extensions",None)
            for finding in report["findings"]:
                ext = finding["fact"].get("extensions",{})
                ext.pop(NAMESPACE,None)
                if not ext:
                    finding["fact"].pop("extensions",None)
        assert reports[0] == reports[1], f"unexpected non-family report changes: {name}"
        over = family_time[0] > max(1.0, timings[0]*.1)
        assert not over, (name,timings,family_time)
        project_records.append({"project":name, "baselineSeconds":timings[0], "familySeconds":timings[1],
                                "familyAnalyzerSeconds":family_time[0], "families":family_count, "semanticDifferential":"identical"})
    return {"synthetic":records,"projects":project_records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    payload = measure(args.output)
    (args.output/"performance.json").write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))
