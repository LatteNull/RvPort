const fs = require("node:fs");
const assert = require("node:assert/strict");
const { loadConfig } = require("../../../../../e2e/lib/env");
const { ApiClient } = require("../../../../../e2e/lib/api-client");

const config = loadConfig();
config.apiBaseUrl = process.env.AUDIT_API_BASE_URL || "http://backend-evidence-repair:8080";
const api = new ApiClient(config);
const projectId = "9915a12c-9338-419e-b589-9a3984d56c62";
const sourceRevisionId = "a019391f-89e6-4d8e-8eed-1b7871055541";
const buildRunId = "be53c759-1e2e-459a-9f73-ef8289ecfaf2";
const historicalAnalysisId = "aee4ef66-6d81-4e88-afd7-606cc7d6cc9a";
const historicalFindingId = "40546c30-01a9-4c22-be32-1329d520b222";
const base = `/api/projects/${projectId}`;

function save(name, value) {
  fs.writeFileSync(`${__dirname}/${name}.json`, `${JSON.stringify(value, null, 2)}\n`);
}

async function checked(promise) {
  const response = await promise;
  assert.notEqual(response.ok, false, JSON.stringify(response));
  return response.data;
}

function counts(items, key) {
  return items.reduce((result, item) => {
    const value = item && item[key];
    if (typeof value === "string") result[value] = (result[value] || 0) + 1;
    return result;
  }, {});
}

async function main() {
  await checked(api.login(config.adminUsername, config.adminPassword));
  await api.csrf();

  const historicalRun = await checked(
    api.get(`${base}/floating-point-analyses/${historicalAnalysisId}`)
  );
  const historicalDetail = await checked(
    api.get(`${base}/floating-point-findings/${historicalFindingId}`)
  );
  save("historical-run", historicalRun);
  save("historical-detail-before", historicalDetail);

  const created = await checked(api.post(`${base}/floating-point-analyses`));
  save("created-task", created);
  console.log(JSON.stringify({ taskId: created.id }));

  let task;
  for (let attempt = 0; attempt < 240; attempt += 1) {
    task = await checked(api.get(`/api/tasks/${created.id}`));
    if (["SUCCEEDED", "FAILED", "CANCELLED"].includes(task.status)) break;
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  save("task", task);

  const runs = await checked(api.get(`${base}/floating-point-analyses?page=1&pageSize=100`));
  const run = runs.items.find((item) => item.taskId === created.id);
  assert.ok(run, "new floating-point analysis run is missing");
  save("run", run);

  let result = null;
  let findings = { items: [] };
  if (task.status === "SUCCEEDED") {
    const raw = await api.download(
      `${base}/floating-point-analyses/${run.id}/artifacts:download?format=json`
    );
    assert.ok(raw.ok, raw.text);
    result = JSON.parse(raw.text);
    save("result", result);
    findings = await checked(
      api.get(`${base}/floating-point-analyses/${run.id}/findings?page=1&pageSize=100`)
    );
    save("findings", findings);
    for (const row of findings.items) {
      const detail = await checked(api.get(`${base}/floating-point-findings/${row.id}`));
      save(`detail-${row.id}`, detail);
    }
  }

  const historicalDetailAfter = await checked(
    api.get(`${base}/floating-point-findings/${historicalFindingId}`)
  );
  save("historical-detail-after", historicalDetailAfter);

  const analysis = result?.extensions?.["org.rvport.floating-point-scanner.analysis"];
  const artifacts = result?.extensions?.["org.rvport.floating-point-scanner.artifacts"];
  const assessments = Array.isArray(analysis?.assessments) ? analysis.assessments : [];
  const diagnostics = Array.isArray(result?.diagnostics) ? result.diagnostics : [];
  const verification = {
    projectId,
    sourceRevisionId: run.sourceRevisionId,
    buildRunId: run.buildRunId,
    historicalAnalysisId,
    analysisId: run.id,
    taskId: created.id,
    taskStatus: task.status,
    runStatus: run.status,
    exitCode: run.exitCode,
    analysisMode: run.analysisMode,
    bcStatus: run.bcStatus,
    bcPlannedCount: run.bcPlannedCount,
    bcUsableCount: run.bcUsableCount,
    bcFailedCount: run.bcFailedCount,
    bcDegradationReason: run.bcDegradationReason,
    bcAudit: run.summary?.bcAudit || null,
    artifactSetId: run.artifactSetId,
    resultStatus: result?.scan?.status,
    resultTranslationUnits: result?.project?.translationUnits,
    layerCounts: result?.summary?.layers,
    diagnosticCounts: counts(diagnostics, "code"),
    assessmentReasonCounts: counts(assessments, "reasonCode"),
    findingCount: findings.items.length,
    findings: findings.items.map((item) => ({
      id: item.id,
      externalFindingId: item.externalFindingId,
      code: item.findingCode,
      file: item.filePath,
      line: item.startLine,
      evidenceOrigin: item.detail?.conclusion?.evidenceOrigin,
    })),
    artifactSet: artifacts?.artifactSet || null,
    irAnalysis: artifacts?.irAnalysis || null,
    historicalUnchanged: JSON.stringify(historicalDetailAfter) === JSON.stringify(historicalDetail),
  };
  save("verification", verification);
  console.log(JSON.stringify(verification));

  assert.equal(task.status, "SUCCEEDED");
  assert.equal(run.sourceRevisionId, sourceRevisionId);
  assert.equal(run.buildRunId, buildRunId);
  assert.equal(result.schemaVersion, "2.0");
  assert.equal(run.bcStatus, "READY");
  assert.notEqual(run.analysisMode, "AST_ONLY");
  assert.equal(run.bcPlannedCount, 3);
  assert.equal(run.bcUsableCount, 3);
  assert.equal(run.bcFailedCount, 0);
  assert.equal(run.artifactSetId, "f9e95a698b4c5c97c60148791ce9daafbd906d7fd38f1f89550a530b65524af9");
  assert.equal(run.summary.bcAudit.translationUnits.rawCommandCount, 14);
  assert.equal(run.summary.bcAudit.translationUnits.cCppCandidateCount, 5);
  assert.equal(run.summary.bcAudit.translationUnits.projectTranslationUnitCount, 3);
  assert.equal(verification.historicalUnchanged, true);
  for (const code of [
    "long_double_abi_provenance_budget_exceeded",
    "mixed_precision_conversion_conversion_type_unknown",
    "unsupported_floating_fact",
  ]) {
    assert.equal(verification.diagnosticCounts[code] || 0, 0, code);
  }
  assert.ok(
    verification.findings.some(
      (item) => item.code === "reduction-reassociation"
        && item.file === "src/vectorcalc.cpp"
        && item.line === 62
    ),
    "expected reduction finding is missing"
  );
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await api.csrf();
    await api.logout();
  });
