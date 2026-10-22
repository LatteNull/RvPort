"""位码发布单元测试：隔离编译器子进程，核对协议、归档及失败恢复。"""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_produce_bitcode import MODULE as m


@pytest.fixture(autouse=True)
def clear_compiler_caches():
    m.COMPILER_INFO_CACHE.clear()
    m.IMPLICIT_INCLUDE_CACHE.clear()
    yield
    m.COMPILER_INFO_CACHE.clear()
    m.IMPLICIT_INCLUDE_CACHE.clear()


@pytest.mark.parametrize("entry,expected", [
    ({"arguments": ["gcc", 1, "a.c"]}, ["gcc", "1", "a.c"]),
    ({"command": 'ccache gcc "a b.c" -c'}, ["ccache", "gcc", "a b.c", "-c"]),
])
def test_command_token_inputs(entry, expected):
    assert m.command_tokens(entry) == expected


@pytest.mark.parametrize("entry,reason", [
    ({}, "COMMAND_MISSING"), ({"arguments": [], "command": " "}, "COMMAND_MISSING"),
    ({"command": "gcc\na.c"}, "UNSAFE_COMMAND"),
    ({"command": "gcc `echo a`"}, "UNSAFE_COMMAND"),
    ({"command": "gcc $(echo a)"}, "UNSAFE_COMMAND"),
    ({"arguments": ["gcc", "a.c", "&&", "other"]}, "UNSAFE_COMMAND"),
])
def test_unsafe_and_missing_commands(entry, reason):
    with pytest.raises(ValueError, match=reason):
        m.command_tokens(entry)


def test_response_limits_absolute_paths_and_wrappers(tmp_path):
    response = tmp_path / "args.rsp"
    response.write_text("@args.rsp")
    with pytest.raises(ValueError, match="RESPONSE_FILE_DEPTH_EXCEEDED"):
        m.expand_response_files(["@args.rsp"], tmp_path, tmp_path, {})
    response.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="RESPONSE_FILE_SIZE_EXCEEDED"):
        m.expand_response_files(["@" + str(response)], tmp_path, tmp_path, {})
    response.write_text("-DVALUE=1")
    inputs = {}
    assert m.expand_response_files(["@", "-I", "inc", "@" + str(response)], tmp_path, tmp_path, inputs) == ["@", "-I", "inc", "-DVALUE=1"]
    assert inputs == {"args.rsp": hashlib.sha256(response.read_bytes()).hexdigest()}
    assert m.compiler_index(["ccache", "sccache", "/usr/bin/g++", "a.cc"]) == 2
    for tokens in ([], ["ccache"], ["vendorcc"]):
        with pytest.raises(ValueError, match="UNSUPPORTED_COMPILER"):
            m.compiler_index(tokens)


def test_compiler_probe_and_cached_metadata(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="clang version 21\nmore details\n")
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.probe("clang", "--version").endswith("more details")
    assert m.compiler_info("/bin/clang")["family"] == "clang"
    assert m.compiler_info("/bin/clang")["version"] == "clang version 21"
    assert len(calls) == 2
    monkeypatch.setattr(m, "probe", lambda *args: "")
    assert m.compiler_info("gcc") == {"family": "gcc", "executable": "gcc", "version": "unknown"}


@pytest.mark.parametrize("error", [OSError("missing"), subprocess.TimeoutExpired("cc", 30)])
def test_probe_and_implicit_include_failure(monkeypatch, tmp_path, error):
    def run(*args, **kwargs):
        raise error
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.probe("cc") == "unknown"
    assert m.implicit_includes("cc", "c", tmp_path) == []
    assert m.implicit_includes("cc", "c", tmp_path) == []


def test_implicit_include_cache_and_language(monkeypatch, tmp_path):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stderr=f"#include <...> search starts here:\n\nrelative\n{tmp_path}\nEnd of search list.\nignored")
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.implicit_includes("g++", "c++", tmp_path) == ["-isystem", str(tmp_path)]
    assert m.implicit_includes("g++", "c++", tmp_path) == ["-isystem", str(tmp_path)]
    assert calls == [["g++", "-E", "-x", "c++", "-", "-v"]]


def test_normalization_preserves_context_and_selects_cxx(monkeypatch, tmp_path):
    source = tmp_path / "a.cc"
    source.write_text("int main() {}")
    monkeypatch.setattr(m, "implicit_includes", lambda *args: ["-isystem", "/tool/include"])
    monkeypatch.setattr(m, "compiler_info", lambda *args: {"family": "gcc"})
    entry = {"directory": ".", "file": "a.cc", "arguments": ["ccache", "g++", "-c", "a.cc", "-o", "a.o", "-MF", "a.d", "-Wp,-MD,a.d", "-I" + str(tmp_path), "-std=c++20", "extra.a"]}
    command, directory, actual, language, stable, inputs, info = m.normalized_entry(entry, tmp_path, tmp_path / "a.bc", "clang", "clang++")
    assert command[0] == "clang++" and language == "c++"
    assert directory == tmp_path and actual == source
    assert stable["arguments"] == ["-I<SOURCE_ROOT>", "-std=c++20", "extra.a"]
    assert "-isystem" in command and command[-2:] == ["-o", str(tmp_path / "a.bc")]
    assert inputs == {"a.cc": m.file_digest(source)} and info == {"family": "gcc"}
    with pytest.raises(ValueError, match="UNSUPPORTED_LANGUAGE"):
        m.normalized_entry({"file": "a.rs"}, tmp_path, tmp_path / "a.bc", "clang", "clang++")
    with pytest.raises(ValueError, match="PATH_OUTSIDE_SOURCE_ROOT"):
        m.normalized_entry({"directory": "../", "file": "a.c"}, tmp_path, tmp_path / "a.bc", "clang", "clang++")


@pytest.mark.parametrize("returncode,stdout,stderr,error", [
    (1, "", "invalid module", "LLVM_VERIFY_FAILED"),
    (0, 'target triple = "x86_64-linux"', "", "LLVM_TARGET_METADATA_MISSING"),
    (0, 'target datalayout = "e-p:64:64"', "", "LLVM_TARGET_METADATA_MISSING"),
])
def test_ir_metadata_failures(monkeypatch, tmp_path, returncode, stdout, stderr, error):
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr))
    with pytest.raises(ValueError, match=error):
        m.parse_ir_metadata("llvm-dis", tmp_path / "a.bc", 1)


def test_metadata_abi_and_diagnostic(monkeypatch, tmp_path):
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='target triple = "x86_64-linux"\ntarget datalayout = "e-p:64:64"', stderr=""))
    assert m.parse_ir_metadata("llvm-dis", tmp_path / "a.bc", 1) == ("x86_64-linux", "e-p:64:64")
    assert m.abi_for("x86_64-linux", "e-p:64:64") == {"architecture": "x86_64", "pointer_width": 64, "endianness": "little"}
    assert m.abi_for("arm-linux", "E")["pointer_width"] is None
    assert m.abi_for("arm-linux", "E")["endianness"] == "big"
    assert m.sanitize("\r\n" + str(tmp_path) + "/a.c\n\n", tmp_path) == "<SOURCE_ROOT>/a.c"
    assert len(m.sanitize("x" * 2000, tmp_path)) == 1600
    assert m.sanitize(None, tmp_path) == ""
    assert m.diagnostic("X", "说明")["detail_en"] == "说明"
    assert m.language_standard(["-std=c++20"], "c")["standard"] == "unsupported"
    assert m.language_standard(["-std=c11"], "c++")["standard"] == "unsupported"


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    for name in ("a.c", "b.c", "c.cc"):
        (root / name).write_text("int main() { return 0; }")
    output = tmp_path / "output"
    args = argparse.Namespace(compile_db=str(root / "compile_commands.json"), source_root=str(root), output_dir=str(output), clang="clang", clangxx="clang++", llvm_dis="llvm-dis", manifest=str(tmp_path / "manifest.json"), bundle=str(tmp_path / "bundle.tar.gz"), toolchain_id="llvm-21", toolchain_version="21.1.8", max_tu=10, max_tu_bytes=1024, max_total_bytes=2048, tu_timeout=1, total_timeout=10)
    monkeypatch.setattr(m, "parse_args", lambda: args)
    monkeypatch.setattr(m, "probe", lambda *unused: "x86_64-linux")
    monkeypatch.setattr(m, "implicit_includes", lambda *unused: [])
    monkeypatch.setattr(m, "compiler_info", lambda *unused: {"family": "gcc", "executable": "gcc", "version": "13"})
    calls = []
    outcomes = {}
    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "llvm-dis":
            return SimpleNamespace(returncode=0, stdout='target triple = "x86_64-linux"\ntarget datalayout = "e-p:64:64"', stderr="")
        source = Path(command[-3]).name
        outcome = outcomes.get(source, "success")
        if isinstance(outcome, Exception):
            raise outcome
        if outcome != "missing":
            Path(command[-1]).write_bytes(b"BC\xc0\xde" if outcome != "tiny" else b"B")
        return SimpleNamespace(returncode=1 if outcome == "failed" else 0, stderr=str(root) + "/compiler diagnostic")
    monkeypatch.setattr(m.subprocess, "run", run)
    def execute(entries):
        Path(args.compile_db).write_text(json.dumps(entries))
        assert m.main() == 0
        return json.loads(Path(args.manifest).read_text())
    def entry(name="a.c", *flags):
        return {"directory": str(root), "file": name, "arguments": ["gcc", *flags, "-c", name]}
    return SimpleNamespace(root=root, args=args, output=output, calls=calls, outcomes=outcomes, execute=execute, entry=entry)


def test_publication_success_deduplicates_and_writes_valid_bundle(pipeline):
    p = pipeline
    manifest = p.execute([p.entry(), p.entry(), p.entry("c.cc", "-std=c++20"), None, {"file": "ignored.txt"}])
    assert manifest["status"] == "READY"
    assert manifest["counts"] == {"planned_contexts": 2, "planned_records": 2, "produced": 2, "missing": 0, "failed": 0, "total_bytes": 8}
    assert len(p.calls) == 4
    assert {record["language"] for record in manifest["records"]} == {"c", "c++"}
    assert manifest["scopes"][0]["closed"] is False
    assert manifest["semantic_digest"] == m.digest(manifest, "semantic_digest", "generated_at", "artifact_set_id", "raw_compile_commands_sha256")
    with tarfile.open(p.args.bundle) as bundle:
        assert json.load(bundle.extractfile("manifest.json")) == manifest
        for record in manifest["records"]:
            data = bundle.extractfile(record["bitcode"]["path"]).read()
            assert hashlib.sha256(data).hexdigest() == record["bitcode"]["sha256"]
            info = bundle.getmember(record["bitcode"]["path"])
            assert info.mode == 0o600 and info.mtime == 0 and info.uid == 0
        assert len(bundle.getnames()) == 6


@pytest.mark.parametrize("outcome,code", [
    ("failed", "TRANSLATION_UNIT_FAILED"), ("missing", "TRANSLATION_UNIT_FAILED"),
    ("tiny", "TRANSLATION_UNIT_FAILED"),
    (subprocess.TimeoutExpired("clang", 1), "TRANSLATION_UNIT_TIMEOUT"),
    (RuntimeError(""), "TRANSLATION_UNIT_FAILED"),
])
def test_partial_publication_isolates_compilation_failures(pipeline, outcome, code):
    p = pipeline
    p.outcomes["b.c"] = outcome
    manifest = p.execute([p.entry(), p.entry("b.c")])
    assert manifest["status"] == "PARTIAL"
    assert manifest["counts"]["produced"] == 1 and manifest["counts"]["failed"] == 1
    failed = next(record for record in manifest["records"] if record["status"] == "failed")
    assert failed["bitcode"] is None and failed["diagnostic"]["code"] == code
    assert str(p.root) not in failed["diagnostic"]["detail"]
    assert len(list((p.output / "bitcode").glob("*.bc"))) == 1


@pytest.mark.parametrize("setting,value,code", [
    ("max_tu", 0, "TRANSLATION_UNIT_LIMIT_EXCEEDED"),
    ("max_tu_bytes", 3, "OUTPUT_SIZE_LIMIT_EXCEEDED"),
    ("max_total_bytes", 3, "OUTPUT_SIZE_LIMIT_EXCEEDED"),
    ("total_timeout", -1, "TOTAL_TIMEOUT"),
])
def test_limits_publish_failure_without_leaving_bitcode(pipeline, setting, value, code):
    p = pipeline
    setattr(p.args, setting, value)
    manifest = p.execute([p.entry()])
    assert manifest["status"] == "FAILED"
    assert manifest["records"][0]["diagnostic"]["code"] == code
    assert manifest["counts"]["total_bytes"] == 0
    assert list((p.output / "bitcode").glob("*.bc")) == []


def test_total_size_limit_and_unsupported_standard(pipeline):
    p = pipeline
    p.args.max_total_bytes = 4
    manifest = p.execute([p.entry(), p.entry("b.c"), p.entry("c.cc", "-std=vendor-cpp")])
    assert manifest["counts"]["produced"] == 1 and manifest["counts"]["total_bytes"] == 4
    assert {r["diagnostic"]["code"] for r in manifest["records"] if r["diagnostic"]} == {"OUTPUT_SIZE_LIMIT_EXCEEDED", "UNSUPPORTED_LANGUAGE_STANDARD"}


def test_empty_and_invalid_database(pipeline):
    assert pipeline.execute([])["status"] == "FAILED"
    Path(pipeline.args.compile_db).write_text("{}")
    with pytest.raises(ValueError, match="COMPILE_DATABASE_NOT_ARRAY"):
        m.main()


def test_fallback_failure_identity_is_unique(pipeline):
    entry = pipeline.entry()
    entry["arguments"] = ["unsupported-compiler"]
    manifest = pipeline.execute([entry, entry])
    assert manifest["counts"]["failed"] == 1
    assert manifest["records"][0]["diagnostic"]["code"] == "UNSUPPORTED_COMPILER"


def test_cli_required_arguments_and_types(monkeypatch):
    values = {name: "example" for name in ("compile-db", "source-root", "output-dir", "clang", "clangxx", "llvm-dis", "manifest", "bundle", "toolchain-id", "toolchain-version")}
    values.update({name: "10" for name in ("max-tu", "max-tu-bytes", "max-total-bytes", "tu-timeout", "total-timeout")})
    argv = ["produce_bitcode.py"] + [value for key, item in values.items() for value in ("--" + key, item)]
    monkeypatch.setattr("sys.argv", argv)
    assert m.parse_args().max_tu == 10
    monkeypatch.setattr("sys.argv", ["produce_bitcode.py"])
    with pytest.raises(SystemExit) as exc:
        m.parse_args()
    assert exc.value.code == 2
