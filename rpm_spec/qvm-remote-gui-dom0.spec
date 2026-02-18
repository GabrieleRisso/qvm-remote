Name:           qvm-remote-gui-dom0
Version:        @VERSION@
Release:        1%{?dist}
Summary:        GTK3 graphical interface for qvm-remote-dom0 service manager
License:        GPLv2+
Group:          Qubes
URL:            https://github.com/user/qvm-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
Requires:       qvm-remote-dom0 >= 1.0.0
Requires:       qubes-core-dom0
Requires:       python3 >= 3.8
Requires:       python3-gobject >= 3.30
Requires:       gtk3 >= 3.22

%description
GTK3 graphical interface for the qvm-remote dom0 service manager.
Provides a tabbed interface for monitoring daemon status, managing
authorized virtual machines, and viewing the daemon log.
Built following Qubes OS 4.3 UI conventions.

%prep
%setup -q

%build
# Pure Python -- nothing to compile.

%install
make install-gui-dom0 DESTDIR=%{buildroot}

%files
/usr/bin/qvm-remote-dom0-gui
/usr/lib/qvm-remote/qubes_remote_ui.py
/usr/lib/qvm-remote/version
/usr/share/applications/qvm-remote-dom0-gui.desktop
