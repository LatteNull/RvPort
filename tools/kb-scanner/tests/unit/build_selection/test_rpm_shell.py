import unittest
from types import SimpleNamespace
from unittest.mock import patch
from kb_scanner.frontends.build.rpm.shell import Script,parse_scripts
from kb_scanner.frontends.build.rpm.records import Records
from kb_scanner.frontends.build.rpm.macros import MacroEnv,Value


class Node:
    def __init__(self,kind,start,end,children=(),fields=None):
        self.type,self.start_byte,self.end_byte=kind,start,end
        self.children=self.named_children=list(children)
        self.fields=fields or {};self.has_error=False
    def child_by_field_name(self,name): return self.fields.get(name)
    def field_name_for_child(self,index):
        child=self.children[index]
        return 'value' if child.type=='extglob_pattern' else next((key for key,value in self.fields.items() if value is child),None)


def setup(source):
    data=source.encode();env=MacroEnv('riscv64');records=Records('x.spec')
    lines=[(line,raw,env.copy(),{'active':True,'parents':(),'package':'main','section':'build'})
           for line,raw in enumerate(source.splitlines(),1)]
    script=Script(data,{line:(raw,env,ctx) for line,raw,env,ctx in lines},records)
    def make(kind,text,start=0,children=(),fields=None):
        offset=data.index(text.encode(),start)
        return Node(kind,offset,offset+len(text.encode()),children,fields)
    def assignment(text,start=0):
        name,body=text.split('=',1);offset=data.index(text.encode(),start)
        n=make('variable_name',name,offset);v=make('word',body,offset+len(name)+1)
        return make('variable_assignment',text,offset,(n,v),{'name':n,'value':v})
    return script,records,lines,make,assignment


class RpmShellTests(unittest.TestCase):
    def test_values_and_condition_shapes(self):
        s,r,_,make,_=setup('[ "$machine" != "x86_64" ]\ntest "$machine" = riscv64\nbad\n')
        env=MacroEnv('riscv64');variables={'machine':Value('riscv64',('a',))}
        for raw,expected in [('$(uname -m)','riscv64'),('`uname -m`','riscv64'),("'$machine'",'$machine'),
                             ('"$machine"','riscv64'),('${machine}','riscv64'),('text','text'),
                             ('"$(uname -m)"','riscv64'), ('"uname -m"','uname -m'), ("'$(uname -m)'",'$(uname -m)')]:
            self.assertEqual(expected,s.value(raw,variables,env).text)
        for raw in ('$(touch x)','`touch x`','a\\b','$missing','$1','%{external}','"a"b', '%{generated}'):
            env.define('generated','x; evil','g')
            self.assertIsNone(s.value(raw,variables,env).text,raw)
        a=make('test_command','[ "$machine" != "x86_64" ]')
        self.assertEqual((True,('a',)),s.condition(a,variables,env))
        b=make('command','test "$machine" = riscv64')
        self.assertTrue(s.condition(b,variables,env)[0])
        self.assertIsNone(s.condition(b,{},env)[0])
        self.assertIsNone(s.condition(make('command','bad'),{},env)[0])

    def test_selector_references_and_equal_unknown_branch_merge(self):
        source='if [ "$(uname -m)" = "%{_arch}" ]; then\nX=one\nelse\nX=one\nfi'
        s,r,_,make,assign=setup(source)
        cond=make('test_command','[ "$(uname -m)" = "%{_arch}" ]')
        else_=make('else_clause','else\nX=one',children=(assign('X=one',source.index('else')),))
        node=make('if_statement',source,children=(cond,assign('X=one'),else_),fields={'condition':cond})
        self.assertEqual('one',s.run([node],{},True,(),0)['X'].text)
        self.assertEqual({'$(uname -m)','%{_arch}'},{x.value for x in r.items if x.kind=='build_arch_probe'})
        with patch.object(s,'condition',return_value=(None,())):
            self.assertEqual('one',s.run([node],{},True,(),0)['X'].text)
        s,r,_,make,_=setup("'$(uname -m)' $(touch x)")
        self.assertEqual((),s.selector_refs(make('word',"'$(uname -m)' $(touch x)"),True,()))

    def test_assignment_probe_sources_and_unknown_command(self):
        multiline='CFLAGS="-mavx\n  -msse %{_arch}"\n'
        ms,mr,_,_,ma=setup(multiline)
        ms.run([ma(multiline.strip())],{},True,(),0)
        self.assertEqual([('-mavx',1,9),('-msse',2,3)],[(r.value,r.line,r.start_column) for r in mr.items if r.kind=='build_argument'])
        for item in mr.items:
            self.assertEqual(item.value,multiline.splitlines()[item.line-1][item.start_column-1:item.end_column-1])
        source='machine=$(uname -m)\nCFLAGS="-mavx -O2"\nSOURCES="src/a.c"\nunknown\n# hi\n'
        s,r,_,make,assign=setup(source)
        nodes=[assign('machine=$(uname -m)'),assign('CFLAGS="-mavx -O2"'),assign('SOURCES="src/a.c"'),
               make('command','unknown'),make('comment','# hi')]
        result=s.run(nodes,{},True,(),0)
        self.assertIsNone(result['machine'].text)
        self.assertTrue(any(x.kind=='build_arch_probe' for x in r.items))
        self.assertEqual(['-mavx','-O2','src/a.c'],[x.value for x in r.items if x.kind in {'build_argument','build_source'}])
        s._add_parent('missing','unused')
        s2,r2,_,_,assign2=setup('X=one')
        self.assertNotIn('X',s2.run([assign2('X=one')],{},False,(),0))
        self.assertIsNone(s2.run([assign2('X=one')],{},None,(),0)['X'].text)
        self.assertEqual('one',s2.run([assign2('X=one')],{'X':Value('one')},None,(),0)['X'].text)

    def test_if_else_and_elif(self):
        source='if [ "$machine" = x86_64 ]; then\nX=one\nelif test "$machine" = riscv64; then\nX=two\nelse\nX=three\nfi\n'
        s,r,_,make,assign=setup(source)
        cond=make('test_command','[ "$machine" = x86_64 ]')
        c2=make('command','test "$machine" = riscv64')
        elif_=make('elif_clause','elif test "$machine" = riscv64; then\nX=two',children=(c2,assign('X=two')))
        else_=make('else_clause','else\nX=three',children=(assign('X=three'),))
        node=make('if_statement',source.strip(),children=(cond,assign('X=one'),elif_,else_),fields={'condition':cond})
        variables={'machine':Value('riscv64',('probe',))}
        result=s.run([node],variables,True,(),0)
        self.assertEqual('two',result['X'].text)
        self.assertEqual(['inactive','selected','inactive'],[x.metadata['selectionStatus'] for x in r.items if x.kind=='build_branch'])
        self.assertIsNone(s.selection(node,{},True,(),0)['X'].text)
        self.assertEqual({},s.selection(node,{},False,(),0))

    def test_case_first_match_unknown_patterns_and_remaining(self):
        source='case "$machine" in\nx86_64|amd64) X=one ;;\nriscv64) X=two ;;\n*) X=three ;;\nesac\n'
        s,r,_,make,assign=setup(source)
        value=make('string','"$machine"')
        arms=[]
        for pattern,assignment in [('x86_64|amd64','X=one'),('riscv64','X=two'),('*','X=three')]:
            armtext=f'{pattern}) {assignment} ;;'
            children=[make('extglob_pattern',part,source.index(armtext)) for part in pattern.split('|')]
            arms.append(make('case_item',armtext,children=(*children,assign(assignment))))
        node=make('case_statement',source.strip(),children=(value,*arms),fields={'value':value})
        self.assertEqual('two',s.run([node],{'machine':Value('riscv64')},True,(),0)['X'].text)
        self.assertEqual(['inactive','selected','inactive'],[x.metadata['selectionStatus'] for x in r.items if x.kind=='build_branch'])
        self.assertIsNone(s.run([node],{},True,(),0)['X'].text)
        node.children=node.named_children=[value,arms[0]]
        self.assertNotIn('X',s.run([node],{'machine':Value('other')},True,(),0))
        badsource='case "$machine" in\nrisc*) X=one ;&\nesac'
        s,r,_,make,assign=setup(badsource);value=make('string','"$machine"')
        arm=make('case_item','risc*) X=one ;&',children=(make('extglob_pattern','risc*'),assign('X=one')))
        node=make('case_statement',badsource,children=(value,arm),fields={'value':value})
        self.assertIsNone(s.run([node],{'machine':Value('riscv64')},True,(),0)['X'].text)

    def test_budget_compound_and_real_parser_boundary_fake(self):
        source='X=one\n'
        s,r,lines,make,assign=setup(source);assignment=assign('X=one')
        root=Node('program',0,len(source),[assignment]);root.has_error=True
        with patch('kb_scanner.frontends.build.rpm.shell.Language'), \
             patch('kb_scanner.frontends.build.rpm.shell.tree_sitter_bash.language'), \
             patch('kb_scanner.frontends.build.rpm.shell.Parser',return_value=SimpleNamespace(parse=lambda data:SimpleNamespace(root_node=root))):
            parse_scripts(source,lines,r)
        self.assertTrue(r.diagnostics)
        self.assertTrue(all(x.metadata['selectionStatus']=='unknown' for x in r.items))
        self.assertEqual('one',s.run([root],{},True,(),0)['X'].text)
        self.assertIsNone(s.run([assignment],{'X':Value('old')},True,(),64)['X'].text)
        s.remaining=0
        self.assertIsNone(s.run([assignment],{'X':Value('old')},True,(),0)['X'].text)
