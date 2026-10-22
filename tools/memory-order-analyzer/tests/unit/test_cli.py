import io
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import pytest
from memory_order_analyzer import cli
from memory_order_analyzer.contracts import AnalysisError, document
from memory_order_analyzer.publication_report import failed_publication_report
from memory_order_analyzer.validation_contracts import failed_validation_report


def test_arguments_and_module_entry(monkeypatch):
    for argv in ([], ["collect"], ["link", "--output", "/tmp/out"]):
        with pytest.raises(SystemExit):
            cli.parser().parse_args(argv)
    parsed_ingest = cli.parser().parse_args(["ingest-bc-bundle", "--output", "x", "--bundle", "bundle.json"])
    assert parsed_ingest.operation == "ingest-bc-bundle" and parsed_ingest.worker
    parsed = cli.parser().parse_args(["detect-publication-risks", "--request", "r.json",
                                      "--artifact-store", "store", "--output", "out"])
    assert parsed.operation == "detect-publication-risks" and parsed.worker
    out = io.StringIO()
    assert cli.main(["link", "--output", "/tmp/out"], stdout=out) == 1
    assert json.loads(out.getvalue())["failures"][0]["code"] == "request_invalid"
    assert cli.main(["--help"]) == 0
    monkeypatch.setattr("sys.argv", ["moa", "--help"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("memory_order_analyzer", run_name="__main__")
    assert caught.value.code == 0


def test_publication_cli_dispatch_and_failure_report(monkeypatch, tmp_path):
    expected = failed_publication_report("unit", "broken")
    monkeypatch.setattr(cli, "detect_publication_risks", lambda *args: expected)
    args = cli.parser().parse_args(["detect-publication-risks", "--request", "request.json",
                                    "--artifact-store", "store", "--output", str(tmp_path / "out")])
    report, details = cli.execute(args)
    assert report == expected and details is None
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["detect-publication-risks"], stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["kind"] == "PublicationRiskReport"
    def fail(*args):
        raise AnalysisError("unit", "classified")
    monkeypatch.setattr(cli, "detect_publication_risks", fail)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["detect-publication-risks", "--request", "r", "--artifact-store", "s",
                     "--output", str(tmp_path / "failed")], stdout=out, stderr=err)
    assert code == 1 and json.loads(out.getvalue())["verdict"] == "failed"
    assert "classified" in err.getvalue()


def test_validation_cli_dispatch_and_failure_report(monkeypatch, tmp_path):
    expected = failed_validation_report("unit", "错误", "Broken")
    monkeypatch.setattr(cli, "validate_analysis", lambda *args: expected)
    argv = ["validate-analysis", "--request", "request.json", "--artifact-store", "store",
            "--output", str(tmp_path / "out")]
    args = cli.parser().parse_args(argv)
    report, details = cli.execute(args)
    assert report == expected and details is None and args.worker
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["validate-analysis"], stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["kind"] == "AnalysisValidationReport"
    def fail(*args):
        raise AnalysisError("validation_unit", "classified")
    monkeypatch.setattr(cli, "validate_analysis", fail)
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(argv, stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["safety"] == "not_established"
    assert "classified" in err.getvalue()


def test_doctor_and_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "reader_doctor", lambda worker: {"ready": True, "failures": []})
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["doctor"], stdout=out, stderr=err) == 0
    assert json.loads(out.getvalue())["doctor"]["ready"] and not err.getvalue()
    monkeypatch.setattr(cli, "reader_doctor", lambda worker: {"ready": False, "failures": [{"code": "tool_missing"}]})
    assert cli.main(["doctor"], stdout=io.StringIO()) == 1
    assert cli.main(["collect"], stdout=io.StringIO(), stderr=err) == 1
    for failure in (AnalysisError("unit", "classified"), OSError("io"), ValueError("invalid")):
        def fail(args):
            raise failure
        monkeypatch.setattr(cli, "execute", fail)
        out = io.StringIO()
        assert cli.main(["doctor"], stdout=out, stderr=err) == 1
        assert json.loads(out.getvalue())["findings"] is None


def test_import_and_bundle_dispatch(monkeypatch, tmp_path, fixture_artifact, fixture_module):
    status = {"ready": True, "failures": [], "tools": {}}
    monkeypatch.setattr(cli, "reader_doctor", lambda worker: status)
    monkeypatch.setattr(cli, "import_bc", lambda *a, **k: (fixture_artifact, fixture_module))
    report, _ = cli.execute(cli.parser().parse_args(["import-bc", "--input", "input", "--output", str(tmp_path / "import")]))
    assert report["operation"] == "import-bc" and report["counts"]["verified"] == 1
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(fixture_artifact))
    assert cli.execute(cli.parser().parse_args(["import-bc", "--input", "input", "--manifest", str(manifest), "--output", str(tmp_path / "known")]))[0]["ir_status"] == "complete"

    expected = {"kind": "ExternalBitcodeIngestionReport", "exit_code": 2}
    monkeypatch.setattr(cli, "ingest_bundle", lambda *args, **kwargs: expected)
    args = cli.parser().parse_args(["ingest-bc-bundle", "--bundle", "bundle.json",
                                    "--output", str(tmp_path / "bundle"), "--cache", str(tmp_path / "cache")])
    assert cli.execute(args) == (expected, None)
    out = io.StringIO()
    assert cli.main(["ingest-bc-bundle"], stdout=out, stderr=io.StringIO()) == 1
    assert json.loads(out.getvalue())["kind"] == "ExternalBitcodeIngestionReport"


def test_index(monkeypatch, tmp_path, fixture_artifact, fixture_module):
    key = fixture_artifact["artifact_key"]
    inputs = tmp_path / "inputs"
    for folder, data in (("artifacts", fixture_artifact), ("facts", fixture_module)):
        (inputs / folder).mkdir(parents=True)
        (inputs / folder / f"{key}.json").write_text(json.dumps(data))
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps(document("ScopeManifest", target_id="unit", members=[key], evidence="unit", closed=True, external_boundaries=[])))
    common = ["--scope", str(scope), "--artifact-store", str(inputs)]
    index = cli.execute(cli.parser().parse_args(["index", *common, "--output", str(tmp_path / "index")]))[0]
    assert index["scope_status"] == "declared"


def test_unified_project_cli_dispatch_alias_stdout_and_failure(monkeypatch, tmp_path):
    expected = {"kind": "UnifiedMemoryOrderAnalysisReport", "status": "partial",
                "verdict": "inconclusive", "exit_code": 2}
    captured = {}
    def analyze(request, output, **options):
        captured.update(request=request, output=output, **options)
        return expected
    monkeypatch.setattr(cli, "analyze_project", analyze)
    argv = ["analyze-project", "--request", "request.json", "--output", str(tmp_path / "out"),
            "--ir-worker", "ir", "--source-worker", "source", "--artifact-store", str(tmp_path / "cache")]
    args = cli.parser().parse_args(argv)
    assert args.cache == tmp_path / "cache"
    assert cli.execute(args) == (expected, None)
    assert captured["ir_worker"] == "ir" and captured["source_worker"] == "source"
    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(argv, stdout=stdout, stderr=stderr) == 2
    assert json.loads(stdout.getvalue()) == expected and stderr.getvalue() == ""

    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(["analyze-project"], stdout=stdout, stderr=stderr) == 1
    assert json.loads(stdout.getvalue())["kind"] == "UnifiedMemoryOrderAnalysisReport"
    monkeypatch.setattr(cli, "analyze_project",
                        lambda *args, **kwargs: (_ for _ in ()).throw(AnalysisError("unit", "classified")))
    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(argv, stdout=stdout, stderr=stderr) == 1
    failed = json.loads(stdout.getvalue())
    assert failed["status"] == "failed" and failed["verdict"] == "failed"
    assert "classified" in stderr.getvalue()
