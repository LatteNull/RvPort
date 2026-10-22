import io
import json

from memory_order_analyzer import cli
from memory_order_analyzer.analyze_degraded_source import failed_degraded_report
from memory_order_analyzer.contracts import AnalysisError


def test_degraded_cli_dispatch_workers_and_failure_precedence(monkeypatch, tmp_path):
    expected = failed_degraded_report("unit", "测试", "Test")
    captured = {}
    def run(*args):
        captured["args"] = args
        return expected
    monkeypatch.setattr(cli, "analyze_degraded_source", run)
    argv = ["analyze-degraded-source", "--request", "request.json", "--artifact-store", "store",
            "--output", str(tmp_path / "out"), "--source-worker", "source", "--ir-worker", "ir"]
    args = cli.parser().parse_args(argv)
    report, details = cli.execute(args)
    assert report == expected and details is None
    assert captured["args"][-2:] == ("source", "ir")

    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["analyze-degraded-source"], stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["kind"] == "DegradedSourceAnalysisReport"

    def fail(*args):
        raise AnalysisError("invalid_reference", "changed dependency")
    monkeypatch.setattr(cli, "analyze_degraded_source", fail)
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(argv, stdout=out, stderr=err) == 1
    result = json.loads(out.getvalue())
    assert result["status"] == "failed" and result["safety"] == "not-established"
    assert "changed dependency" in err.getvalue()
