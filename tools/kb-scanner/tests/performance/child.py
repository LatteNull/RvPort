"""Scanner subprocess entry; production code receives unchanged snapshots."""
import argparse
import faulthandler
import json
import resource
import signal
from dataclasses import replace
from pathlib import Path

from kb_scanner.adapters.cli import StagedContextFactory
from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_profile
from kb_scanner.pipeline.orchestrator import StagedPipelineRunner
from tests.performance.observation import observe


class ProfiledAnalyzer:
    def __init__(self, delegate, output):
        self.delegate, self.output = delegate, output

    def analyze(self, *args):
        import cProfile
        profiler = cProfile.Profile()
        def expire(*_):
            raise SystemExit(124)
        previous = signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, 120)
        profiler.enable()
        try:
            return self.delegate.analyze(*args)
        finally:
            profiler.disable()
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            profiler.dump_stats(str(self.output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    request = ScanRequest(args.source, "rulesets/riscv-porting", args.output)
    context = StagedContextFactory().build(request)
    emit = lambda event: print(json.dumps(event, sort_keys=True), flush=True)
    profile = observe(create_default_profile(), emit)
    runner = StagedPipelineRunner(profile)
    if args.profile:
        profile = replace(profile, analyzer=ProfiledAnalyzer(profile.analyzer, Path(args.output).parent / "profile.pstats"))
        runner = StagedPipelineRunner(profile)
    result = runner.run(context.value, context.diagnostics)
    emit({"event": "resource", "maxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "exitCode": result.exit_code})
    faulthandler.cancel_dump_traceback_later()
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
