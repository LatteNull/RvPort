"""Project target usage requirements into bounded, source-specific events."""
from collections import defaultdict
from dataclasses import replace
from pathlib import PurePosixPath
import posixpath
import re

from ..adapters import AdapterResult
from .macro_conflicts import macro_conflicts


def bind_usage(results, *, max_items=10000, max_depth=32):
    output = {p:list(r.records) for p,r in results.items()}
    diagnostics = {p:list(r.diagnostics) for p,r in results.items()}
    arguments, links, declarations = defaultdict(list), defaultdict(list), {}
    sources, directory_args = [], []
    for path, part in sorted(results.items()):
        for record in part.records:
            info = record.metadata['cmake']
            target = info.get('target')
            if record.kind == 'build_target' and target:
                if target not in declarations or record.metadata['selectionStatus'] != 'inactive':
                    declarations[target] = (path, record)
            elif record.kind == 'build_source' and info.get('source'):
                sources.append((path, record))
            elif record.kind == 'build_argument':
                if 'directory' in info:
                    directory_args.append((path, record))
                elif target:
                    arguments[target].append((path, record))
            elif record.kind == 'build_dependency' and target:
                links[target].append((path, record))
    count = 0
    visits = 0

    def requirements(target, exporting=False, trail=()):
        nonlocal visits
        visits += 1
        if visits > max_items or target in trail or len(trail) >= max_depth or target not in declarations:
            return [], False
        values, complete = [], True
        allowed = {'PUBLIC','INTERFACE'} if exporting else {'PUBLIC','PRIVATE'}
        for path, record in arguments[target]:
            if record.metadata['cmake'].get('visibility') in allowed:
                values.append((path, record, ()))
        for path, link in links[target]:
            if link.metadata['cmake'].get('visibility') not in allowed:
                continue
            if link.metadata['selectionStatus'] == 'inactive':
                continue
            nested, ok = requirements(link.value, True, (*trail,target))
            complete &= ok and link.metadata['selectionStatus'] == 'selected'
            values.extend((p,r,(*parents,link.metadata['cmake']['key'])) for p,r,parents in nested)
        return values, complete

    for path, source in sources:
        info = source.metadata['cmake']
        # INTERFACE sources are not own compilation units. Retain them unknown
        # until a source propagation proof exists, never bind own compile flags.
        if info.get('visibility') == 'INTERFACE':
            continue
        target = info.get('target')
        values, complete = requirements(target)
        declaration_path, declaration = declarations.get(target, (path,source))
        directory = declaration.metadata['cmake'].get('directory', str(PurePosixPath(declaration_path).parent))
        for p,r in directory_args:
            d = r.metadata['cmake']['directory']
            same_scope_definition = d == directory and r.metadata['cmake'].get('commandName') == 'add_compile_definitions'
            if (d == '.' or directory == d or directory.startswith(d+'/')) and (same_scope_definition or r.metadata['cmake']['order'] < declaration.metadata['cmake']['order']):
                values.append((p,r,()))
        values.sort(key=lambda item: (item[1].metadata['cmake']['order'],item[0],item[1].line,item[1].start_column))
        conflicts = macro_conflicts(values)
        if conflicts:
            complete = False
            diagnostics[path].extend(sorted(set(conflicts.values())))
        binding_key = info['key']+':usage'
        binding_args = []
        for index,(p,record,parents) in enumerate(values):
            count += 1
            if count > max_items:
                complete = False
                diagnostics[path].append('cmake-usage-budget')
                break
            original = record.metadata['cmake']
            state = source.metadata['selectionStatus']
            if not complete or record.metadata['selectionStatus'] == 'unknown':
                state = 'unknown'
            elif record.metadata['selectionStatus'] == 'inactive':
                continue
            key = original['key']+':use:'+info['key']
            metadata = {**record.metadata, 'selectionStatus':state,
                'cmake':{**original,'key':key,'parents':tuple(dict.fromkeys((info['key'], original['key'],*parents))),
                         'effective':True,'target':target,'source':info['source']}}
            match = re.fullmatch(r'(-D|-U)([A-Za-z_]\w*)(?:=(.*))?',record.value)
            if match and not (match[1] == '-U' and match[3] is not None):
                data = {'role':'argument','key':key,'order':index,'recipeLine':source.line,
                        'macro':match[2],'operation':match[1],'value':match[3] if match[3] is not None else '1'}
                metadata['sourceChain'] = data
                binding_args.append(data)
            elif record.value.startswith(('-D','-U','-include','-imacros','-Wp,','-undef','-Xpreprocessor')):
                complete = False
            output[p].append(replace(record,metadata=metadata))
        binding = {'role':'recipe','key':binding_key,'target':target,'source':posixpath.relpath(info['source'], str(PurePosixPath(path).parent)),
                   'arguments':tuple(binding_args),'proven':complete and source.metadata['selectionStatus']=='selected'}
        if conflicts:
            binding['macroConflicts'] = conflicts
        metadata = {**source.metadata,'sourceChain':binding,
                    'cmake':{**info,'key':binding_key,'parents':(info['key'],),'binding':True}}
        output[path].append(replace(source,kind='build_configuration',metadata=metadata))
    return {p:AdapterResult(tuple(records),tuple(sorted(set(diagnostics[p]))),bool(diagnostics[p])) for p,records in output.items()}
