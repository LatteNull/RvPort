"""Bounded Linux subprocesses and exclusive publication into owned output trees."""

from contextlib import contextmanager
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

from .contracts import AnalysisError

ENV_KEYS = ("PATH", "LANG", "LC_ALL", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "SDKROOT")


def _linux_process_usage(pid):
    """Return best-effort process CPU/RSS counters without a runtime dependency."""
    if os.name != "posix":
        return {"cpu_seconds": 0.0, "peak_rss_bytes": 0}
    cpu_seconds = 0.0
    peak_rss_bytes = 0
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace")
        memory = {}
        for line in status.splitlines():
            name, separator, value = line.partition(":")
            if separator and name in {"VmHWM", "VmRSS"}:
                memory[name] = int(value.strip().split()[0]) * 1024
        peak_rss_bytes = memory.get("VmHWM", memory.get("VmRSS", 0))
    except (OSError, ValueError, IndexError):
        pass
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = stat[stat.rfind(")") + 2:].split()
        ticks = os.sysconf("SC_CLK_TCK")
        cpu_seconds = (int(fields[11]) + int(fields[12])) / ticks
    except (OSError, ValueError, IndexError):
        pass
    return {"cpu_seconds": cpu_seconds, "peak_rss_bytes": peak_rss_bytes}


def environment(overrides=None):
    result = {key: os.environ[key] for key in ENV_KEYS if key in os.environ}
    result.update({"LC_ALL": "C", "LANG": "C"})
    for key, value in (overrides or {}).items():
        if key not in ENV_KEYS or not isinstance(value, str):
            raise AnalysisError("environment_invalid", f"Unsupported environment key/value: {key}")
        result[key] = value
    return result


def run(argv, cwd, *, env=None, timeout=60, log_limit=1024 * 1024):
    if not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv):
        raise AnalysisError("argv_invalid", "argv must be a nonempty string array")
    if timeout <= 0 or log_limit < 1 or not Path(cwd).is_dir():
        raise AnalysisError("budget_invalid", "Invalid working directory or execution budget")
    if os.name != "posix":
        raise AnalysisError("platform_unsupported", "Run workers in the Linux development container")
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=environment(env), shell=False,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        return {"status": "failed", "code": "start_failed", "exit_code": None,
                "stdout": "", "stderr": str(exc), "argv": argv}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    status, code = "completed", None
    deadline = time.monotonic() + timeout
    resources = {"cpu_seconds": 0.0, "peak_rss_bytes": 0}
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            observed = _linux_process_usage(process.pid)
            resources["cpu_seconds"] = max(resources["cpu_seconds"], observed["cpu_seconds"])
            resources["peak_rss_bytes"] = max(resources["peak_rss_bytes"], observed["peak_rss_bytes"])
            if time.monotonic() >= deadline:
                status, code = "timed_out", "timed_out"
                break
            for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = log_limit - sum(map(len, buffers.values()))
                buffers[key.data].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    status, code = "failed", "log_limit"
                    break
            if code:
                break
        if code:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            status, code = "timed_out", "timed_out"
    process.stdout.close()
    process.stderr.close()
    if process.returncode and not code:
        status, code = "failed", "nonzero_exit"
    return {"status": status, "code": code, "exit_code": process.returncode,
            **{key: bytes(value).decode("utf-8", errors="replace") for key, value in buffers.items()},
            **resources, "output_bytes": sum(map(len, buffers.values())), "argv": argv}


def require_success(result, stage):
    if result["status"] != "completed":
        raise AnalysisError(result["code"], f"{stage}: {result['stderr']}")
    return result["stdout"]


class OutputStore:
    """Only task-created staging directories are removed; existing destinations survive."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        if self.root == Path(self.root.anchor) or self.root == Path.home():
            raise AnalysisError("output_unsafe", "A dedicated output directory is required")
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative):
        result = (self.root / relative).resolve()
        if result == self.root or self.root not in result.parents:
            raise AnalysisError("output_unsafe", f"Path escapes output store: {relative}")
        return result

    @contextmanager
    def temporary(self):
        path = Path(tempfile.mkdtemp(prefix=".task-", dir=self.root))
        try:
            yield path
        finally:
            if path.is_symlink() or path.resolve().parent != self.root:
                raise AnalysisError("output_unsafe", "Staging path changed unexpectedly")
            shutil.rmtree(path)

    def publish(self, source, relative):
        source = Path(source).resolve()
        if self.root not in source.parents or not source.is_file():
            raise AnalysisError("output_unsafe", "Publication source must be inside this store")
        destination = self.path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Same-filesystem hard link is atomic and fails rather than replacing a user file.
        try:
            os.link(source, destination)
        except FileExistsError as exc:
            raise AnalysisError("output_exists", str(destination)) from exc
        return destination
