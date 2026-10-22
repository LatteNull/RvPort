ASSESSMENT_DIMENSIONS = (
    "input_completeness",
    "target_reachability",
    "x86_dependency",
    "riscv_or_generic_alternative",
    "test_selection_coverage",
    "packaging_constraint",
)

DIMENSION_STATES = frozenset({"satisfied", "issue", "unknown", "not_applicable"})
PROJECT_STATES = frozenset(
    {
        "architecture_independent",
        "x86_only",
        "multiarch_without_riscv",
        "partial_riscv",
        "riscv_ready",
        "provisional",
        "unknown",
    }
)
