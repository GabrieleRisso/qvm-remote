Name:           qvm-remote-gui
Version:        @VERSION@
Release:        1%{?dist}
Summary:        GTK3 graphical interface for qvm-remote (VM client)
License:        GPLv2+
Group:          Qubes
URL:            https://github.com/user/qvm-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
Requires:       qvm-remote >= 1.0.0
Requires:       python3 >= 3.8
Requires:       python3-gobject >= 3.30
Requires:       gtk3 >= 3.22

%description
GTK3 graphical interface for the qvm-remote VM client.  Provides a
tabbed interface for command execution with streaming output, command
history, authentication key management, and audit log viewing.
Built following Qubes OS 4.3 UI conventions.

%prep
%setup -q

%build
# Pure Python -- nothing to compile.

%install
make install-gui-vm DESTDIR=%{buildroot}

%files
/usr/bin/qvm-remote-gui
/usr/lib/qvm-remote/qubes_remote_ui.py
/usr/lib/qvm-remote/version
/usr/share/applications/qvm-remote-gui.desktop
