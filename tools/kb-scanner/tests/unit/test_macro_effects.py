from dataclasses import replace
import unittest

from kb_scanner.analyzers.macro_effects import MacroEffectIndex, Token, arguments
from kb_scanner.analyzers.macro_state import MacroState
from tests.unit.test_macro_session import event
from kb_scanner.core import stable_id


def macro(name, parameters, tokens, line=1, **metadata):
    definition = event(name, 'macro_definition', name, line, functionLike=True)
    items = [definition]
    for ordinal, parameter in enumerate(parameters):
        items.append(event(name+'-p-'+str(ordinal), 'macro_parameter', parameter, line,
                           ordinal=ordinal, macroDefinitionEvidenceId=name))
    for ordinal, token in enumerate(tokens):
        items.append(event(name+'-t-'+str(ordinal), 'macro_replacement_token', token, line,
                           ordinal=ordinal, macroDefinitionEvidenceId=name, **metadata))
    return tuple(items)


def invocation(name='OUTER', arguments_values=(('intrinsic',), ('x',))):
    attachments, args = [], []
    for ordinal, values in enumerate(arguments_values):
        copied = []
        for index, value in enumerate(values):
            item = event('arg-'+str(ordinal)+'-'+str(index), 'macro_argument_token', value, 10)
            attachments.append(item)
            copied.append({'value': value, 'evidenceId': item.id})
        args.append(tuple(copied))
    call = event('call', 'call_expression', name, 10, macroCall={'status': 'complete', 'arguments': tuple(args)})
    return call, tuple(attachments)


class MacroEffectTests(unittest.TestCase):
    def test_argument_references_cannot_borrow_other_calls_producers_or_contexts(self):
        definitions = macro('OUTER', ('fn','a'), ('fn','(','a',')'))
        call, args = invocation()
        env = {'OUTER':MacroState(True,'body',definitions[0].id,function_like=True)}
        for changed in (None,replace(args[0],kind='comment'),replace(args[0],subject_id=stable_id('other')),
                        replace(args[0],value='different'),replace(args[0],metadata={'callEvidenceId':'other'}),
                        replace(args[0],metadata={'compilationContextId':'other'})):
            records = (*definitions,call,*args[1:],*((changed,) if changed else ()))
            self.assertEqual(('invalid-macro-argument-reference',),MacroEffectIndex(records).resolve(call,env).reasons)
        numeric = replace(call,metadata={'macroCall':{'status':'complete','arguments':(({'value':'12'},),({'value':'0'},))}})
        self.assertEqual((),MacroEffectIndex((*definitions,numeric)).resolve(numeric,env).paths)

    def test_reverse_demand_is_fact_based_transitive_bounded_and_order_independent(self):
        outer = macro('OUTER', ('fn','a'), ('INNER','(','fn',',','a',')'))
        inner = macro('INNER', ('fn','a'), ('fn','(','a',')'), 2)
        alias = macro('ALIAS', (), ('intrinsic',), 3)
        call, args = invocation(arguments_values=(('ALIAS',),('x',)))
        records = (*outer,*inner,*alias,call,*args)
        for values in (records,tuple(reversed(records))):
            index = MacroEffectIndex(values, {'intrinsic'})
            self.assertEqual({call.id},index.demanded_calls)
            self.assertEqual(len(records),len(index.evidence))
            self.assertEqual(set(),MacroEffectIndex(values, set()).demanded_calls)
        fixed, _ = invocation('ALIAS', ())
        cycle = macro('CYCLE', (), ('CYCLE','ALIAS'), 4)
        self.assertEqual({fixed.id},MacroEffectIndex((*alias,*cycle,fixed),{'intrinsic'}).demanded_calls)
        orphan = replace(alias[-1], metadata={'macroDefinitionEvidenceId':'missing'})
        self.assertFalse(MacroEffectIndex((orphan,call,*args),{'intrinsic'}).demanded_calls)

    def resolve(self, definitions, call=None, extra=None, **limits):
        default, attachments = invocation()
        call = call or default
        index = MacroEffectIndex((*definitions, call, *attachments))
        env = {str(item.value): MacroState(True, 'body', item.id, function_like=True)
               for item in definitions if item.kind == 'macro_definition'}
        env.update(extra or {})
        return index.resolve(call, env, **limits)

    def test_nested_forwarding_links_original_actual_parameters_and_replacements(self):
        outer = macro('OUTER', ('fn','a'), ('INNER','(','fn',',','a',')'))
        inner = macro('INNER', ('fn','a'), ('fn','(','a',')'), 2)
        result = self.resolve((*outer,*inner))
        self.assertEqual((), result.reasons)
        self.assertEqual(1, len(result.paths))
        path = result.paths[0]
        self.assertEqual(stable_id('call'), path[0])
        self.assertEqual(stable_id('arg-0-0'), path[-1])
        self.assertIn(stable_id('OUTER-p-0'), path)
        self.assertIn(stable_id('INNER-p-0'), path)
        self.assertNotIn(stable_id('arg-1-0'), path)
        self.assertGreater(result.expanded_tokens, 0)

    def test_unused_and_noncalled_parameters_are_not_execution_proofs(self):
        for body in (('a',), ('store','(','fn',')'), ('1',)):
            result = self.resolve(macro('OUTER', ('fn','a'), body))
            self.assertFalse(any(path[-1] == stable_id('arg-0-0') for path in result.paths))
        self.assertEqual((), self.resolve(()).paths)
        self.assertEqual((), self.resolve(macro('OUTER', ('fn','a'), ('fn',))).paths)
        nested = self.resolve(macro('OUTER', ('fn','a'), ('store','(','fn','(','a',')',')')))
        self.assertTrue(any(path[-1] == stable_id('arg-0-0') for path in nested.paths))
        self.assertFalse(self.resolve(macro('OUTER', ('fn','a'), ('fn','(','a',')'), tokenRole='comment')).paths)

    def test_conflicts_unsupported_cycles_missing_and_limits_remain_unknown(self):
        simple = macro('OUTER', ('fn','a'), ('fn','(','a',')'))
        for extra, reason in (({'OUTER': MacroState(None,None,'x')}, 'macro-definition-unknown-or-conflicting'),
                              ({'OUTER': MacroState(True,'1','missing')}, 'macro-definition-source-missing'),
                              ({'OUTER': MacroState(True,'1',stable_id('OUTER'))}, 'unsupported-object-call'),
                              ({'OUTER': MacroState(True,'1',stable_id('OUTER'),('other',))}, 'macro-definition-unknown-or-conflicting')):
            self.assertIn(reason, self.resolve(simple, extra=extra).reasons)
        self.assertEqual((), self.resolve(simple, extra={'OUTER': MacroState(False,None,'x')}).paths)
        self.assertIn('macro-token-budget', self.resolve(simple, token_limit=1).reasons)
        self.assertIn('macro-expansion-cycle-or-depth', self.resolve(simple, depth_limit=0).reasons)
        recursive = macro('OUTER', ('fn','a'), ('OUTER','(','fn',',','a',')'))
        self.assertIn('macro-expansion-cycle-or-depth', self.resolve(recursive).reasons)
        self.assertIn('macro-argument-count', self.resolve(macro('OUTER', ('a',), ('a',))).reasons)
        self.assertIn('unsupported-macro-semantics', self.resolve(macro('OUTER', ('fn','a'), ('#','fn'), unsupportedSemantics=('stringification',))).reasons)
        self.assertIn('malformed-macro-replacement', self.resolve(macro('OUTER', ('fn','a'), ('fn','(','a'))).reasons)
        call, _ = invocation(arguments_values=((), ('x',)))
        self.assertIn('macro-argument-count', self.resolve(simple, call).reasons)
        call = replace(call, metadata={'macroCall': {'status':'unknown','reason':'unsupported'}})
        self.assertEqual(('unsupported',), self.resolve(simple, call).reasons)
        self.assertEqual(('missing-call-arguments',), self.resolve(simple, replace(call, metadata={})).reasons)

    def test_object_alias_zero_arguments_and_nested_parentheses(self):
        alias = event('ALIAS', 'macro_definition', 'ALIAS', 1)
        call, _ = invocation('ALIAS')
        simple = macro('OUTER', ('fn','a'), ('fn','(','a',')'))
        result = self.resolve((alias,*simple), call, extra={'ALIAS': MacroState(True,'OUTER',alias.id)})
        self.assertTrue(result.paths)
        zero, _ = invocation('ZERO', ())
        self.assertTrue(self.resolve(macro('ZERO', (), ('terminal','(',')')), zero).paths)
        values, end = arguments(tuple(Token(t,None) for t in ('(','x',')',',','y',')')), 0)
        self.assertEqual(6,end)
        self.assertEqual(2,len(values))
        self.assertEqual((), arguments((Token(')',None),),0)[0])
        self.assertEqual(2,len(arguments((Token(',',None),Token(')',None)),0)[0]))
        wrapped, attachments = invocation(arguments_values=(('(','intrinsic',')'),('x',)))
        definitions = macro('OUTER', ('fn','a'), ('fn','(','a',')'))
        result = MacroEffectIndex((*definitions,wrapped,*attachments)).resolve(wrapped,
            {'OUTER':MacroState(True,'body',stable_id('OUTER'),function_like=True)})
        self.assertTrue(any(path[-1]==stable_id('arg-0-1') for path in result.paths))
