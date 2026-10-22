from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


LEGACY_FACT_KINDS = ("headers", "intrinsics", "builtins", "vectorTypes", "platformMacros", "compilerFlags")
NEW_FACT_KINDS = (
    "assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures", "architectureAliases", "vectorWidthMarkers",
)
FACT_KINDS = (*LEGACY_FACT_KINDS, *NEW_FACT_KINDS)
SEMANTIC_SCOPES = ("x86-only", "x86-toolchain", "migration-sensitive")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _relative_json_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in normalized.split("/"):
        raise ValueError("path must be project relative")
    if not normalized.endswith(".json"):
        raise ValueError("path must name a JSON file")
    return normalized


def _relative_source_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in normalized.split("/"):
        raise ValueError("source path must be relative")
    return normalized


def _complete_digest(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError("sha256 must be a complete lowercase digest")
    return value


class GeneratedSourceModel(_StrictModel):
    sourceId: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _relative_json_path(value)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return _complete_digest(value)


class KnowledgeManifestModel(_StrictModel):
    """Frozen v1 contract; curatedSets remains invalid."""

    schemaVersion: str = Field(pattern=r"^1\.0$")
    catalogId: str = Field(min_length=1)
    version: str = Field(min_length=1)
    generatedSources: tuple[GeneratedSourceModel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "KnowledgeManifestModel":
        _require_unique(self.generatedSources, "sourceId", "path")
        return self


class ManifestSourceModel(GeneratedSourceModel):
    kind: Literal["legacy-generated", "generated-v2"]


class CuratedManifestSourceModel(GeneratedSourceModel):
    kind: Literal["curated-v1"]
    referencePath: str
    referenceSha256: str

    @field_validator("referencePath")
    @classmethod
    def validate_reference_path(cls, value: str) -> str:
        return _relative_json_path(value)

    @field_validator("referenceSha256")
    @classmethod
    def validate_reference_sha256(cls, value: str) -> str:
        return _complete_digest(value)


RuntimeManifestSourceModel = Annotated[Union[ManifestSourceModel, CuratedManifestSourceModel], Field(discriminator="kind")]


class KnowledgeManifestV2Model(_StrictModel):
    schemaVersion: str = Field(pattern=r"^2\.0$")
    catalogId: str = Field(min_length=1)
    version: str = Field(min_length=1)
    sources: tuple[RuntimeManifestSourceModel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "KnowledgeManifestV2Model":
        _require_unique(self.sources, "sourceId", "path")
        runtime_paths = [item.path for item in self.sources]
        reference_paths = [item.referencePath for item in self.sources if isinstance(item, CuratedManifestSourceModel)]
        if set(runtime_paths) & set(reference_paths) or len(reference_paths) != len(set(reference_paths)):
            raise ValueError("runtime and reference paths must be unique")
        return self


class GeneratedFactsModel(_StrictModel):
    source: dict[str, Any]
    headers: tuple[str, ...]
    intrinsics: tuple[str, ...]
    builtins: tuple[str, ...]
    vectorTypes: tuple[str, ...]
    platformMacros: tuple[str, ...]
    compilerFlags: tuple[str, ...]

    @field_validator(*LEGACY_FACT_KINDS)
    @classmethod
    def validate_entries(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("generated fact values must be non-empty strings")
        return values

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_value(value)
        return value


class SourceDescriptorModel(_StrictModel):
    sourceId: str = Field(min_length=1)
    officialUrl: HttpUrl
    release: str = Field(min_length=1)
    revision: str
    license: str = Field(min_length=1)
    collectedAt: str
    inputPaths: tuple[str, ...] = Field(min_length=1)
    inputSha256: tuple[str, ...] = Field(min_length=1)

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if value in {"main", "master", "trunk"} or not _REVISION.fullmatch(value):
            raise ValueError("revision must be an exact lowercase 40-character commit")
        return value

    @field_validator("collectedAt")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not _DATE.fullmatch(value):
            raise ValueError("collectedAt must use YYYY-MM-DD")
        return value

    @field_validator("inputPaths")
    @classmethod
    def validate_input_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_relative_source_path(value) for value in values)

    @field_validator("inputSha256")
    @classmethod
    def validate_input_hashes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_complete_digest(value) for value in values)

    @model_validator(mode="after")
    def validate_inputs(self) -> "SourceDescriptorModel":
        if len(self.inputPaths) != len(self.inputSha256):
            raise ValueError("each input path requires one digest")
        if len(self.inputPaths) != len(set(self.inputPaths)):
            raise ValueError("input paths must be unique")
        return self


class GeneratedFactV2Model(_StrictModel):
    factKind: Literal["assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures", "architectureAliases", "vectorWidthMarkers"]
    architectureFamily: Literal["x86"]
    canonicalValue: str = Field(min_length=1)
    semanticScope: Literal["x86-only", "x86-toolchain", "migration-sensitive"]

class GeneratedFactsV2Model(_StrictModel):
    schemaVersion: str = Field(pattern=r"^2\.0$")
    source: SourceDescriptorModel
    facts: tuple[GeneratedFactV2Model, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_facts(self) -> "GeneratedFactsV2Model":
        keys = [(item.factKind, item.architectureFamily, item.canonicalValue) for item in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("generated facts must be unique")
        return self


class SourceReferenceModel(_StrictModel):
    referenceId: str = Field(min_length=1)
    officialUrl: HttpUrl
    release: str = Field(min_length=1)
    revision: str
    logicalLocation: str = Field(min_length=1)
    license: str = Field(min_length=1)
    collectedAt: str
    sha256: str

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        return SourceDescriptorModel.validate_revision(value)

    @field_validator("collectedAt")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return SourceDescriptorModel.validate_date(value)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return _complete_digest(value)


class ReferenceRegistryModel(_StrictModel):
    schemaVersion: str = Field(pattern=r"^1\.0$")
    references: tuple[SourceReferenceModel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_references(self) -> "ReferenceRegistryModel":
        _require_unique(self.references, "referenceId")
        return self


class CuratedEntryModel(_StrictModel):
    entryId: str = Field(min_length=1)
    factKind: Literal["assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures", "architectureAliases", "vectorWidthMarkers"]
    architectureFamily: Literal["x86"]
    canonicalValue: str = Field(min_length=1)
    semanticScope: Literal["x86-only", "x86-toolchain", "migration-sensitive"]
    referenceIds: tuple[str, ...] = Field(min_length=1)
    reviewStatus: Literal["accepted"]

    @field_validator("referenceIds")
    @classmethod
    def validate_reference_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError("reference ids must be non-empty and unique")
        return values


class CuratedFactsModel(_StrictModel):
    schemaVersion: str = Field(pattern=r"^1\.0$")
    sourceId: str = Field(min_length=1)
    reviewPolicy: str = Field(min_length=1)
    reviewPolicyVersion: str = Field(min_length=1)
    entries: tuple[CuratedEntryModel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> "CuratedFactsModel":
        _require_unique(self.entries, "entryId")
        keys = [(item.factKind, item.architectureFamily, item.canonicalValue) for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("curated facts must be unique")
        return self


class CandidateDecisionModel(_StrictModel):
    decisionId: str = Field(min_length=1)
    category: Literal[
        "assembly-instruction", "register", "cpu-platform-api", "target-feature", "architecture-alias", "vector-width", "linker-source",
    ]
    candidateValue: str = Field(min_length=1)
    status: Literal["generated", "accepted", "rejected", "deferred"]
    referenceIds: tuple[str, ...]
    rationale: str = Field(min_length=1)
    runtimeFactKind: Literal[
        "assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures", "architectureAliases", "vectorWidthMarkers",
    ] | None = None

    @model_validator(mode="after")
    def validate_runtime_decision(self) -> "CandidateDecisionModel":
        if self.status in {"generated", "accepted"} and (not self.referenceIds or self.runtimeFactKind is None):
            raise ValueError("runtime decisions require references and a runtime fact kind")
        if self.status in {"rejected", "deferred"} and self.runtimeFactKind is not None:
            raise ValueError("non-runtime decisions must not declare a runtime fact kind")
        if len(self.referenceIds) != len(set(self.referenceIds)):
            raise ValueError("decision references must be unique")
        return self


class DecisionLedgerModel(_StrictModel):
    schemaVersion: str = Field(pattern=r"^1\.0$")
    scope: Literal["c-cpp-x86-to-riscv-static-analysis"]
    decisions: tuple[CandidateDecisionModel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_decisions(self) -> "DecisionLedgerModel":
        _require_unique(self.decisions, "decisionId")
        return self


def _require_unique(items: tuple[Any, ...], *fields: str) -> None:
    for field in fields:
        values = [getattr(item, field) for item in items]
        if len(values) != len(set(values)):
            raise ValueError(f"{field} values must be unique")


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json_value(item)
        return
    raise ValueError("source metadata must be JSON-safe")
