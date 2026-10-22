"""Produce candidate report diffs for human review, never rewrite an oracle."""
import hashlib
import json
from pathlib import Path
import sys

from kb_scanner.cli import main

ROOT=Path('/workspace/tools/kb-scanner')
CASES=('architecture-candidate-noise','source-evidence-chain','architecture-enum','rpm-architecture')


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def run(output):
    ledger={'fixtures':{},'after':{}}
    for fixture in CASES:
        ledger['fixtures'][fixture]={}
        for version in ('1.0','2.0'):
            target=output/fixture/version
            if main(['scan','--input',str(ROOT/'tests/fixtures'/fixture),'--rules',str(ROOT/'rulesets/riscv-porting'),
                     '--output',str(target),'--schema-version',version]):
                raise RuntimeError('scan failed')
            payload=json.loads((target/'scan-result.json').read_text())
            data={'after':digest(payload),'logSha256':hashlib.sha256((target/'scan.log').read_bytes()).hexdigest()}
            if version=='2.0':
                for finding in payload['findings']:
                    finding['conclusion'].pop('suggestion',None)
                    finding['conclusion'].pop('suggestion_en',None)
                data['strippedSha256']=digest(payload)
            else:
                data['strippedSha256']=None
            ledger['fixtures'][fixture][version]=data
            if fixture==CASES[0]: ledger['after'][version]=data['after']
    (output/'candidate-hashes.json').write_text(json.dumps(ledger,indent=2))


def matrix(output):
    from tests.test_compatible_cutover_differential import run as scan, semantic_signature
    from kb_scanner.pipeline.default import create_default_application
    matrix=json.loads((ROOT/'tests/fixtures/compatible-cutover/matrix-differential-golden-v1.json').read_text())
    signatures={}
    output.mkdir(parents=True,exist_ok=True)
    for entry in matrix['entries']:
        fixture=Path(entry['path'])
        if not fixture.is_absolute(): fixture=ROOT/fixture
        result,payload=scan(create_default_application(),fixture)
        signatures[entry['id']]=semantic_signature(payload,result,fixture)
        (output/(entry['id']+'.json')).write_text(json.dumps(payload,ensure_ascii=False))
    (output/'candidate-signatures.json').write_text(json.dumps(signatures,indent=2))


if __name__=='__main__':
    (matrix if '--matrix' in sys.argv else run)(Path(sys.argv[1]))
