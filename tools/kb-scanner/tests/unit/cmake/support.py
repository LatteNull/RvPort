from kb_scanner.frontends.build.cmake.syntax import Command, Token


def command(name, *args, line=1):
    tokens = tuple(Token(a, line, i*20+len(name)+2, line, i*20+len(name)+len(a)+2, a.startswith(('"','['))) for i,a in enumerate(args))
    text = name+'('+ ' '.join(args)+')'
    return Command(name, tokens, Token(text, line, 1, line, len(text)+1))


def project(*commands, extra=None, **kwargs):
    from kb_scanner.frontends.build.cmake.project import analyze_project
    sources = {'CMakeLists.txt': 'root', **{p:p for p in extra or {}}}
    def parser(source):
        return commands if source == 'root' else extra[source]
    return analyze_project(sources, 'riscv64', parser=parser, **kwargs)


def selected(result, kind):
    return [(r.value, r.metadata['selectionStatus']) for part in result.values() for r in part.records if r.kind == kind]
