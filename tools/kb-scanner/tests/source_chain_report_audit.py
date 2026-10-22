"""Compare fixed-input V2 reports and audit every returned source/context line."""
import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    before, after = (json.loads((p / 'scan-result.json').read_text()) for p in (args.before, args.after))
    old = {f['id']: f for f in before['findings']}
    errors, files = [], {}
    locations = lines_checked = highlights_checked = 0
    context_characters = 0
    for f in after['findings']:
        previous = old.pop(f['id'], None)
        if previous is None or previous['conclusion'] != f['conclusion']:
            errors.append('finding/conclusion changed: ' + f['id'])
        if previous:
            stable = lambda fact: {k:v for k,v in fact.items() if k != 'primaryLocation'}
            if stable(previous['fact']) != stable(f['fact']):
                errors.append('fact changed: ' + f['id'])
        chain = f['evidenceChain']
        steps = {s['id']: s for s in chain['steps']}
        pairs = {(e['fromStepId'], e['toStepId']) for e in chain['edges']}
        if chain['impactStepIds'] or any(s['kind'] in {'classification', 'assessment'} for s in chain['steps']):
            errors.append('stage node/impact present')
        if any(pair not in pairs for pair in zip(chain['primaryPath'], chain['primaryPath'][1:])):
            errors.append('disconnected primary path')
        if any(steps[sid]['kind'] == 'knowledge_match' for sid in chain['primaryPath']):
            errors.append('knowledge on primary path')
        sources = [f['fact']['primaryLocation'], *(o['location'] for o in f['occurrences']), *(s['source'] for s in chain['steps'] if 'source' in s)]
        for source in sources:
            locations += 1
            path = (args.source / source['file']).resolve()
            if not path.is_relative_to(args.source.resolve()):
                errors.append('root escape')
                continue
            if path not in files:
                files[path] = path.read_text().splitlines()
            original = files[path]
            context = source['context']
            by_line = {line['line']: line['text'] for line in context['lines']}
            for number, text in by_line.items():
                lines_checked += 1
                context_characters += len(text)
                if number < 1 or number > len(original) or original[number-1] != text:
                    errors.append(f'context mismatch: {path}:{number}')
            for hit in context['highlights']:
                highlights_checked += 1
                if hit['line'] not in by_line or not 1 <= hit['startColumn'] < hit['endColumn'] <= len(by_line[hit['line']])+1:
                    errors.append('invalid highlight: ' + source['file'])
            if len(by_line) > 256 or sum(map(len, by_line.values())) > 65536:
                errors.append('context exceeds hard budget')
    if old: errors.append('removed findings: ' + str(len(old)))
    if before['summary'] != after['summary']: errors.append('summary changed')
    report = {'passed': not errors, 'errors': errors, 'findings': len(after['findings']),
              'locationsChecked': locations, 'contextLinesChecked': lines_checked,
              'highlightsChecked': highlights_checked, 'contextCharacters': context_characters,
              'uniqueFiles': len(files), 'chainStates': dict(Counter(f['evidenceChain']['status'] for f in after['findings']))}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
