Name: unsafe-fixture
Version: 1
Release: 1
Summary: static-only security fixture

%global generated %(touch /tmp/kb-scanner-security-marker)
%global scripted %{lua:os.execute("touch /tmp/kb-scanner-security-marker")}
%include /tmp/kb-scanner-security-marker

%description
This file must never be evaluated by RPM during scanning.
