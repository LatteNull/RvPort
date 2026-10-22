"""Infrastructure adapters for the active KB Scanner application boundary.

Legacy remains available from :mod:`kb_scanner.adapters.legacy` only as an
explicit test oracle.  Importing this package must not load it (or PyYAML) on
the production scan path.
"""

from .cli import StagedContextFactory, scan_request_from_namespace

__all__ = ["StagedContextFactory", "scan_request_from_namespace"]
