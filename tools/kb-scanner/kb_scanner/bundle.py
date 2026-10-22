from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BundleError(ValueError):
    """A scanner bundle is malformed or cannot be trusted."""


@dataclass(frozen=True, slots=True)
class BundleDescriptor:
    root: Path
    rule_pack_id: str
    rule_pack_version: str
    knowledge_manifest_path: Path
    knowledge_manifest_sha256: str
    projection_policy_id: str
    projection_policy_version: int
    identity: str


def load_bundle_descriptor(root: Path, manifest_name: str = "scanner-manifest.json") -> BundleDescriptor:
    bundle_root = root.resolve()
    if not bundle_root.is_dir():
        raise BundleError("bundle root is not a directory")
    manifest_path = (bundle_root / manifest_name).resolve()
    if not manifest_path.is_relative_to(bundle_root):
        raise BundleError("scanner manifest escapes the bundle root")
    try:
        content = manifest_path.read_bytes()
        payload = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"scanner manifest is unavailable or invalid: {type(exc).__name__}") from exc
    root_object = _strict_object(
        payload,
        {"schemaVersion", "rulePack", "knowledgeManifest", "projectionPolicy"},
        "scanner manifest",
    )
    if root_object["schemaVersion"] != "1.0":
        raise BundleError("unsupported scanner manifest version")
    rule_pack = _strict_object(root_object["rulePack"], {"id", "version"}, "rulePack")
    knowledge = _strict_object(root_object["knowledgeManifest"], {"path", "sha256"}, "knowledgeManifest")
    policy = _strict_object(root_object["projectionPolicy"], {"id", "version"}, "projectionPolicy")
    rule_pack_id = _nonempty(rule_pack["id"], "rulePack.id")
    rule_pack_version = _nonempty(rule_pack["version"], "rulePack.version")
    logical_path = _nonempty(knowledge["path"], "knowledgeManifest.path")
    expected_hash = _digest(knowledge["sha256"], "knowledgeManifest.sha256")
    knowledge_path = (bundle_root / logical_path).resolve()
    if Path(logical_path).is_absolute() or not knowledge_path.is_relative_to(bundle_root) or knowledge_path.suffix != ".json":
        raise BundleError("knowledge manifest path must be a bundle-local JSON file")
    try:
        knowledge_bytes = knowledge_path.read_bytes()
    except OSError as exc:
        raise BundleError(f"knowledge manifest is unreadable: {type(exc).__name__}") from exc
    if hashlib.sha256(knowledge_bytes).hexdigest() != expected_hash:
        raise BundleError("knowledge manifest digest does not match scanner manifest")
    policy_id = _nonempty(policy["id"], "projectionPolicy.id")
    policy_version = policy["version"]
    if isinstance(policy_version, bool) or not isinstance(policy_version, int) or policy_version < 1:
        raise BundleError("projectionPolicy.version must be a positive integer")
    identity_material = json.dumps(root_object, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return BundleDescriptor(
        root=bundle_root,
        rule_pack_id=rule_pack_id,
        rule_pack_version=rule_pack_version,
        knowledge_manifest_path=knowledge_path,
        knowledge_manifest_sha256=expected_hash,
        projection_policy_id=policy_id,
        projection_policy_version=policy_version,
        identity=hashlib.sha256(identity_material).hexdigest(),
    )


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise BundleError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BundleError(f"{label} must be a non-empty string")
    return value.strip()


def _digest(value: Any, label: str) -> str:
    digest = _nonempty(value, label)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise BundleError(f"{label} must be a lowercase SHA-256 digest")
    return digest
