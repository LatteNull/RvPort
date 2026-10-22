"""Bounded Bash syntax consumer for RPM script sections. No command execution."""
from __future__ import annotations
from dataclasses import replace
import re

from tree_sitter import Language, Parser
import tree_sitter_bash

from ..safety import symbolic_uname
from .conditions import conjunction, negate
from .macros import Value


def parse_scripts(source, lines, records):
    groups = {}
    for entry in lines:
        ctx = entry[3]
        groups.setdefault((ctx['package'],ctx['section'],ctx['parents'][-1:]),[]).append(entry)
    for group in groups.values():
        indexed = {line:(raw,env,ctx) for line,raw,env,ctx in group}
        # Preserve original rows/bytes for every code occurrence.
        masked = '\n'.join(raw if number in indexed else '' for number,raw in enumerate(source.splitlines(),1))
        data = masked.encode('utf-8')
        tree = Parser(Language(tree_sitter_bash.language())).parse(data)
        engine = Script(data,indexed,records)
        engine.run(tree.root_node.named_children,{},True,(),0)
        if tree.root_node.has_error:
            records.damage(engine.start,'rpm-shell-partial-syntax')
            records.diagnostics.append(f'{records.path}: RPM shell partial syntax')


class Script:
    def __init__(self,data,indexed,records):
        self.data,self.indexed,self.records = data,indexed,records
        self.start = len(records.items)
        self.remaining = 10000

    def text(self,node):
        return self.data[node.start_byte:node.end_byte].decode('utf-8') if node is not None else ''

    def context(self,node,active,parents):
        line = self.data.count(b'\n',0,node.start_byte)+1
        start = self.data.rfind(b'\n',0,node.start_byte)+1
        column = len(self.data[start:node.start_byte].decode('utf-8'))+1
        raw,env,ctx = self.indexed[line]
        return line,column,env,{**ctx,'active':conjunction(active,ctx['active']),
                                 'parents':tuple(dict.fromkeys((*ctx['parents'],*parents)))}

    def value(self,text,variables,env):
        expanded = env.expand(text)
        if expanded.text is None:
            return expanded
        text = expanded.text
        # A macro that manufactures shell structure is not parsed from the raw tree.
        if expanded.names and re.search(r'[\n;`]|\$\(', text):
            return replace(expanded,text=None,reason='rpm-generated-shell-structure')
        if text.startswith("'") and text.endswith("'"):
            return replace(expanded,text=text[1:-1])
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        probe = symbolic_uname(text,env.target) if text.startswith(('$(', '`')) else None
        if probe is not None and probe.recognized:
            return Value(probe.value,expanded.refs,(*expanded.names,'uname -m'))
        if '$(' in text or '`' in text or '\\' in text:
            return replace(expanded,text=None,reason='rpm-shell-value-unsupported')
        refs,names = list(expanded.refs),list(expanded.names)
        missing = False
        def substitute(match):
            nonlocal missing
            name = match.group(1) or match.group(2)
            value = variables.get(name,Value(reason='rpm-shell-variable-unknown'))
            refs.extend(value.refs); names.extend(value.names)
            if value.text is None:
                missing = True
            return value.text or ''
        text = re.sub(r'\$\{([A-Za-z_][\w]*)\}|\$([A-Za-z_][\w]*)',substitute,text)
        if '$' in text or re.search(r'["\'\n]',text):
            missing = True
        return Value(None if missing else text,tuple(dict.fromkeys(refs)),tuple(dict.fromkeys(names)),
                     'rpm-shell-variable-unknown' if missing else '')

    def condition(self,node,variables,env):
        text = self.text(node).strip()
        match = re.fullmatch(r'(?:\[\s+|test\s+)(.+?)\s+(==|=|!=)\s+(.+?)(?:\s+\])?',text)
        if not match:
            return None,()
        left = self.value(match.group(1),variables,env)
        right = self.value(match.group(3),variables,env)
        truth = None if left.text is None or right.text is None else left.text == right.text
        return negate(truth) if match.group(2)=='!=' else truth,(*left.refs,*right.refs)

    def run(self,nodes,variables,active,parents,depth,hypothetical=False):
        for node in nodes:
            self.remaining -= 1
            line,col,env,ctx = self.context(node,active,parents)
            if depth >= 64 or self.remaining < 0:
                self.records.unknown(self.text(node).splitlines()[0],line,'rpm-shell-budget',**ctx)
                return {k:replace(v,text=None,reason='rpm-shell-budget') for k,v in variables.items()}
            if node.type == 'comment':
                continue
            if node.type == 'variable_assignment':
                name = self.text(node.child_by_field_name('name'))
                value_node = node.child_by_field_name('value')
                raw_value = self.text(value_node)
                macro = self.records.expand(env,raw_value,line,col + self.text(node).find(raw_value),**ctx)
                value = self.value(raw_value,variables,env).with_refs(*macro.refs)
                key = self.records.emit('build_assignment',self.text(node).splitlines()[0],line,col,**{
                    **ctx,'parents':(*ctx['parents'],*value.refs)},
                    variable=name,resolvedValue=value.text,valueKnown=value.text is not None,reason=value.reason)
                if 'uname -m' in value.names:
                    probe_key = self.records.emit('build_arch_probe',raw_value,line,col + self.text(node).find(raw_value),**ctx,
                                                  resolvedValue=env.target,architectureRelated=True)
                    value = value.with_refs(probe_key)
                    self._add_parent(key,probe_key)
                if ctx['active'] is not False:
                    value = value.with_refs(key)
                    if ctx['active'] is None and not hypothetical:
                        old = variables.get(name,Value())
                        value = Value(value.text if old.text==value.text else None,
                                      tuple(dict.fromkeys((*old.refs,*value.refs))),value.names,'rpm-shell-assignment-conditional')
                    variables[name] = value
                if name in {'CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','SOURCES','SRCS'}:
                    for token in re.finditer(r'-[A-Za-z][\w=+.,/-]*|[\w./-]+\.(?:c|cc|cpp|cxx|S|s)\b',raw_value):
                        kind = 'build_argument' if token.group().startswith('-') else 'build_source'
                        prefix = raw_value[:token.start()]
                        row = line + prefix.count('\n')
                        column = col+self.text(node).find(raw_value)+token.start() if '\n' not in prefix else len(prefix.rsplit('\n',1)[1])+1
                        self.records.emit(kind,token.group(),row,column,
                                          **{**ctx,'parents':(*ctx['parents'],key)},
                                          valueKnown=value.text is not None,buildUseKnown=False,
                                          reason='rpm-script-build-use-unknown' if ctx['active'] is not False else '')
            elif node.type in {'if_statement','case_statement'}:
                variables = self.selection(node,variables,ctx['active'],ctx['parents'],depth+1)
            elif node.type in {'program','compound_statement'}:
                variables = self.run(node.named_children,variables,ctx['active'],ctx['parents'],depth+1,hypothetical)
            else:
                key = self.records.unknown(self.text(node).splitlines()[0],line,'rpm-shell-command-unsupported',**ctx)
                if ctx['active'] is not False:
                    variables = {name:replace(value.with_refs(key),text=None,reason='rpm-shell-side-effect-unknown')
                                 for name,value in variables.items()}
        return variables

    def _add_parent(self,key,parent):
        for index,item in enumerate(self.records.items):
            if item.metadata['rpm']['key']==key:
                rpm = {**item.metadata['rpm'],'parents':(*item.metadata['rpm']['parents'],parent)}
                self.records.items[index] = replace(item,metadata={**item.metadata,'rpm':rpm})
                break

    def selection(self,node,variables,active,parents,depth):
        line,col,env,ctx = self.context(node,active,parents)
        arms = []
        if node.type == 'if_statement':
            children = list(node.named_children)
            condition = node.child_by_field_name('condition') or children[0]
            body = [n for n in children if n is not condition and n.type not in {'elif_clause','else_clause'}
                    and n.start_byte >= condition.end_byte]
            arms.append((condition,body,self.condition(condition,variables,env)))
            for child in children:
                if child.type == 'elif_clause':
                    first,*body = child.named_children
                    arms.append((first,body,self.condition(first,variables,env)))
                elif child.type == 'else_clause':
                    arms.append((child,child.named_children,(True,())))
        else:
            selector = node.child_by_field_name('value')
            value = self.value(self.text(selector),variables,env).with_refs(*self.selector_refs(selector,active,parents))
            for child in node.named_children:
                if child.type != 'case_item':
                    continue
                pattern_nodes = [n for i,n in enumerate(child.children) if child.field_name_for_child(i)=='value']
                patterns = [self.text(n) for n in pattern_nodes]
                literal = all(p=='*' or re.fullmatch(r'[\w.-]+',p) for p in patterns)
                truth = None if value.text is None or not literal else any(p=='*' or p==value.text for p in patterns)
                if re.search(r'(?:;&|;;&)',self.text(child)):
                    truth = None
                body = [n for n in child.named_children if n not in pattern_nodes]
                arms.append((child,body,(truth,value.refs)))
        remaining = True
        alternatives = []
        preceding = []
        for origin,body,(truth,refs) in arms:
            arm_active = conjunction(active,conjunction(remaining,truth))
            row,column,_,arm_ctx = self.context(origin,arm_active,parents)
            if node.type == 'if_statement' and origin.type != 'else_clause':
                refs = (*refs,*self.selector_refs(origin,active,parents))
            key = self.records.emit('build_branch',self.text(origin).splitlines()[0],row,column,**{
                **arm_ctx,'parents':(*parents,*preceding,*refs)},conditionGroup=f'{self.records.path}:{line}:{col}',
                conditionTruth=truth,reason='' if truth is not None else 'rpm-shell-condition-unknown')
            branch_variables = self.run(body,dict(variables),arm_active,(*parents,key),depth,True)
            if arm_active is not False:
                alternatives.append(branch_variables)
            preceding.append(key)
            remaining = conjunction(remaining,negate(truth))
        if remaining is not False:
            alternatives.append(variables)
        if not alternatives:
            return variables
        result = {}
        for name in set().union(*(branch.keys() for branch in alternatives)):
            values = [branch.get(name,Value()) for branch in alternatives]
            text = values[0].text if all(v.text==values[0].text for v in values) else None
            result[name] = Value(text,tuple(dict.fromkeys(r for v in values for r in v.refs)),
                                 tuple(dict.fromkeys(n for v in values for n in v.names)),
                                 '' if text is not None else 'rpm-shell-branch-conflict')
        return result

    def selector_refs(self,node,active,parents):
        line,column,env,ctx = self.context(node,active,parents)
        raw = self.text(node)
        value = self.records.expand(env,raw,line,column,**ctx)
        refs = list(value.refs)
        # Bash expansions inside single-quoted literal strings are not probes.
        for match in re.finditer(r"'[^']*'|\$\([^()]*\)|`[^`]*`", raw):
            if match.group().startswith("'"):
                continue
            probe = symbolic_uname(match.group(),env.target)
            if probe.recognized:
                refs.append(self.records.emit('build_arch_probe',match.group(),line,column+match.start(),
                                              **ctx,resolvedValue=env.target,architectureRelated=True))
        return tuple(refs)
