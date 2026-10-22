Name: demo
Version: 1
ExclusiveArch: riscv64 x86_64
%ifarch riscv64
BuildRequires: libportable-devel
%else
BuildRequires: libx86-devel
%endif
%build
echo %(touch /tmp/kb-scanner-build-selection-marker)
%{lua:os.execute('touch /tmp/kb-scanner-build-selection-marker')}
%include unsafe.inc
