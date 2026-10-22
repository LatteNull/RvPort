Name: demo
Version: 1.0
Release: 1
Summary: demo package

%description
Demo package.

%build
CFLAGS="%{optflags} -mavx2" make

%check
./run-tests --skip-riscv
