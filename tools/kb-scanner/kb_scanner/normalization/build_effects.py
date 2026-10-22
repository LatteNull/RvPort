"""检查多来源参数的实例内引用；不修改原始 Evidence。"""
from collections import defaultdict


def validate_effects(evidence):
    origins = defaultdict(list)
    for item in evidence:
        data = item.metadata.get('sourceChain', {})
        if data.get('useId') and data.get('role') in {'argument','origin'}:
            origins[data['useId'], data['key']].append(item)
    invalid = set()
    for item in evidence:
        data = item.metadata.get('sourceChain', {})
        if not data.get('originKeys'):
            continue
        if not data.get('useId') or type(data.get('order')) is not int or data['order'] < 0:
            invalid.add(item.id)
            continue
        for key in data['originKeys']:
            matches = origins.get((data['useId'], key), ())
            locations = {m.location for m in matches}
            configurations = {m.metadata.get('configuration') for m in matches if m.metadata.get('configuration')}
            expected = item.metadata.get('configuration')
            if not matches or None in locations or len(locations) != 1 or len(configurations) > 1 or (expected and configurations and configurations != {expected}):
                invalid.add(item.id)
    return frozenset(invalid)
