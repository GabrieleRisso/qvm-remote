Name:           qvm-remote
Version:        @VERSION@
Release:        1%{?dist}
Summary:        Execute commands in Qubes OS dom0 from a VM
License:        GPLv2+
Group:          Qubes
URL:            https://github.com/user/qvm-remote
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
Requires:       python3 >= 3.8
Obsoletes:      qubes-remote < 1.0.0

%description
Client tool for qvm-remote.  Submits commands to a file-based queue,
waits for the dom0-side daemon to process them, and returns the result
with full stdout/stderr passthrough and exit code preservation.
Written in Python following Qubes OS tool conventions.

%prep
%setup -q

%build
# Pure Python -- nothing to compile.

%install
make install-vm DESTDIR=%{buildroot}

%files
/usr/bin/qvm-remote
