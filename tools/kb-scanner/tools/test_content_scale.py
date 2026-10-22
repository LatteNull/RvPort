"""独立容器内的 1 万/2 万原始断言规模入口；每组用独立进程运行。"""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import resource
import time
from unittest.mock import patch

from kb_scanner.cli import main
from kb_scanner.analyzers.test_content import TestContentAnalyzer, CATALOG
from kb_scanner.pipeline.default import create_default_profile
from tests.performance.observation import observe
from tests.performance.support import verify_limits, digest


def source(count, density):
    if count < 100 or count % 100 or density not in {"plain", "sparse", "dense"}:
        raise ValueError("use a positive multiple of 100 and a known density")
    bodies=[]
    for index in range(count//100):
        anchor=density=="dense" or density=="sparse" and index==0
        bodies.append(f"void f{index}(){{\n"+
            ("int value=_mm_cvtsi128_si32(_mm_setzero_si128());\n" if anchor else "int value=42;\n")+
            "assert(value==42);\n"*100+"}\n")
    return "".join(bodies)+"int main(){"+"".join(f"f{i}();" for i in range(count//100))+"}\n"


def accept(metrics, density):
    return (metrics["exitCode"]==0 and metrics["artifactCount"]==3
        and metrics["queries"]<=metrics["visitedFacts"]<=20000
        and metrics["contentRecords"]<=100000
        and (metrics["queries"]>0 if density!="plain" else metrics["queries"]==0)
        and (metrics["partialInventories"]>0 if density=="dense" else True))


def run(output, count, density):
    limits=verify_limits(lambda p:p.read_text())
    output.mkdir(parents=True,exist_ok=False)
    project=output/"input"; project.mkdir()
    text=source(count,density)
    (project/"unit.c").write_text(text)
    (project/"CMakeLists.txt").write_text("enable_testing()\nadd_executable(unit unit.c)\nadd_test(NAME original COMMAND unit)\n")
    counters={"queries":0,"visitedFacts":0,"contentRecords":0,"partialInventories":0}
    events=[]
    original=TestContentAnalyzer.analyze
    def analyzed(self,context,facts,knowledge,base):
        counters["contentRecords"]=sum(e.metadata["testContent"]["recordCount"] for e in facts.evidence if e.kind=="test_content")
        counters["partialInventories"]=sum(e.metadata["testContent"]["status"]!="complete" for e in facts.evidence if e.kind=="test_content")
        started=time.perf_counter()
        result=original(self,context,facts,knowledge,base)
        counters["analysisSeconds"]=time.perf_counter()-started
        for entity in result.value.entities:
            if entity.kind==CATALOG:
                counters.update({k:entity.properties[k] for k in ("queries","visitedFacts")})
        return result
    start=time.perf_counter()
    with ExitStack() as guards:
        guards.enter_context(patch.object(TestContentAnalyzer,"analyze",analyzed))
        guards.enter_context(patch("kb_scanner.pipeline.default.create_default_profile",
            side_effect=lambda:observe(create_default_profile(),events.append)))
        guards.enter_context(patch("subprocess.run",side_effect=AssertionError("禁止执行被扫描项目")))
        code=main(["scan","--input",str(project),"--rules","rulesets/riscv-porting","--output",str(output/"report")])
    artifacts={p.name:p.stat().st_size for p in (output/"report").glob("*")}
    metrics={"assertions":count,"density":density,"exitCode":code,"artifactCount":len(artifacts),
        "artifactsBytes":artifacts,"seconds":time.perf_counter()-start,
        "maxRssKiB":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"limits":limits,
        "inputHash":hashlib.sha256(text.encode()).hexdigest(),
        "sourceDigest":digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path("kb_scanner").rglob("*.py"))}),
        "stages":events,**counters}
    metrics["passed"]=accept(metrics,density)
    (output/"metrics.json").write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics),flush=True)
    return 0 if metrics["passed"] else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--assertions",type=int,choices=(10000,20000),required=True)
    parser.add_argument("--density",choices=("plain","sparse","dense"),required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.output,args.assertions,args.density))
