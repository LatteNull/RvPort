# Autoconf human oracle and pinned sources

English | [简体中文](README.md)

This directory contains read-only test data, not build inputs. Never execute its scripts. Complete sources, pinned commits, and SHA-256 are in `oracle.json`. GNU originals and GPLv3/additional permissions are retained in `gnu/`; libarchive originals/licenses are in `libarchive/`. Preserve LF endings and do not reformat third-party text.

## Independent human judgments

- Neither GCC 4.8.0 script contains a riscv literal. That alone cannot prove rejection. External commands/dynamic shell in the full scripts require unknown in this bounded analysis.
- GCC 14.2.0 config.guess has a RISC-V Linux branch at line 1089, but output still depends on `$LIBC`; config.sub has a riscv CPU candidate at line 1254. Literals do not prove a complete successful normalization chain. Earlier external commands also exceed the subset. Expected status is unknown, never fabricated acceptance.
- libarchive configure.ac selects build/autoconf at line 26 and uses parenthesis-free AC_CANONICAL_HOST at line 92. Actual helper scripts are absent. Expect declarations and unavailable/unknown; do not guess future bootstrap output or declare RISC-V unsupported.

The independent small oracle in `tests/test_autoconf_target_component.py` also covers first-match wildcard rejection, explicit riscv rejection, generic-output acceptance, unknown OS, if/elif, parameter trimming, empty output, successful guess followed by rejected sub, and malicious commands. Expected values are not generated backward from scanner output.

## References

- [GNU Autoconf 2.72: canonicalization and build/host/target](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Canonicalizing.html)
- [GNU Autoconf 2.72: helper search and generation](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Input.html)

The local fixture includes only libarchive configuration inputs, not the remaining project source. Full-project regressions use the read-only historical project directory specified in validation records.
