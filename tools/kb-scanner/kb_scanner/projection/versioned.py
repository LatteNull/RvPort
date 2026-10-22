from __future__ import annotations

from .projector import CompatibleReportProjector
from .v2.projector import SchemaV2ReportProjector


class VersionedReportProjector:
    def __init__(self, v1=None, v2=None) -> None:
        self._v1 = v1 or CompatibleReportProjector()
        self._v2 = v2 or SchemaV2ReportProjector()

    def project(self, context, *snapshots):
        if context.schema_version == "1.0":
            return self._v1.project(context, *snapshots)
        if context.schema_version == "2.0":
            return self._v2.project(context, *snapshots)
        raise ValueError(f"unsupported schema version: {context.schema_version}")
