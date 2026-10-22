import unittest
from dataclasses import replace

from kb_scanner.frontends.build.make_values import Token, Variable, tokens, expand, merge_environments
from kb_scanner.frontends.build.make_effects import MakeEffects
from kb_scanner.frontends.build.macro_arguments import parse_macro_recipes


class MakeValueTests(unittest.TestCase):
    def test_tokens_immediate_and_recursive_expansion(self):
        a = tokens('-DA', 'f', 2, 4)
        self.assertEqual(('f',2,5,8),a[0].source)
        env = {'A':Variable(a),'B':Variable(tokens('$(A)', 'f',3)), 'I':Variable(a,True)}
        out = expand(tokens('${B} $(I) $@','f',4),env,automatic={'$@':'out.o'})
        self.assertEqual(['-DA','-DA','out.o'],[t.text for t in out])
        self.assertEqual([3,4],[span[1] for span in out[0].via])
        for source in ('$(MISSING)','$(SELF)','$(BAD)','@args','a;b','$(B)'):
            limits = {'limit':0} if source=='$(B)' else {}
            self.assertIsNone(expand(tokens(source,'f',1),{**env,'SELF':Variable(tokens('$(SELF)','f',1)),
                'BAD':Variable(None,True)},**limits))
        self.assertIsNone(expand(None,{}))
        self.assertIsNone(expand(a,{},depth=0))

    def test_merging_values_preserves_sources_not_arbitrary_branch(self):
        a=Variable(tokens('-DX','a',1))
        b=Variable(tokens('-DX','b',2))
        merged=merge_environments(({'A':a},{'A':b}))['A']
        self.assertEqual({('a',1,1,4),('b',2,1,4)},set(merged.tokens[0].origins))
        for other in ({},{'A':Variable(None)},{'A':Variable(tokens('-DY','b',1))},{'A':Variable(b.tokens,True)}):
            self.assertIsNone(merge_environments(({'A':a},other))['A'].tokens)
        self.assertIsNone(merge_environments(({}, {'A':a}))['A'].tokens)


class MakeEffectTests(unittest.TestCase):
    def parse(self, text, extra=None):
        return parse_macro_recipes(text,'Makefile',sources=extra)

    def test_include_split_and_explicit_automatic_arguments(self):
        text='include flags.mk\nNAME = X=1\nFLAGS = $(PREFIX) $(NAME)\nx.o: x.cpp\n\tc++ $(FLAGS) -c $< -o $@\n'
        records=self.parse(text,{'flags.mk':'PREFIX = -D\n'})
        recipe=records[-1].metadata['sourceChain']
        self.assertTrue(recipe['proven'])
        self.assertEqual('x.cpp',recipe['source'])
        arg=next(r for r in records if r.kind=='build_argument')
        self.assertEqual('-D',arg.value)
        self.assertEqual('flags.mk',arg.metadata['sourcePath'])
        self.assertEqual('1',arg.metadata['sourceChain']['value'])
        self.assertTrue(any(r.value=='X=1' and r.line==2 for r in records if r.kind=='build_assignment'))

    def test_branches_merge_and_correct_uname(self):
        template='A = -DX=9\n{condition}\nA = -DX=1\nelse\nA = -DX={other}\nendif\nx.o: x.c\n\tcc $(A) -c $<\n'
        for condition,other,value,known in [('ifdef UNKNOWN','1','1',True),('ifdef UNKNOWN','0',None,False),
                ('ifeq (1,1)','0','1',True),('ifneq (1,1)','0','0',True)]:
            result=self.parse(template.format(condition=condition,other=other))
            self.assertEqual(known,result[-1].metadata['sourceChain']['proven'])
            if known:
                self.assertEqual(value,result[0].metadata['sourceChain']['value'])
        result=self.parse('ARCH := $(shell uname -m)\nifeq ($(ARCH),riscv64)\nA=-DX\nelse\nA=-UX\nendif\nx.o: x.c\n\tcc $(A) -c $<\n')
        self.assertTrue(result[-1].metadata['sourceChain']['proven'])
        self.assertEqual('-DX',result[0].value)

    def test_nested_inactive_side_effects_and_absent_else(self):
        result=self.parse('A=-DX\nifeq (0,1)\nifdef X\nA=-UX\nelse\ninclude ../bad\nendif\nendif\nx.o: x.c\n\tcc $(A) -c $<\n')
        self.assertTrue(result[-1].metadata['sourceChain']['proven'])
        self.assertEqual('-DX',result[0].value)
        result=self.parse('ifdef X\nA=-DX\nendif\nx.o: x.c\n\tcc $(A) -c x.c\n')
        self.assertFalse(result[-1].metadata['sourceChain']['proven'])

    def test_order_unknown_target_and_invalid_include(self):
        for line in ('include ../bad','include missing.mk','include /outside','include $(X)',
                     'else','endif','include loop.mk','ifdef X'):
            result=self.parse('A=-DX\n'+line+'\nx.o: x.c\n\tcc $(A) -c x.c\n',{'loop.mk':'include loop.mk'})
            self.assertFalse(result[-1].metadata['sourceChain']['proven'],line)
        result=self.parse('ifdef X\nx.o: x.c\nendif\n\tcc -DX -c x.c\n')
        self.assertFalse(result[-1].metadata['sourceChain']['proven'])
        result=self.parse('A=-DX\nx.o: x.c\n\tcc $(A) -c $<\n\tcc -UX -c $<\n')
        self.assertEqual(2,len([r for r in result if r.kind=='build_configuration']))

    def test_condition_helpers_and_hard_limits(self):
        engine=MakeEffects({'f':''},'f')
        self.assertIsNone(engine.condition('ifeq','bad','f',1))
        self.assertIsNone(engine.condition('ifeq','($(X),1)','f',1))
        self.assertIsNone(engine.condition('ifndef','X','f',1))
        engine.env={'X':Variable(())}
        self.assertTrue(engine.condition('ifndef','X','f',1))
        engine.visits=128
        engine.read('f')
        self.assertIn('make-include-unresolved-or-budget',engine.reasons)
        engine=MakeEffects({'f':'A=1'},'f')
        engine.events=100000
        engine.read('f')
        self.assertIn('make-event-budget',engine.reasons)
        engine.read('f',tuple(str(i) for i in range(8)))
        self.assertIn('make-include-unresolved-or-budget',engine.reasons)
        engine=MakeEffects({'f':'ifdef X\nelse\nelse\nendif'},'f')
        self.assertIn('make-malformed-condition',engine.reasons)

    def test_compiler_override_preprocessor_options_and_included_recipe(self):
        for command, expected in [('CXX=g++',True),('CXX=wrapper',False),('CXX=$(MISSING)',False)]:
            result=self.parse(command+'\nx.o: x.c\n\t$(CXX) -DX -c x.c\n')
            self.assertEqual(expected,result[-1].metadata['sourceChain']['proven'])
        self.assertFalse(self.parse('x.o: x.c\n\tcc -include extra.h -DX -c x.c\n')[-1].metadata['sourceChain']['proven'])
        result=self.parse('include rules.mk',{'rules.mk':'x.o: x.c\n\n\tcc -DX -c x.c\n'})
        self.assertEqual('rules.mk',result[-1].metadata['sourcePath'])
        self.assertEqual(1,result[-1].metadata['sourceChain']['targetLine'])
        self.assertTrue(result[-1].metadata['sourceChain']['proven'])
