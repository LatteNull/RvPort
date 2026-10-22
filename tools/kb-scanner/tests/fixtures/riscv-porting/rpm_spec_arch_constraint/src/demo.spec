Name: demo
Version: 1.0
Release: 1
Summary: demo package

ExclusiveArch: x86_64 %{ix86}
# ExcludeArch: riscv64

%description
Demo package.

%build
make

%changelog
* Thu Aug 27 2026 Example <example@example.com> - 1.0-1
- Historical note mentioning ExcludeArch: riscv64
