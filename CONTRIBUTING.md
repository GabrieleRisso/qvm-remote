# Contributing to qvm-remote

Thank you for your interest in improving qvm-remote.

## Requirements

- Python 3.8+ (no external dependencies for CLI tools)
- GTK3 + PyGObject (for GUI, optional)
- Bash (for install script and test harnesses)
- Docker or Podman (for container-based tests)
- rpmbuild (optional, for local RPM builds)

## Development workflow

```bash
# Syntax check (CLI + GUI)
make check

# Unit tests (runs on any machine, no display required)
make test

# RPM install test (Fedora 41 container)
make docker-test

# Full dom0 simulation E2E (Fedora 41 container with mock Qubes tools)
make dom0-test

# Arch Linux client test
make arch-test

# GUI build and import test (Fedora 41 container)
make gui-test

# GUI Xvfb integration test (Fedora 41 container, headless display)
make gui-integration-test

# Run ALL tests across all distros
make all-test

# Build RPMs in container
make docker-rpm
```

## Code style

- Python: standard library only for CLI tools; GTK3/PyGObject for GUI only.
- Target Python 3.8+ (the version shipping in Qubes OS dom0).
- Use `from __future__ import annotations` for modern type hints.
- Keep scripts minimal -- avoid unnecessary flags and configuration.
- Follow Qubes OS naming conventions (`qvm-*` for VM tools, `qvm-*-dom0` for dom0).

## Security considerations

- HMAC comparisons must use `hmac.compare_digest()` (constant-time).
- Subprocess calls must include a `timeout` parameter.
- Key files must be created with `0600` permissions.
- Work files must be written with strict permissions (`0700`) before execution.
- Validate all input (size, binary content) before writing to disk.
- Use the `secrets` module for any random values in security-sensitive contexts.
- Dom0 daemon commands that modify state must check for root privileges.

## Test guidelines

- One assertion per test method.
- Descriptive test names: `test_<component>_<behavior>_<condition>`.
- Tests must run without Qubes OS (skip gracefully when `qvm-run` is unavailable).
- New security features must have a corresponding test in `TestSecurity`.
- GUI tests that need a display should skip gracefully when headless.

## Submitting changes

1. Fork the repository and create a branch.
2. Make your changes, ensuring all tests pass (`make test`).
3. Run the full container test suite if modifying core logic (`make all-test`).
4. Submit a pull request with a clear description of the change.

## Project structure

```
vm/qvm-remote                  VM-side client (Python)
dom0/qvm-remote-dom0           dom0-side daemon (Python)
dom0/qvm-remote-dom0.service   systemd unit
gui/qubes_remote_ui.py         shared GTK3 UI library
gui/qvm-remote-gui             VM-side GUI (GTK3)
gui/qvm-remote-dom0-gui        dom0-side GUI (GTK3)
gui/*.desktop                  desktop entry files
install/install-dom0.sh        dom0 installer script
etc/qubes-remote.conf          config template
rpm_spec/                      RPM spec files (CLI + GUI, dom0 + VM)
pkg/PKGBUILD                   Arch Linux CLI package
pkg/PKGBUILD-gui               Arch Linux GUI package
debian/                        Debian packaging
salt/                          SaltStack formula
test/                          Test suite and Dockerfiles
.github/workflows/ci.yml       GitHub Actions CI
```
