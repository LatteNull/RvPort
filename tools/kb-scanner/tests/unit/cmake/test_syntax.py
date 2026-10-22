import unittest
from types import SimpleNamespace as N
from unittest.mock import patch
from kb_scanner.frontends.build.cmake.syntax import parse


def node(kind,start,end,children=()):
    return N(type=kind,start_byte=start,end_byte=end,children=children,
             named_children=tuple(n for n in children if n.type not in {'(',')'}),has_error=False)


class SyntaxTests(unittest.TestCase):
    def test_native_nodes_are_lowered_with_multiline_unicode_positions(self):
        text='set(X "中\n文")'
        data=text.encode()
        arg=node('argument',6,len(data)-1,(node('quoted_argument',6,len(data)-1),))
        command=node('normal_command',0,len(data),(node('identifier',0,3),node('argument_list',4,len(data)-1,
            (node('argument',4,5),arg))))
        root=node('source_file',0,len(data),(command,))
        with patch('kb_scanner.frontends.build.cmake.syntax.Language'),patch('kb_scanner.frontends.build.cmake.syntax.Parser') as parser:
            parser.return_value.parse.return_value=N(root_node=root)
            result=parse(text)
        self.assertEqual('set',result[0].name)
        token=result[0].args[1]
        self.assertEqual(('"中\n文"',1,7,2,3,True),(token.text,token.line,token.column,token.end_line,token.end_column,token.quoted))
        self.assertEqual((),getattr(token,'children',()))

    def test_empty_parenthesized_and_budget_cases(self):
        command=node('if_command',0,8,(node('if',0,2),node('argument_list',3,7,(node('(',3,4),node('argument',4,6),node(')',6,7)))))
        root=node('source_file',0,8,(command,))
        with patch('kb_scanner.frontends.build.cmake.syntax.Language'),patch('kb_scanner.frontends.build.cmake.syntax.Parser') as parser:
            parser.return_value.parse.return_value=N(root_node=root)
            self.assertEqual(['(','ON',')'],[t.text for t in parse('if((ON))')[0].args])
            for kwargs in ({'max_nodes':1},{'max_depth':1},{'max_bytes':1},{'max_nodes':0}):
                with self.assertRaises(ValueError): parse('if((ON))',**kwargs)
            root.has_error=True
            command.has_error=True
            with self.assertRaisesRegex(ValueError,'partial-syntax'): parse('bad(')

    def test_recovered_commands_are_owned_and_not_proven(self):
        from kb_scanner.frontends.build.cmake.syntax import PartialSyntaxError
        cmd=node('normal_command',0,6,(node('identifier',0,3),))
        root=node('source_file',0,6,(cmd,))
        root.has_error=True
        with patch('kb_scanner.frontends.build.cmake.syntax.Language'),patch('kb_scanner.frontends.build.cmake.syntax.Parser') as parser:
            parser.return_value.parse.return_value=N(root_node=root)
            with self.assertRaises(PartialSyntaxError) as failure: parse('set() ')
        self.assertEqual('set',failure.exception.commands[0].name)
