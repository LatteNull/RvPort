# Lost workers and domain-run finalization

English | [简体中文](worker-lost-domain-finalization.zh-CN.md)

## Scope and delivery status

This document describes how domain tasks converge after a worker is lost. Upgrading existing deployments still requires the draining procedure below.

## State rules

- Lost-worker cleanup changes a still-`RUNNING` Task to `FAILED` with error code `WORKER_LOST`.
- In the same transaction, it finalizes nonterminal domain-run and `tool_runs` records linked to that Task, removes temporary secrets, and persists task and node-change events. After commit, clients are notified through the existing Redis/SSE channels.
- Only `PENDING/QUEUED/RUNNING` records are updated. Existing terminal states, including success, partial success, and failure, as well as findings, artifacts, and summaries, are retained.
- Historical reconciliation maps nonterminal domain records of failed, cancelled, and timed-out Tasks to `FAILED/CANCELLED/TIMEOUT`. Autofix items have no timeout enum and use `FAILED`; their parent run and Task retain `TIMEOUT`.
- A `SUCCEEDED` Task linked to nonterminal domain records is audited only. No successful result is fabricated.
- Records are linked by actual `task_id`, not by the project's latest run. Dual-environment tasks and different source revisions do not finalize each other.
- `ENV_RUN_SCRIPT`, which has no independent domain run, represents its result through Task and `tool_runs`. Domain records without a native finish-time column can obtain it from their Task; other records store it in the native column or summary.

## Execution ownership and transactions

The current attempt is identified by `task_runtime_handles.id`. An existing partial unique index ensures at most one active handle per Task; no separate attempt table is introduced.

Claiming locks Worker first, then atomically updates Task and creates the handle. Publishing locks Task and requires both `RUNNING` state and an exact active-handle ID match. Cleanup locks Worker, Task, then handle to avoid reversing the publication lock order.

SSH, scanner processes, model calls, and object-storage uploads must not run inside transactions holding a Task lock. Validate and register artifacts after upload; expired attempts cannot update existing artifact references. Clean up newly uploaded objects after a definite rollback, and replaced objects only after commit. Preserve objects for reconciliation if the commit result is unknown.

An ordinary retry closes the old handle and sets Task to `QUEUED`; the next claim creates a new handle. Throw redelivery exceptions only after transaction commit. An old handle does not regain write access when its Task runs again.

## Scheduling and historical repair

Use the existing `rvport.worker.cleanup` settings:

- `enabled`: master switch for cleanup and historical reconciliation.
- `interval-ms`: scan interval.
- `lost-timeout-seconds`: lost-worker threshold, which must exceed the ordinary offline threshold.
- `retention-hours`: worker-record retention period.
- `batch-size`: maximum records per batch.

Historical reconciliation runs only on API/combined nodes and does not require a Worker record to still exist. It uses a stable Task UUID cursor and a separate transaction per item; one item's exception does not block subsequent items. Reset the cursor at the end of a scan and retry failures on the next pass.

Back up the database and record anomalous Task IDs before processing. Afterwards, check Task and domain state, latest results, overview, and SSE. Repeated execution must neither overwrite terminal states nor emit duplicate `task.failed` events. Logs contain only identifiers, counts, and exception types, not credentials or full business payloads.

## Deployment and rollback

1. Stop old workers from accepting tasks and drain running work. Do not mix old and new workers: old code may bypass execution-ownership protection.
2. Update API and worker images, validate with isolated fixtures, then resume consumption.
3. Drain workers before rollback as well; disable cleanup scheduling if necessary. Do not bulk-reset finalized Tasks to `RUNNING` to resume work. Create new tasks when reruns are required.

Database finalization means that the platform no longer accepts results from the attempt; it does not guarantee that a remote process has exited. Remote installations, file writes, and other side effects during a disconnect cannot be rolled back and require separate inspection. Missing findings cannot be inferred from historical states and must not be fabricated.
