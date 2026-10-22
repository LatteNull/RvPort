"""独立容器性能验收入口；baseline 仅禁用本轮新增阶段，不执行被扫描代码。"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import resource
from time import perf_counter
from unittest.mock import patch

from kb_scanner.pipeline.default import create_default_application
from kb_scanner.core import StageResult, ScanRequest
from kb_scanner.frontends.cpp.function_inventory import inventory
from kb_scanner.analyzers.function_multiversion.analysis import FunctionMultiversionAnalyzer, CATALOG_KIND
from kb_scanner.analyzers.function_multiversion.grouping import Budget


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,choices=(10000,20000),required=True)
    parser.add_argument('--mode',choices=('baseline','current','budget'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    project=args.output/str(args.count)/'input'
    project.mkdir(parents=True,exist_ok=True)
    lines=[('__attribute__((target_clones("avx2,default"))) ' if i%1000==0 else '')+
           f'int f{i}(int n){{'+('_mm256_setzero_ps();' if i%1000==0 else '')+f'return n+{i};}}' for i in range(args.count)]
    (project/'sparse.cpp').write_text('\n'.join(lines))
    metrics={'functionCount':args.count,'mode':args.mode,'inventorySeconds':0.0,'analysisSeconds':0.0}
    original=FunctionMultiversionAnalyzer.analyze
    def measured_inventory(*values,**kwargs):
        start=perf_counter()
        result=inventory(*values,**kwargs)
        metrics['inventorySeconds']+=perf_counter()-start
        metrics['functionEvidenceCount']=sum(e.kind=='function_declaration' for e in result)
        return result
    def measured_analysis(self,*values):
        if args.mode=='budget':
            self.budget=Budget(groups=1,versions=1,associations=0)
        start=perf_counter()
        result=original(self,*values)
        metrics['analysisSeconds']+=perf_counter()-start
        catalog=next(e.properties for e in result.value.entities if e.kind==CATALOG_KIND)
        metrics.update({k:catalog[k] for k in ('declarationCount','retainedDeclarationCount','groupCount','associationCount','discoveryStatus')})
        metrics['retainedGroups']=len(catalog['groups'])
        metrics['defaultGaps']=sum(g['defaultGap'] for g in catalog['groups'])
        return result
    with ExitStack() as stack:
        if args.mode=='baseline':
            stack.enter_context(patch('kb_scanner.frontends.cpp.tree_sitter_adapter.inventory',side_effect=lambda *v,**kw:v[6]))
            stack.enter_context(patch.object(FunctionMultiversionAnalyzer,'analyze',side_effect=lambda *v:StageResult(v[-1])))
        else:
            stack.enter_context(patch('kb_scanner.frontends.cpp.tree_sitter_adapter.inventory',side_effect=measured_inventory))
            stack.enter_context(patch.object(FunctionMultiversionAnalyzer,'analyze',measured_analysis))
        start=perf_counter()
        result=create_default_application().run(ScanRequest(str(project),str(Path.cwd()/'rulesets/riscv-porting'),str(args.output/str(args.count)/args.mode)))
        metrics['scanSeconds']=perf_counter()-start
    metrics.update(exitCode=result.exit_code,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (args.output/f'{args.count}-{args.mode}.json').write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics),flush=True)
    return result.exit_code


if __name__=='__main__':
    raise SystemExit(main())
