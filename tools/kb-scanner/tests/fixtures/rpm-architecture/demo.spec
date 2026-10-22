Name: demo
Version: 1
Release: 1
Summary: Static scanner oracle
License: MIT
%if "%{_target_cpu}" == "x86_64"
BuildRequires: x86-only
%else
BuildRequires: portable
%endif
Requires: libfoo%{?_isa}
Recommends: liboptional(x86-64)
Requires: unknown%{?__external_isa}%{_arch}
%global machine %(uname -m)
%if "%{machine}" == "riscv64"
Requires: common
%endif
%build
machine=$(uname -m)
case "$machine" in
x86_64|amd64) CFLAGS=-mavx ;;
riscv64) CFLAGS=-O2 ;;
*) CFLAGS=-O1 ;;
esac
