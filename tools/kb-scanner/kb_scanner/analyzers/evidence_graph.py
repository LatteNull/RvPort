from __future__ import annotations
from bisect import bisect_left, bisect_right
from .span_lookup import SpanLookup

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Callable

from ..core import (
    AnalysisSnapshot,
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    Relation,
    ScanContext,
    SourceSpan,
    StageResult,
    stable_id,
)
from ..graph import GraphStore, NetworkXGraphStore
from .macro_resolution import MacroDefinitionResolver
from .proof import ProofBudgets, ProofPathResolver
from .relation_diagnostics import relation_diagnostic
from .architecture_guards import foreign_guard_proof, required_foreign


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ROLE_PATTERNS = {
    "riscv": re.compile(r"(?i)(?<![A-Za-z0-9])riscv(?:32|64)?(?![A-Za-z0-9])"),
    "generic": re.compile(r"(?i)(?<![A-Za-z0-9])(generic|default)(?![A-Za-z0-9])"),
    "portable": re.compile(r"(?i)(?<![A-Za-z0-9])portable(?![A-Za-z0-9])"),
    "scalar": re.compile(r"(?i)(?<![A-Za-z0-9])scalar(?![A-Za-z0-9])"),
}


@dataclass(frozen=True, slots=True)
class BranchRecord:
    group: Entity
    branch: Entity
    implementation: Entity
    evidence: Evidence
    role: str
    knowledge_ids: tuple[str, ...]


@dataclass(slots=True)
class GraphIndex:
    entities: dict[str, Entity]
    project: Entity
    files_by_id: dict[str, Entity]
    files_by_path: dict[str, Entity]
    implementations_by_file: dict[str, Entity]
    evidence_entities: dict[str, tuple[Entity, ...]]
    definitions_by_name: dict[str, tuple[Entity, ...]]
    definition_by_evidence: dict[str, Entity]
    definition_file: dict[str, str]
    invocation_entities: tuple[Entity, ...]
    symbol_entities: tuple[Entity, ...]
    branches: tuple[BranchRecord, ...]


class GraphEntityIndexer:
    __slots__ = ()

    def index(
        self,
        context: ScanContext,
        snapshot: NormalizedSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> GraphIndex:
        entities = {item.id: item for item in snapshot.entities}
        files_by_id = {item.id: item for item in snapshot.entities if item.kind == "source_file"}
        files_by_path = {item.name: item for item in files_by_id.values()}
        project = Entity(
            stable_id("graph_entity", 1, "project", tuple(sorted(files_by_path)), context.rule_pack_id),
            "project",
            ".",
            properties={"identityVersion": 1, "rulePackId": context.rule_pack_id},
        )
        entities[project.id] = project
        implementations_by_file: dict[str, Entity] = {}
        for file_entity in files_by_id.values():
            implementation = Entity(
                stable_id("graph_entity", 1, "implementation", file_entity.name),
                "implementation",
                file_entity.name,
                properties={"identityVersion": 1, "sourceFileId": file_entity.id, "role": "unknown"},
            )
            entities[implementation.id] = implementation
            implementations_by_file[file_entity.id] = implementation

        evidence_entities: dict[str, list[Entity]] = defaultdict(list)
        definitions_by_name: dict[str, list[Entity]] = defaultdict(list)
        definition_by_evidence: dict[str, Entity] = {}
        definition_file: dict[str, str] = {}
        symbol_by_name: dict[str, Entity] = {}
        invocation_entities: list[Entity] = []

        for evidence in sorted(snapshot.evidence, key=lambda item: item.id):
            if evidence.subject_id not in files_by_id:
                raise ValueError("Evidence references an unknown source file Entity")
            if not isinstance(evidence.value, str):
                continue
            kind = {
                "macro_definition": "macro_definition",
                "macro_expansion": "macro_invocation",
                "call_expression": "call_site",
                "include": "include_site",
                "enum_declaration": "enum_type",
                "enum_member_declaration": "enum_member",
                "enum_member_reference": "enum_member_reference",
                "constexpr_condition": "selection_predicate",
                "selection_condition": "selection_predicate",
                "inline_asm": "asm_site",
                "declaration_attribute": "attribute_site",
            }.get(evidence.kind)
            if kind is None:
                continue
            entity = _entity_from_evidence(kind, evidence.value, evidence)
            entities[entity.id] = entity
            evidence_entities[evidence.id].append(entity)
            if kind == "macro_definition":
                definitions_by_name[evidence.value].append(entity)
                definition_by_evidence[evidence.id] = entity
                definition_file[entity.id] = evidence.subject_id
            elif kind == "macro_invocation":
                invocation_entities.append(entity)
            elif kind == "call_site":
                symbol = symbol_by_name.setdefault(evidence.value, _symbol_entity(evidence.value))
                entities[symbol.id] = symbol
                evidence_entities[evidence.id].append(symbol)

        for evidence in sorted(snapshot.evidence, key=lambda item: item.id):
            if evidence.kind != "call_expression" or not isinstance(evidence.value, str):
                continue
            if evidence.value in definitions_by_name:
                invocation = _entity_from_evidence("macro_invocation", evidence.value, evidence)
                entities[invocation.id] = invocation
                evidence_entities[evidence.id].append(invocation)
                invocation_entities.append(invocation)

        branches = _index_branches(snapshot.evidence, entities, evidence_entities, knowledge)
        return GraphIndex(
            entities=entities,
            project=project,
            files_by_id=files_by_id,
            files_by_path=files_by_path,
            implementations_by_file=implementations_by_file,
            evidence_entities={key: tuple(sorted(value, key=lambda item: item.id)) for key, value in evidence_entities.items()},
            definitions_by_name={key: tuple(sorted(value, key=lambda item: item.id)) for key, value in definitions_by_name.items()},
            definition_by_evidence=definition_by_evidence,
            definition_file=definition_file,
            invocation_entities=tuple(sorted({item.id: item for item in invocation_entities}.values(), key=lambda item: item.id)),
            symbol_entities=tuple(sorted(symbol_by_name.values(), key=lambda item: item.id)),
            branches=branches,
        )


class IncludeResolver:
    __slots__ = ("_index",)

    def __init__(self, index: GraphIndex) -> None:
        self._index = index

    def resolve(self, including_file: Entity, include_value: str) -> tuple[tuple[Entity, ...], str, str | None]:
        normalized = include_value.replace("\\", "/").strip('<>"')
        include_path = PurePosixPath(normalized)
        if include_path.is_absolute() or ".." in include_path.parts:
            return (self._external(normalized, "unsafe"),), "unknown", "unsafe-include-path"
        parent_candidate = (PurePosixPath(including_file.name).parent / include_path).as_posix()
        direct = self._index.files_by_path.get(parent_candidate) or self._index.files_by_path.get(include_path.as_posix())
        if direct is not None:
            return (direct,), "complete", None
        suffix = f"/{include_path.as_posix()}"
        candidates = tuple(
            sorted(
                (item for path, item in self._index.files_by_path.items() if path == include_path.as_posix() or path.endswith(suffix)),
                key=lambda item: item.id,
            )
        )
        if len(candidates) == 1:
            return candidates, "complete", None
        if candidates:
            scored = tuple((self._common_prefix(including_file.name, item.name), item) for item in candidates)
            best = max(score for score, _ in scored)
            nearest = tuple(item for score, item in scored if score == best)
            if best > 0 and len(nearest) == 1:
                return nearest, "complete", None
            return candidates, "partial", "ambiguous-include"
        return (self._external(normalized, "external"),), "unknown", "unresolved-include"

    @staticmethod
    def _common_prefix(including: str, candidate: str) -> int:
        left = PurePosixPath(including).parent.parts
        right = PurePosixPath(candidate).parent.parts
        score = 0
        for first, second in zip(left, right):
            if first != second:
                break
            score += 1
        return score

    def _external(self, name: str, resolution: str) -> Entity:
        entity = Entity(
            stable_id("graph_entity", 1, "external_header", name, resolution),
            "external_header",
            name,
            properties={"identityVersion": 1, "resolution": resolution},
        )
        self._index.entities[entity.id] = entity
        return entity


class RelationBuilder:
    __slots__ = ("_context", "_snapshot", "_knowledge", "_index", "_relations", "_diagnostics",
                 "_evidence_by_id", "_first_evidence", "_relation_buckets", "_branches_by_path",
                 "_knowledge_patterns", "_evidence_by_subject", "_predicate_evidence", "_enum_conditions", "_enum_dependencies", "_enum_dependency_lines")

    def __init__(
        self,
        context: ScanContext,
        snapshot: NormalizedSnapshot,
        knowledge: KnowledgeSnapshot,
        index: GraphIndex,
    ) -> None:
        self._context = context
        self._snapshot = snapshot
        self._knowledge = knowledge
        self._index = index
        self._relations: dict[str, Relation] = {}
        self._diagnostics: list[Diagnostic] = []
        self._evidence_by_id = {item.id: item for item in snapshot.evidence}
        self._first_evidence = {}
        for item in snapshot.evidence:
            self._first_evidence.setdefault(item.id, item)
        self._relation_buckets: dict[tuple, list[str]] = defaultdict(list)
        self._knowledge_patterns = {}
        self._evidence_by_subject: dict[str, list[Evidence]] = defaultdict(list)
        for item in snapshot.evidence:
            self._evidence_by_subject[item.subject_id].append(item)
        self._predicate_evidence: dict[str, list[tuple[Entity, Evidence]]] = defaultdict(list)
        self._enum_conditions = SpanLookup(item for item in snapshot.evidence
            if item.kind in {"constexpr_condition", "selection_condition"})
        self._enum_dependencies = defaultdict(list)
        for item in snapshot.evidence:
            if item.location is not None and item.kind in {"call_expression", "type_reference", "include", "inline_asm", "declaration_attribute"}:
                self._enum_dependencies[item.subject_id].append(item)
        self._enum_dependency_lines = {}
        for subject, items in self._enum_dependencies.items():
            items.sort(key=lambda item: item.location.start.line)
            self._enum_dependency_lines[subject] = [item.location.start.line for item in items]
        for item in snapshot.evidence:
            for entity in index.evidence_entities.get(item.id, ()):
                if entity.kind == "selection_predicate":
                    self._predicate_evidence[entity.id].append((entity, item))
        self._branches_by_path: dict[str, list[BranchRecord]] = defaultdict(list)
        for record in index.branches:
            if record.evidence.location is not None:
                self._branches_by_path[record.evidence.location.start.path].append(record)

    def build(self) -> tuple[tuple[Relation, ...], tuple[Diagnostic, ...]]:
        self._define_files_and_implementations()
        include_targets = self._includes()
        self._calls_and_macro_invocations(include_targets)
        self._macro_replacements()
        self._branch_relations()
        self._enum_relations()
        return tuple(sorted(self._relations.values(), key=_relation_key)), tuple(self._diagnostics)

    def _define_files_and_implementations(self) -> None:
        for file_id, implementation in self._index.implementations_by_file.items():
            self._add("defines", file_id, implementation.id, (), "complete")
        for evidence_id, definition in self._index.definition_by_evidence.items():
            self._add("defines", self._index.definition_file[definition.id], definition.id, (evidence_id,), "complete")

    def _includes(self) -> dict[str, set[str]]:
        resolver = IncludeResolver(self._index)
        targets: dict[str, set[str]] = defaultdict(set)
        for evidence in self._snapshot.evidence:
            if evidence.kind != "include" or not isinstance(evidence.value, str):
                continue
            including = self._index.files_by_id[evidence.subject_id]
            resolved, status, reason = resolver.resolve(including, evidence.value)
            for target in resolved:
                targets[including.id].add(target.id)
                self._add("includes", including.id, target.id, (evidence.id,), status, reason)
            if reason:
                self._diagnostics.append(relation_diagnostic("graph.include-" + reason, evidence, reason, "includes"))
        return targets

    def _calls_and_macro_invocations(self, include_targets: dict[str, set[str]]) -> None:
        for evidence in self._snapshot.evidence:
            if evidence.kind not in {"call_expression", "macro_expansion"} or not isinstance(evidence.value, str):
                continue
            attached = self._index.evidence_entities.get(evidence.id, ())
            call_sites = [item for item in attached if item.kind == "call_site"]
            invocations = [item for item in attached if item.kind == "macro_invocation"]
            symbols = [item for item in attached if item.kind == "symbol"]
            for call_site in call_sites:
                for symbol in symbols:
                    self._add("calls", call_site.id, symbol.id, (evidence.id,), "complete")
            resolution = self._visible_definitions(evidence, include_targets)
            definitions = resolution.definitions
            if definitions and not invocations:
                invocation = _entity_from_evidence("macro_invocation", evidence.value, evidence)
                self._index.entities[invocation.id] = invocation
                invocations = [invocation]
            status = resolution.status
            reason = resolution.reason
            for invocation in invocations:
                for definition in definitions:
                    self._add("invokes_macro", invocation.id, definition.id, (evidence.id,), status, reason)
            if invocations and not definitions:
                self._diagnostics.append(relation_diagnostic("graph.unresolved-macro", evidence, "unresolved-macro", "invokes_macro"))

    def _visible_definitions(self, evidence: Evidence, include_targets: dict[str, set[str]]):
        definitions = self._index.definitions_by_name.get(str(evidence.value), ())
        visible_files = {evidence.subject_id, *include_targets.get(evidence.subject_id, set())}
        resolver = MacroDefinitionResolver(
            self._index.definition_file,
            self._evidence_by_id,
        )
        return resolver.resolve(evidence, definitions, visible_files)

    def _macro_replacements(self) -> None:
        for evidence in self._snapshot.evidence:
            if evidence.kind != "macro_replacement_token" or not isinstance(evidence.value, str):
                continue
            if evidence.metadata.get("tokenRole") != "call_candidate":
                continue
            definition_id = evidence.metadata.get("macroDefinitionEvidenceId")
            definition = self._index.definition_by_evidence.get(str(definition_id))
            if definition is None:
                raise ValueError("replacement token references an unknown macro definition")
            unsupported = tuple(evidence.metadata.get("unsupportedSemantics", ()))
            unsupported_reason = "unsupported-preprocessor-semantics" if unsupported else None
            targets = self._index.definitions_by_name.get(evidence.value, ())
            if targets:
                status = "complete" if len(targets) == 1 and not unsupported else "partial"
                reasons = tuple(
                    item
                    for item in ("ambiguous-macro-definition" if len(targets) != 1 else None, unsupported_reason)
                    if item
                )
                reason = ",".join(reasons) or None
                for target in targets:
                    self._add("expands_to", definition.id, target.id, (evidence.id,), status, reason)
                continue
            symbol = _symbol_entity(evidence.value)
            self._index.entities[symbol.id] = symbol
            status = "partial" if unsupported else "complete"
            self._add("expands_to", definition.id, symbol.id, (evidence.id,), status, unsupported_reason)
            self._add("calls", definition.id, symbol.id, (evidence.id,), status, unsupported_reason)

    def _branch_relations(self) -> None:
        by_group: dict[str, list[BranchRecord]] = defaultdict(list)
        for record in self._index.branches:
            by_group[record.group.id].append(record)
            self._add("has_branch", record.group.id, record.branch.id, (record.evidence.id,), "complete")
            self._add("defines", record.evidence.subject_id, record.implementation.id, (record.evidence.id,), "complete")
            self._add("guarded_by", record.implementation.id, record.branch.id, tuple(sorted({record.evidence.id, *record.implementation.properties.get("architectureEvidenceIds", ())})), "complete")
            local = self._branches_by_path.get(record.evidence.location.start.path, ()) if record.evidence.location else ()
            parents = [parent for parent in local if parent.group.id != record.group.id
                       and parent.evidence.location != record.evidence.location
                       and _contains(parent.evidence.location, record.evidence.location)]
            if parents:
                parent = min(parents, key=lambda item: (_span_size(item.evidence.location), item.branch.id))
                self._add("guarded_by", record.branch.id, parent.branch.id,
                          (record.evidence.id, parent.evidence.id), "complete", metadata={"nestedGuard": True})

        for evidence_id, attached in self._index.evidence_entities.items():
            evidence = self._first_evidence.get(evidence_id)
            if evidence is None or evidence.kind in {"preprocessor_condition", "preprocessor_branch"}:
                continue
            local_branches = self._branches_by_path.get(evidence.location.start.path, ()) if evidence.location else ()
            branch = _innermost_branch(evidence, local_branches)
            if branch is None:
                continue
            for entity in attached:
                if entity.kind in {"macro_definition", "macro_invocation", "call_site", "include_site", "asm_site", "attribute_site"}:
                    self._add("guarded_by", entity.id, branch.branch.id, tuple(sorted({evidence.id, branch.evidence.id, *branch.implementation.properties.get("architectureEvidenceIds", ())})), "complete", metadata={"architectureDisposition": "foreign" if branch.role == "foreign" else "unknown"})

        alternatives = {"riscv", "generic", "portable", "scalar", "fallback"}
        for records in by_group.values():
            x86 = [item for item in records if item.role == "x86"]
            siblings = [item for item in records if item.role in alternatives]
            for source in x86:
                for target in siblings:
                    self._add(
                        "alternative_to",
                        source.branch.id,
                        target.branch.id,
                        (source.evidence.id, target.evidence.id),
                        "complete",
                        metadata={
                            "sourceRole": source.role,
                            "targetRole": target.role,
                            "knowledgeIds": tuple(sorted(set(source.knowledge_ids + target.knowledge_ids))),
                        },
                    )
                    self._add(
                        "alternative_to",
                        source.implementation.id,
                        target.implementation.id,
                        (source.evidence.id, target.evidence.id),
                        "complete",
                        metadata={
                            "sourceRole": source.role,
                            "targetRole": target.role,
                            "knowledgeIds": tuple(sorted(set(source.knowledge_ids + target.knowledge_ids))),
                        },
                    )

    def _enum_relations(self) -> None:
        for evidence in self._snapshot.evidence:
            attached = self._index.evidence_entities.get(evidence.id, ())
            if evidence.kind == "enum_declaration":
                for entity in attached:
                    if entity.kind == "enum_type":
                        self._add("defines", evidence.subject_id, entity.id, (evidence.id,), _binding_status(evidence))
            elif evidence.kind == "enum_member_declaration":
                member = next((item for item in attached if item.kind == "enum_member"), None)
                declaration_id = evidence.metadata.get("enumDeclarationEvidenceId")
                enum_type = next((item for item in self._index.evidence_entities.get(str(declaration_id), ()) if item.kind == "enum_type"), None)
                if member is not None:
                    self._add("defines", evidence.subject_id, member.id, (evidence.id,), _binding_status(evidence))
                if enum_type is not None and member is not None:
                    self._add("contains", enum_type.id, member.id, (str(declaration_id), evidence.id), _binding_status(evidence))
            elif evidence.kind == "enum_member_reference":
                reference = next((item for item in attached if item.kind == "enum_member_reference"), None)
                if reference is None:
                    continue
                member_ids = tuple(value for value in evidence.metadata.get("enumMemberDeclarationEvidenceIds", ()) if isinstance(value, str))
                status = _binding_status(evidence)
                for member_id in member_ids:
                    member = next((item for item in self._index.evidence_entities.get(member_id, ()) if item.kind == "enum_member"), None)
                    if member is not None:
                        self._add("contains", member.id, reference.id, (member_id, evidence.id), status)
                predicates = [
                    item
                    for candidate in self._enum_conditions.containing(evidence)
                    for item in self._index.evidence_entities.get(candidate.id, ())
                    if item.kind == "selection_predicate"
                ]
                for predicate in predicates:
                    for member_id in member_ids:
                        member = next((item for item in self._index.evidence_entities.get(member_id, ()) if item.kind == "enum_member"), None)
                        if member is not None:
                            condition = next(item for entity, item in self._predicate_evidence[predicate.id] if entity == predicate)
                            relation_status = "unknown" if condition.metadata.get("templateDependent") else status
                            self._add("selects", predicate.id, member.id, (condition.id, evidence.id, member_id), relation_status, metadata={"selectionContext": condition.metadata.get("selectionContext", "unknown"), "templateDependent": bool(condition.metadata.get("templateDependent"))})
                            self._guard_enum_downstream(predicate, condition, evidence, member_id, relation_status)

    def _guard_enum_downstream(self, predicate: Entity, condition: Evidence, reference: Evidence, member_id: str, status: str) -> None:
        end_line = condition.metadata.get("guardEndLine")
        if not isinstance(end_line, int) or condition.location is None:
            return
        start_line = condition.location.end.line
        items = self._enum_dependencies.get(condition.subject_id, ())
        lines = self._enum_dependency_lines.get(condition.subject_id, ())
        for candidate in items[bisect_left(lines, start_line):bisect_right(lines, end_line)]:
            dependency = _x86_knowledge_ids(candidate, self._knowledge, self._knowledge_patterns)
            for entity in self._index.evidence_entities.get(candidate.id, ()):
                if entity.kind not in {"call_site", "symbol", "include_site", "asm_site", "attribute_site"}:
                    continue
                details = {
                    "enumDependency": bool(dependency),
                    "itemKind": "source_x86_dependency" if dependency else "source_dependency",
                    "knowledgeIds": dependency,
                    "selectionContext": condition.metadata.get("selectionContext", "unknown"),
                }
                self._add("guarded_by", entity.id, predicate.id, (member_id, reference.id, condition.id, candidate.id), status, metadata=details)

    def _add(
        self,
        kind: str,
        source_id: str,
        target_id: str,
        evidence_ids: tuple[str, ...],
        status: str,
        reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        details = dict(metadata or {})
        reasons = set(filter(None, reason.split(",") if reason else ()))
        referenced_evidence = {identifier: self._evidence_by_id[identifier]
                               for identifier in evidence_ids if identifier in self._evidence_by_id}
        if referenced_evidence and any(
            item.confidence != "high" and not (
                kind == "guarded_by" and details.get("architectureDisposition") == "foreign"
                and item.metadata.get("structureComplete") is True
            ) for item in referenced_evidence.values()
        ):
            status = "partial"
            reasons.add("partial-evidence")
        if reasons:
            details["reason"] = ",".join(sorted(reasons))
        provenance = set(evidence_ids)
        bucket_key = (kind, source_id, target_id, status)
        bucket = self._relation_buckets[bucket_key]
        for existing_id in tuple(bucket):
            existing = self._relations[existing_id]
            if (
                existing.kind == kind
                and existing.source_id == source_id
                and existing.target_id == target_id
                and existing.status == status
                and dict(existing.metadata) == details
            ):
                provenance.update(existing.evidence_ids)
                del self._relations[existing.id]
                bucket.remove(existing.id)
        stable_evidence_ids = tuple(sorted(provenance))
        relation_id = stable_id("relation", 1, kind, source_id, target_id, stable_evidence_ids, status, details)
        relation = Relation(
            relation_id,
            kind,
            source_id,
            target_id,
            stable_evidence_ids,
            "high" if status == "complete" else "medium",
            status,
            details,
        )
        self._relations[relation.id] = relation
        if relation.id not in bucket:
            bucket.append(relation.id)


class EvidenceGraphAnalyzer:
    __slots__ = ("_indexer", "_store_factory", "_budgets", "_demand_selector")

    def __init__(
        self,
        indexer: GraphEntityIndexer | None = None,
        store_factory: Callable[[], GraphStore] = NetworkXGraphStore,
        budgets: ProofBudgets = ProofBudgets(),
        demand_selector: Callable | None = None,
    ) -> None:
        self._indexer = indexer or GraphEntityIndexer()
        self._store_factory = store_factory
        self._budgets = budgets
        self._demand_selector = demand_selector

    def analyze(
        self,
        context: ScanContext,
        facts: NormalizedSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> StageResult[AnalysisSnapshot]:
        try:
            _validate_snapshot(facts)
            index = self._indexer.index(context, facts, knowledge)
            relations, diagnostics = RelationBuilder(context, facts, knowledge, index).build()
            _validate_relations(index, facts, relations)
            store = self._store_factory()
            for entity in sorted(index.entities.values(), key=lambda item: item.id):
                store.add_entity(entity)
            for relation in relations:
                store.add_relation(relation)
            terminal_ids = tuple(
                item.id
                for item in index.entities.values()
                if item.kind == "symbol"
            )
            proof_source_ids = tuple(
                item.id
                for item in index.entities.values()
                if item.kind in {"source_file", "macro_invocation"}
            )
            demand = None if self._demand_selector is None else self._demand_selector(facts, knowledge)
            proofs = ProofPathResolver(store, self._budgets).resolve(
                proof_source_ids, terminal_ids, relations, required_evidence_ids=demand,
            )
            derived = list(relations)
            relations_by_id = {item.id: item for item in relations}
            for proof in proofs:
                evidence_ids = tuple(
                    sorted(
                        {
                            evidence_id
                            for relation_id in proof.relation_ids
                            for relation in (relations_by_id.get(relation_id),)
                            if relation is not None
                            for evidence_id in relation.evidence_ids
                        }
                    )
                )
                derived.append(
                    Relation(
                        stable_id("relation", 1, "reachable_from", proof.source_id, proof.target_id, proof.id),
                        "reachable_from",
                        proof.source_id,
                        proof.target_id,
                        evidence_ids,
                        "medium",
                        "unknown",
                        {"reason": "build-selection-deferred", "proofPathId": proof.id},
                    )
                )
            all_relations = tuple(sorted({item.id: item for item in derived}.values(), key=_relation_key))
            snapshot = AnalysisSnapshot(
                relations=all_relations,
                entities=tuple(sorted(index.entities.values(), key=lambda item: item.id)),
                proof_paths=proofs,
            )
            partial = diagnostics or any(item.status != "complete" for item in all_relations) or any(
                item.status != "complete" for item in proofs
            )
            return StageResult(
                value=snapshot,
                status=CompletionStatus.PARTIAL if partial else CompletionStatus.COMPLETE,
                diagnostics=diagnostics,
            )
        except (TypeError, ValueError, KeyError) as exc:
            diagnostic = Diagnostic(
                code="graph.invalid-analysis-input",
                stage="analyzer.evidence-graph",
                severity=DiagnosticSeverity.ERROR,
                message=f"Evidence Graph rejected invalid input: {type(exc).__name__}",
                producer="evidence-graph-analyzer",
                details={"reason": str(exc)[:256]},
                affects_exit_code=True,
            )
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(diagnostic,))


def _entity_from_evidence(kind: str, name: str, evidence: Evidence) -> Entity:
    location = evidence.location
    entity_id = stable_id("graph_entity", 1, kind, name, location, evidence.metadata.get("compilationContextId"))
    return Entity(
        entity_id,
        kind,
        name,
        location,
        {"identityVersion": 1, "sourceEvidenceId": evidence.id},
    )


def _symbol_entity(name: str) -> Entity:
    return Entity(stable_id("graph_entity", 1, "symbol", name), "symbol", name, properties={"identityVersion": 1})


def _relation_key(relation: Relation) -> tuple[str, str, str, str]:
    return relation.kind, relation.source_id, relation.target_id, relation.id


def _contains(outer: SourceSpan | None, inner: SourceSpan | None) -> bool:
    if outer is None or inner is None or outer.start.path != inner.start.path:
        return False
    outer_start = (outer.start.line, outer.start.column or 1)
    outer_end = (outer.end.line, outer.end.column or 1)
    inner_start = (inner.start.line, inner.start.column or 1)
    inner_end = (inner.end.line, inner.end.column or 1)
    return outer_start <= inner_start and inner_end <= outer_end


def _span_size(span: SourceSpan | None) -> tuple[int, int]:
    if span is None:
        return (10**9, 10**9)
    return span.end.line - span.start.line, (span.end.column or 1) - (span.start.column or 1)


def _index_branches(
    evidence_items: tuple[Evidence, ...],
    entities: dict[str, Entity],
    evidence_entities: dict[str, list[Entity]],
    knowledge: KnowledgeSnapshot,
) -> tuple[BranchRecord, ...]:
    # Query indexes live only for this snapshot; preserve order within each bucket.
    by_subject: dict[str, list[Evidence]] = defaultdict(list)
    groups_by_path: dict[str, list[tuple[Evidence, Entity]]] = defaultdict(list)
    group_counts: dict[str, int] = defaultdict(int)
    for evidence in evidence_items:
        by_subject[evidence.subject_id].append(evidence)
    branch_knowledge = replace(knowledge, entries=tuple(
        entry for entry in knowledge.entries
        if entry.architecture_family.lower() == "x86"
        and entry.fact_kind in {"architectureAliases", "platformMacros", "targetFeatures"}
    ))
    roots = [
        item
        for item in evidence_items
        if item.kind == "preprocessor_condition"
        and item.metadata.get("nodeType") in {"preproc_if", "preproc_ifdef", "preproc_ifndef"}
    ]
    records: list[BranchRecord] = []
    for root in roots:
        group = _entity_from_evidence("condition_group", str(root.value), root)
        branch = _entity_from_evidence("branch", f"if:{root.value}", root)
        entities[group.id] = group
        entities[branch.id] = branch
        evidence_entities[root.id].extend((group, branch))
        role, knowledge_ids = _branch_role(
            str(root.value),
            branch_knowledge,
            fallback=False,
            negated=root.metadata.get("nodeType") == "preproc_ifndef" or bool(root.metadata.get("conditionNegated")) or bool(re.match(r"\s*!", str(root.value))),
        )
        foreign_proof = foreign_guard_proof(root, by_subject[root.subject_id])
        if foreign_proof and role != "x86":
            role = "foreign"
        implementation = _branch_implementation(entities[root.subject_id], branch, role, knowledge_ids, foreign_proof)
        entities[implementation.id] = implementation
        records.append(BranchRecord(group, branch, implementation, root, role, knowledge_ids))
        if root.location is not None:
            groups_by_path[root.location.start.path].append((root, group))
        group_counts[group.id] += 1

    branch_evidence = [
        item
        for item in evidence_items
        if item.kind == "preprocessor_branch"
        or (
            item.kind == "preprocessor_condition"
            and item.metadata.get("nodeType") == "preproc_elif"
        )
    ]
    for item in branch_evidence:
        local_groups = groups_by_path.get(item.location.start.path, ()) if item.location else ()
        containing = [(root, group) for root, group in local_groups if _contains(root.location, item.location)]
        if not containing:
            continue
        root, group = min(containing, key=lambda value: _span_size(value[0].location))
        ordinal = 1 + group_counts[group.id]
        fallback = item.kind == "preprocessor_branch" and str(item.value) == "else"
        role, knowledge_ids = _branch_role(str(item.value), branch_knowledge, fallback=fallback)
        branch = _entity_from_evidence("branch", f"{ordinal}:{item.value}", item)
        foreign_proof = () if fallback else foreign_guard_proof(item, by_subject[item.subject_id])
        if foreign_proof and role != "x86":
            role = "foreign"
        implementation = _branch_implementation(entities[item.subject_id], branch, role, knowledge_ids, foreign_proof)
        entities[branch.id] = branch
        entities[implementation.id] = implementation
        evidence_entities[item.id].append(branch)
        records.append(BranchRecord(group, branch, implementation, item, role, knowledge_ids))
        group_counts[group.id] += 1
    return tuple(sorted(records, key=lambda item: (item.group.id, item.evidence.location.start.line if item.evidence.location else 0, item.branch.id)))


def _branch_role(
    value: str,
    knowledge: KnowledgeSnapshot,
    *,
    fallback: bool,
    negated: bool = False,
) -> tuple[str, tuple[str, ...]]:
    if fallback:
        return "fallback", ()
    condition = re.sub(r"/\*.*?\*/|//[^\r\n]*", " ", value, flags=re.DOTALL)
    for role, pattern in _ROLE_PATTERNS.items():
        if pattern.search(condition):
            return ("unknown", ()) if negated else (role, ())
    matched = []
    lowered = condition.lower()
    for entry in knowledge.entries:
        if entry.architecture_family.lower() != "x86":
            continue
        if entry.fact_kind not in {"architectureAliases", "platformMacros", "targetFeatures"}:
            continue
        token = entry.canonical_value.lower()
        if token and re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", lowered):
            matched.append(entry.id)
    if matched or re.search(r"(?i)(?<![A-Za-z0-9])(?:x86(?:_64)?|i[3-6]86|sse|avx)(?![A-Za-z0-9])", condition):
        tokens = {entry.canonical_value.casefold() for entry in knowledge.entries if entry.id in matched}
        necessary = required_foreign(condition, lambda name: (name,) if name.casefold() in tokens or re.search(r"(?i)(?<![A-Za-z0-9])(?:x86(?:_64)?|i[3-6]86|sse|avx)(?![A-Za-z0-9])", name) else ())
        return ("unknown" if negated or not necessary else "x86"), tuple(sorted(set(matched)))
    return "unknown", ()


def _branch_implementation(
    source_file: Entity,
    branch: Entity,
    role: str,
    knowledge_ids: tuple[str, ...],
    architecture_evidence_ids: tuple[str, ...] = (),
) -> Entity:
    return Entity(
        stable_id("graph_entity", 1, "branch_implementation", source_file.id, branch.id),
        "implementation",
        f"{source_file.name}#{branch.name}",
        branch.location,
        {
            "identityVersion": 1,
            "sourceFileId": source_file.id,
            "branchId": branch.id,
            "role": role,
            "knowledgeIds": knowledge_ids,
            "architectureEvidenceIds": architecture_evidence_ids,
        },
    )


def _innermost_branch(evidence: Evidence, branches: tuple[BranchRecord, ...]) -> BranchRecord | None:
    candidates = [item for item in branches if _contains(item.evidence.location, evidence.location)]
    return min(candidates, key=lambda item: _span_size(item.evidence.location), default=None)


def _binding_status(evidence: Evidence) -> str:
    value = evidence.metadata.get("bindingStatus", "unknown")
    return value if value in {"complete", "partial", "ambiguous", "unknown"} else "unknown"


def _x86_knowledge_ids(evidence: Evidence, knowledge: KnowledgeSnapshot, patterns: dict | None = None) -> tuple[str, ...]:
    if not isinstance(evidence.value, str):
        return ()
    kinds = {
        "call_expression": {"intrinsics", "builtins", "cpuPlatformApis"},
        "type_reference": {"vectorTypes"},
        "include": {"headers"},
        "inline_asm": {"assemblyInstructions", "registerNames"},
        "declaration_attribute": {"targetFeatures", "architectureAliases"},
    }.get(evidence.kind, set())
    lowered = evidence.value.casefold()
    cache = patterns if patterns is not None else {}
    if evidence.kind not in cache:
        cache[evidence.kind] = tuple(
            (entry.id, entry.canonical_value.casefold(),
             re.compile(rf"(?<![A-Za-z0-9_]){re.escape(entry.canonical_value.casefold())}(?![A-Za-z0-9_])"))
            for entry in knowledge.entries
            if entry.architecture_family.casefold() == "x86" and entry.fact_kind in kinds
        )
    matches = []
    for identifier, token, pattern in cache[evidence.kind]:
        if lowered == token or pattern.search(lowered):
            matches.append(identifier)
    return tuple(sorted(set(matches)))


def _validate_snapshot(snapshot: NormalizedSnapshot) -> None:
    entity_ids = {item.id for item in snapshot.entities}
    evidence_ids = {item.id for item in snapshot.evidence}
    for evidence in snapshot.evidence:
        if evidence.subject_id not in entity_ids:
            raise ValueError("Evidence references an unknown Entity")
    for fact in snapshot.facts:
        if fact.subject_id not in entity_ids or not set(fact.evidence_ids).issubset(evidence_ids):
            raise ValueError("NormalizedFact references unknown Entity or Evidence")


def _validate_relations(index: GraphIndex, snapshot: NormalizedSnapshot, relations: tuple[Relation, ...]) -> None:
    entity_ids = set(index.entities)
    evidence_ids = {item.id for item in snapshot.evidence}
    for relation in relations:
        if relation.source_id not in entity_ids or relation.target_id not in entity_ids:
            raise ValueError("Relation references an unknown Entity")
        if not set(relation.evidence_ids).issubset(evidence_ids):
            raise ValueError("Relation references unknown Evidence")
