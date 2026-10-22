import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from kb_scanner.core import WorkspaceSnapshot, CompletionStatus
from kb_scanner.frontends.build.frontend import BuildFrontend
from kb_scanner.frontends.build.vocabulary import BuildInputKind as K, BuildRecord
from kb_scanner.frontends.build.adapters import AdapterResult
from tests.unit.build_selection.support import context


class MakeEffectFrontendTests(unittest.TestCase):
    def analyze(self, sources, **kwargs):
        root=Path('/project')
        scan_context = context(root)
        with patch.object(Path,'stat',return_value=NS(st_size=2)), patch.object(Path,'resolve',lambda p:p), \
             patch('kb_scanner.frontends.build.make.Language'), \
             patch('kb_scanner.frontends.build.make.Parser',return_value=NS(parse=lambda _:NS(root_node=NS(has_error=False)))):
            return BuildFrontend(reader=lambda p:sources[p.relative_to(root).as_posix()],**kwargs).analyze(scan_context,WorkspaceSnapshot(root,tuple(sources)))

    def test_collected_include_provenance_uses_real_source_entity(self):
        result=self.analyze({'Makefile':'include flags.mk\nx.o: x.c\n\tcc $(FLAGS) -c $<\n','flags.mk':'FLAGS=-DX'})
        self.assertEqual(CompletionStatus.COMPLETE,result.status)
        argument=next(e for e in result.value.evidence if e.kind=='build_argument' and e.metadata.get('sourceChain'))
        self.assertEqual('flags.mk',argument.location.start.path)
        self.assertEqual('flags.mk',next(e.name for e in result.value.entities if e.id==argument.subject_id))

    def test_unsupported_origin_is_rejected_and_parse_errors_degrade(self):
        bad=BuildRecord('build_assignment','bad',1,1,4,{'sourcePath':'outside.mk'})
        with patch('kb_scanner.frontends.build.frontend.parse_make',return_value=AdapterResult((bad,))):
            with self.assertRaisesRegex(ValueError,'outside collected'):
                self.analyze({'Makefile':'A=1'})
        with patch('kb_scanner.frontends.build.frontend.parse_make',side_effect=ValueError('bad input')):
            self.assertEqual(CompletionStatus.PARTIAL,self.analyze({'Makefile':'A=1'}).status)
        self.assertEqual(CompletionStatus.PARTIAL,self.analyze({'package.spec':'big'},max_bytes=1).status)
        with patch.object(BuildFrontend,'_parse',side_effect=OSError('unreadable')):
            self.assertEqual(CompletionStatus.PARTIAL,self.analyze({'package.spec':'small'}).status)

    def test_static_adapter_routes_remain_available_without_native_parsers(self):
        for kind,name in ((K.MAKE,'parse_make'),(K.SHELL,'parse_shell'),(K.M4,'parse_m4')):
            expected=AdapterResult((),('reason',),True)
            with patch('kb_scanner.frontends.build.frontend.'+name,return_value=expected) as parser:
                result=BuildFrontend._parse('text','file',kind,'riscv64')
            self.assertEqual(expected,result)
            parser.assert_called_once()
        with patch('kb_scanner.frontends.build.frontend.analyze_project',return_value={}), \
             patch.object(BuildFrontend,'_parse',return_value=AdapterResult(())) as parser:
            self.analyze({'configure':'text'})
        parser.assert_called_once()
