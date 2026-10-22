from __future__ import annotations

import re

from pydantic import BaseModel

from .models import SchemaV2Report


_EXTENSION = re.compile(r"^org\.rvport\.kb-scanner\.[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_CODE_KINDS = {"build_selector", "target_selection", "source_selection", "source_evidence", "macro_invocation", "macro_definition", "macro_replacement", "intrinsic_call", "vector_type", "compiler_flag", "test_asset"}


class V2ValidationError(ValueError):
    def __init__(self, rule: str, reason: str) -> None:
        self.rule = rule
        self.reason = reason
        super().__init__(f"{rule}: {reason}")


class V2ReferentialIntegrityValidator:
    def validate(self, report: SchemaV2Report) -> None:
        self._unique((item.id for item in report.findings), "result.finding-id-unique")
        if tuple(report.findings) != tuple(sorted(report.findings, key=lambda item: item.id)):
            self._fail("result.stable-order", "findings")
        for finding in report.findings:
            occurrence_ids = self._unique((item.id for item in finding.occurrences), "finding.occurrence-id-unique")
            if finding.primaryOccurrenceId not in occurrence_ids:
                self._fail("finding.primary-occurrence-resolves", finding.primaryOccurrenceId)
            expected_occurrences = sorted(finding.occurrences, key=lambda item: (item.location.file, item.location.span.start.line, item.location.span.start.column, item.id))
            if list(finding.occurrences) != expected_occurrences:
                self._fail("result.stable-order", "occurrences")
            self._chain(finding.evidenceChain)
            self._source(finding.fact.primaryLocation)
            for occurrence in finding.occurrences:
                self._source(occurrence.location)
        expected_diagnostics = sorted(report.diagnostics, key=lambda item: (item.severity, item.code, item.stage, item.id))
        if list(report.diagnostics) != expected_diagnostics:
            self._fail("result.stable-order", "diagnostics")
        self._extensions(report)

    def _extensions(self, value, seen=None) -> None:
        # 仅本次遍历共享对象；不同报告/再次校验必须重新检查可变扩展内容。
        if seen is None:
            seen = set()
        if isinstance(value, (BaseModel, tuple, list)):
            if id(value) in seen:
                return
            seen.add(id(value))
        if isinstance(value, BaseModel):
            fields = type(value).model_fields
            extensions = (value.extensions or {}) if "extensions" in fields else {}
            if any(not _EXTENSION.fullmatch(key) for key in extensions):
                self._fail("result.extension-namespace", "invalid extension key")
            for name in fields:
                self._extensions(getattr(value, name), seen)
        elif isinstance(value, (tuple, list)):
            for item in value:
                self._extensions(item, seen)

    def _chain(self, chain) -> None:
        step_ids = self._unique((item.id for item in chain.steps), "chain.step-id-unique")
        if chain.rootStepId not in step_ids:
            self._fail("chain.root-step-resolves", chain.rootStepId)
        if len(chain.primaryPath) != len(set(chain.primaryPath)) or any(item not in step_ids for item in chain.primaryPath):
            self._fail("chain.primary-path-resolves", "unresolved or duplicate step")
        pairs = set()
        for edge in chain.edges:
            if edge.fromStepId not in step_ids or edge.toStepId not in step_ids:
                self._fail("chain.edge-endpoints-resolve", edge.id)
            pairs.add((edge.fromStepId, edge.toStepId))
        if any(pair not in pairs for pair in zip(chain.primaryPath, chain.primaryPath[1:])):
            self._fail("chain.primary-path-connected", "missing connecting edge")
        by_id = {item.id: item for item in chain.steps}
        if not chain.primaryPath or chain.rootStepId != chain.primaryPath[0]:
            self._fail("chain.primary-path-resolves", "root must start the primary path")
        if any(item not in by_id or by_id[item].kind not in {"classification", "assessment"} for item in chain.impactStepIds):
            self._fail("chain.impact-step-resolves", "invalid impact step")
        for item in chain.breaks:
            if item.fromStepId and item.fromStepId not in step_ids:
                self._fail("chain.break-references-resolve", item.id)
            if any(candidate not in step_ids for candidate in item.candidateStepIds):
                self._fail("chain.break-references-resolve", item.id)
        if chain.status == "complete" and (chain.breaks or chain.reasonCodes):
            self._fail("chain.complete-has-no-break", "complete chain contains a break/reason")
        if chain.status == "complete" and (
            any(by_id[sid].status != "complete" for sid in chain.primaryPath)
            or any(not any(e.fromStepId == a and e.toStepId == b and e.status == "complete" for e in chain.edges)
                   for a, b in zip(chain.primaryPath, chain.primaryPath[1:]))
        ):
            self._fail("chain.complete-has-no-break", "primary path contains incomplete evidence")
        if chain.status in {"partial", "ambiguous", "unknown"} and not chain.breaks:
            self._fail("chain.incomplete-has-break", "incomplete chain has no break")
        if list(chain.steps) != sorted(chain.steps, key=lambda item: item.id) or list(chain.edges) != sorted(chain.edges, key=lambda item: item.id) or list(chain.breaks) != sorted(chain.breaks, key=lambda item: item.id):
            self._fail("result.stable-order", "chain collections")
        for step in chain.steps:
            if step.kind in _CODE_KINDS and step.source is None:
                self._fail("step.code-kind-has-source", step.id)
            if step.kind not in _CODE_KINDS and step.source is not None:
                self._fail("step.non-code-kind-has-no-source", step.id)
            if step.kind == "knowledge_match" and step.knowledge is None:
                self._fail("step.knowledge-projection-complete", step.id)
            if step.source is not None:
                self._source(step.source)

    def _source(self, source) -> None:
        if source.file.startswith(("/", "\\")) or "\\" in source.file or ".." in source.file.split("/"):
            self._fail("source.path-project-relative", source.file)
        lines = [item.line for item in source.context.lines]
        if lines != sorted(set(lines)):
            self._fail("source.context-lines-ordered", source.file)
        by_line = {item.line: item.text for item in source.context.lines}
        budget = source.context.budget
        if len(lines) > budget.maxLines or sum(len(text) for text in by_line.values()) > budget.maxCharacters:
            self._fail("source.context-budget", source.file)
        for item in source.context.highlights:
            text = by_line.get(item.line)
            if text is None or item.endColumn <= item.startColumn or item.endColumn > len(text) + 1:
                self._fail("source.highlight-resolves", source.file)
        if source.context.status == "complete" and (not lines or not source.context.highlights):
            self._fail("source.complete-context-has-highlight", source.file)

    @staticmethod
    def _unique(values, rule: str) -> set[str]:
        material = list(values)
        if len(material) != len(set(material)):
            raise V2ValidationError(rule, "duplicate id")
        return set(material)

    @staticmethod
    def _fail(rule: str, reason: str) -> None:
        raise V2ValidationError(rule, reason)
