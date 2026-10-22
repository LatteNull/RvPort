# KB Scanner development and validation

English | [简体中文](development.zh-CN.md)

Run the following commands from the repository root. Mount source code, rules, and scanned samples read-only. Keep dependencies, tests, and outputs inside an isolated Docker environment.

```powershell
docker compose -f tools/kb-scanner/compose.test.yml build kb-scanner-test
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

`tests/run_container_tests.py` is the default container test entry point. It runs specialized gates and the full regression suite. Measure coverage over all source code separately using the commands below; specialized gates do not replace that measurement. Overall and affected-module line and branch coverage must both reach at least 90%, including unloaded project-owned code. Fixtures, third-party code, and generated data are excluded from business-source coverage. Integration, contract, and real-parser regressions do not replace isolated unit tests.

Examples of specialized checks, also from the repository root:

```powershell
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --graph-unit
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test tests/run_container_tests.py --architecture-candidate-noise-unit
```

Test and quality inventories are in `tests/*inventory.json`. Older thresholds in historical inventories are for traceability only; current acceptance requires 90% line and branch coverage. Preserve frozen fact hashes, V1/V2 reader contracts, break semantics, malicious-input checks with no side effects, native-crash regressions, and determinism tests. Do not automatically rewrite human oracles or historical differential ledgers to accept new behavior.

## Coverage over all source code

Run these commands inside the same development container, with the tool root as the working directory. Start the shell through Docker; do not run project Python on the host:

```sh
export COVERAGE_FILE=/tmp/kb-all.coverage
python -m coverage run --branch --source=kb_scanner,scripts,tools -m unittest discover -s tests/unit -t .
python -m coverage json -o /tmp/kb-all-coverage.json
```

Reports must include unloaded files in all three source directories above. Evaluate `covered_lines / num_statements` and `covered_branches / num_branches` for the overall scope and each affected module, with a 90% minimum for both. A nonzero test exit or an unmet threshold fails acceptance. Existing specialized runners retain some historical thresholds; their success alone does not establish current overall acceptance. See the repository [testing and coverage scope](../../../docs/testing-and-coverage.md).

## Maintenance constraints

Frontend position tests must cover UTF-8, CRLF, EOF, and fake Node Point getters that reject access. Keep real Tree-sitter parsing as a separate regression. Test missing inputs, exhausted budgets, damaged manifests, unavailable Clang, and projection/publication failures.

Change only the dependencies explicitly needed in runtime/test lock files and rebuild the test image. The scanner never executes the scanned project's Make, CMake, RPM, shell, or test commands. `compose.test.yml` controls network isolation, a read-only root filesystem, and capability limits.

See the [dependency inventory](dependency-inventory.md) and [knowledge maintenance](knowledge.md).
