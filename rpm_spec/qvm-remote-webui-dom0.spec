Name:           qvm-remote-webui-dom0
Version:        @VERSION@
Release:        1%{?dist}
Summary:        Air-gapped web admin panel for Qubes OS dom0 (qvm-remote)
License:        GPLv2+
Group:          Qubes
URL:            https://github.com/user/qvm-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       qvm-remote-dom0 >= 1.1.0
Requires:       python3 >= 3.8
Requires:       curl

%description
Air-gapped web admin panel for Qubes OS dom0.  Serves a localhost-only
single-page application on 127.0.0.1:9876 using Python stdlib only.

Includes:
  - Web server with dashboard, VM management, policy enforcement, OpenClaw
  - Systemd watchdog timer for automatic recovery
  - XFCE genmon panel plugin for tray status
  - XFCE autostart script for login-time setup

%prep
%setup -q

%build
# Pure Python + shell scripts -- nothing to compile.

%install
make install-web DESTDIR=%{buildroot}

%post
%systemd_post qubes-global-admin-web.service
%systemd_post qubes-admin-watchdog.timer

%preun
%systemd_preun qubes-global-admin-web.service
%systemd_preun qubes-admin-watchdog.timer

%postun
%systemd_postun_with_restart qubes-global-admin-web.service

%files
%attr(0755,root,root) /usr/bin/qubes-global-admin-web
/etc/systemd/system/qubes-global-admin-web.service
/etc/systemd/system/qubes-admin-watchdog.service
/etc/systemd/system/qubes-admin-watchdog.timer
/usr/share/applications/qubes-global-admin-web.desktop
%attr(0755,root,root) /usr/local/bin/qubes-admin-genmon.sh
%attr(0755,root,root) /usr/local/bin/qubes-admin-autostart.sh
/etc/xdg/autostart/qubes-admin-autostart.desktop
