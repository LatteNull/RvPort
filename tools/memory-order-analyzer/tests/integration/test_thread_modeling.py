"""真实三 TU compile-only P3：不链接、不运行被分析程序。"""

import json

from test_offline import collect, WORKER
from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document


def test_three_tu_two_instances_join_mutex_and_atomic_candidates(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "main.c": """
#include <pthread.h>
extern void *worker(void *);
int start(void) {
  pthread_t first, second;
  if (pthread_create(&first, 0, worker, 0) != 0) return 1;
  if (pthread_create(&second, 0, worker, 0) != 0) return 2;
  pthread_join(first, 0);
  pthread_join(second, 0);
  return 0;
}
""",
        "worker.c": """
#include <pthread.h>
#include <stdatomic.h>
pthread_mutex_t guard = PTHREAD_MUTEX_INITIALIZER;
_Atomic int shared;
void *worker(void *unused) {
  (void)unused;
  pthread_mutex_lock(&guard);
  atomic_fetch_add_explicit(&shared, 1, memory_order_release);
  pthread_mutex_unlock(&guard);
  return 0;
}
""",
        "spare.c": "int unrelated(void) { return 7; }",
    }, "clang", "c17", flags=("-pthread",))
    assert report["build_status"] == "complete" and len(artifacts) == 3
    scope = document("ScopeManifest", target_id="p3-three-tu", members=sorted(artifacts),
                     evidence="三个显式 compile-only 物理 TU", closed=True,
                     external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] == "start")
    request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"],
    )
    request_path = tmp_path / "thread-request.json"; request_path.write_text(canonical(request))
    output = tmp_path / "thread-output"
    code = cli.main(["model-threads", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    graph = json.loads(next((output / "graphs").glob("*.json")).read_text())
    assert code == result["exit_code"] in {0, 2}
    assert len([item for item in graph["instances"] if item["parent_id"] is not None]) == 2
    assert len({item["id"] for item in graph["instances"]}) == 3
    assert {item["kind"] for item in graph["lifecycles"]} >= {
        "root-start", "create-attempt", "thread-start", "thread-exit", "join-attempt"}
    assert any(item["kind"] == "mutex" for item in graph["synchronization"])
    assert any(item["kind"] == "reads-from" for item in graph["synchronization"])
    assert result["safety"] == "not_evaluated" and result["findings"] is None
    assert not list(tmp_path.glob("*.o"))
