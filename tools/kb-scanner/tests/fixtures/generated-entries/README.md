# Generated Entry Fixtures

These fixtures pin representative generated x86 entries on disk so tests do not hide source samples inside Python code.

Layout:

```text
generated-entries/
  single-file/
    c/
    cpp/
  folder-matrix/
    c/
    cpp/
```

Each `before-x86-only` sample should produce findings. Each `after-portable` sample represents the fixed version and should produce no findings.
