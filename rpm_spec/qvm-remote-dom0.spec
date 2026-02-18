Name:           qvm-remote-dom0
Version:        @VERSION@
Release:        1%{?dist}
Summary:        Execute VM commands in Qubes OS dom0 (dom0 component)
License:        GPLv2+
Group:          Qubes
URL:            https://github.com/user/qvm-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       qubes-core-dom0
Requires:       python3 >= 3.8
Obsoletes:      qubes-remote-dom0 < 1.0.0

%description
Dom0 executor daemon for qvm-remote.  Polls designated VMs for queued
commands, verifies HMAC-SHA256 auth tokens, executes in dom0, and writes
results back.  Written in Python following Qubes OS tool conventions.

%prep
%setup -q

%build
# Pure Python -- nothing to compile.

%install
make install-dom0 DESTDIR=%{buildroot}

%post
%systemd_post qvm-remote-dom0.service

%preun
%systemd_preun qvm-remote-dom0.service

%postun
%systemd_postun_with_restart qvm-remote-dom0.service

%files
%attr(0600,root,root) %config(noreplace) /etc/qubes/remote.conf
/usr/bin/qvm-remote-dom0
/etc/systemd/system/qvm-remote-dom0.service
