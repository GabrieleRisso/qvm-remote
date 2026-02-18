PREFIX    ?= /usr
BINDIR    ?= $(PREFIX)/bin
LIBDIR    ?= $(PREFIX)/lib/qvm-remote
DATADIR   ?= $(PREFIX)/share
SYSCONFDIR ?= /etc
UNITDIR   ?= /etc/systemd/system
DESTDIR   ?=

VERSION   := $(shell cat version)
TARBALL_DOM0 = qvm-remote-dom0-$(VERSION).tar.gz
TARBALL_VM   = qvm-remote-$(VERSION).tar.gz

GPG_NAME  ?= qvm-remote
CONTAINER_ENGINE ?= $(shell command -v podman 2>/dev/null || echo docker)

.PHONY: help install-vm install-dom0 install-gui-vm install-gui-dom0 \
        install-admin-vm install-admin-dom0 install-web \
        uninstall-vm uninstall-dom0 uninstall-gui-vm uninstall-gui-dom0 \
        uninstall-admin-vm uninstall-admin-dom0 uninstall-web \
        check test clean dist rpm rpm-sign docker-rpm docker-test dom0-test \
        arch-test gui-test gui-integration-test backup-e2e-test all-test deb

help:
	@echo "qvm-remote $(VERSION)"
	@echo ""
	@echo "Install targets:"
	@echo "  install-vm         Install VM-side client (run inside the VM)"
	@echo "  install-dom0       Install dom0-side daemon (run in dom0)"
	@echo "  install-gui-vm     Install VM-side GUI (GTK3, run inside the VM)"
	@echo "  install-gui-dom0   Install dom0-side GUI (GTK3, run in dom0)"
	@echo "  uninstall-vm       Remove VM-side client"
	@echo "  uninstall-dom0     Remove dom0-side daemon"
	@echo "  uninstall-gui-vm   Remove VM-side GUI"
	@echo "  uninstall-gui-dom0 Remove dom0-side GUI"
	@echo "  install-web        Install web admin UI (dom0, localhost:9876)"
	@echo "  uninstall-web      Remove web admin UI"
	@echo ""
	@echo "Build targets:"
	@echo "  dist            Create source tarballs in build/SOURCES/"
	@echo "  rpm             Build RPMs (requires rpmbuild)"
	@echo "  rpm-sign        Sign built RPMs with GPG key (GPG_NAME=$(GPG_NAME))"
	@echo "  docker-rpm      Build RPMs inside a Fedora 41 container"
	@echo ""
	@echo "Other:"
	@echo "  check           Syntax-check all scripts (including GUI)"
	@echo "  test            Run full test suite"
	@echo "  docker-test     Run RPM install test in Fedora 41 container"
	@echo "  dom0-test       Run full dom0 simulation (daemon E2E) in container"
	@echo "  arch-test       Run client test in Arch Linux container"
	@echo "  gui-test        Run GUI build/import test in Fedora 41 container"
	@echo "  gui-integration-test  Run GUI Xvfb integration test in container"
	@echo "  backup-e2e-test Run backup/restore E2E test with git in container"
	@echo "  all-test        Run ALL tests across all distros (full CI)"
	@echo "  clean           Remove build artifacts"

# ── Install targets ────────────────────────────────────────────────

install-vm:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 vm/qvm-remote $(DESTDIR)$(BINDIR)/qvm-remote

install-dom0:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 dom0/qvm-remote-dom0 $(DESTDIR)$(BINDIR)/qvm-remote-dom0
	install -d $(DESTDIR)$(UNITDIR)
	install -m 0644 dom0/qvm-remote-dom0.service $(DESTDIR)$(UNITDIR)/qvm-remote-dom0.service
	install -d $(DESTDIR)$(SYSCONFDIR)/qubes
	install -m 0600 etc/qubes-remote.conf $(DESTDIR)$(SYSCONFDIR)/qubes/remote.conf

install-gui-vm:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 gui/qvm-remote-gui $(DESTDIR)$(BINDIR)/qvm-remote-gui
	install -d $(DESTDIR)$(LIBDIR)
	install -m 0644 gui/qubes_remote_ui.py $(DESTDIR)$(LIBDIR)/qubes_remote_ui.py
	install -m 0644 version $(DESTDIR)$(LIBDIR)/version
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 0644 gui/qvm-remote-gui.desktop $(DESTDIR)$(DATADIR)/applications/qvm-remote-gui.desktop

install-gui-dom0:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 gui/qvm-remote-dom0-gui $(DESTDIR)$(BINDIR)/qvm-remote-dom0-gui
	install -d $(DESTDIR)$(LIBDIR)
	install -m 0644 gui/qubes_remote_ui.py $(DESTDIR)$(LIBDIR)/qubes_remote_ui.py
	install -m 0644 version $(DESTDIR)$(LIBDIR)/version
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 0644 gui/qvm-remote-dom0-gui.desktop $(DESTDIR)$(DATADIR)/applications/qvm-remote-dom0-gui.desktop

uninstall-vm:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote

uninstall-dom0:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote-dom0
	rm -f $(DESTDIR)$(UNITDIR)/qvm-remote-dom0.service

uninstall-gui-vm:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote-gui
	rm -f $(DESTDIR)$(LIBDIR)/qubes_remote_ui.py
	rm -f $(DESTDIR)$(DATADIR)/applications/qvm-remote-gui.desktop

uninstall-gui-dom0:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote-dom0-gui
	rm -f $(DESTDIR)$(LIBDIR)/qubes_remote_ui.py
	rm -f $(DESTDIR)$(DATADIR)/applications/qvm-remote-dom0-gui.desktop

install-admin-vm:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 gui2/qubes-global-admin $(DESTDIR)$(BINDIR)/qubes-global-admin
	install -d $(DESTDIR)$(LIBDIR)
	install -m 0644 gui2/qubes_admin_ui.py $(DESTDIR)$(LIBDIR)/qubes_admin_ui.py
	install -m 0644 version $(DESTDIR)$(LIBDIR)/version
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 0644 gui2/qubes-global-admin.desktop $(DESTDIR)$(DATADIR)/applications/qubes-global-admin.desktop

install-admin-dom0:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 gui2/qubes-global-admin-dom0 $(DESTDIR)$(BINDIR)/qubes-global-admin-dom0
	install -d $(DESTDIR)$(LIBDIR)
	install -m 0644 gui2/qubes_admin_ui.py $(DESTDIR)$(LIBDIR)/qubes_admin_ui.py
	install -m 0644 version $(DESTDIR)$(LIBDIR)/version
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 0644 gui2/qubes-global-admin-dom0.desktop $(DESTDIR)$(DATADIR)/applications/qubes-global-admin-dom0.desktop

uninstall-admin-vm:
	rm -f $(DESTDIR)$(BINDIR)/qubes-global-admin
	rm -f $(DESTDIR)$(LIBDIR)/qubes_admin_ui.py
	rm -f $(DESTDIR)$(DATADIR)/applications/qubes-global-admin.desktop

uninstall-admin-dom0:
	rm -f $(DESTDIR)$(BINDIR)/qubes-global-admin-dom0
	rm -f $(DESTDIR)$(LIBDIR)/qubes_admin_ui.py
	rm -f $(DESTDIR)$(DATADIR)/applications/qubes-global-admin-dom0.desktop

install-web:
	install -d $(DESTDIR)$(BINDIR)
	install -m 0755 webui/qubes-global-admin-web $(DESTDIR)$(BINDIR)/qubes-global-admin-web
	install -d $(DESTDIR)$(UNITDIR)
	install -m 0644 webui/qubes-global-admin-web.service $(DESTDIR)$(UNITDIR)/qubes-global-admin-web.service
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 0644 webui/qubes-global-admin-web.desktop $(DESTDIR)$(DATADIR)/applications/qubes-global-admin-web.desktop

uninstall-web:
	rm -f $(DESTDIR)$(BINDIR)/qubes-global-admin-web
	rm -f $(DESTDIR)$(UNITDIR)/qubes-global-admin-web.service
	rm -f $(DESTDIR)$(DATADIR)/applications/qubes-global-admin-web.desktop

check:
	@python3 -c "import py_compile; py_compile.compile('vm/qvm-remote', doraise=True)" && echo "vm/qvm-remote: ok"
	@python3 -c "import py_compile; py_compile.compile('dom0/qvm-remote-dom0', doraise=True)" && echo "dom0/qvm-remote-dom0: ok"
	@python3 -c "import py_compile; py_compile.compile('gui/qubes_remote_ui.py', doraise=True)" && echo "gui/qubes_remote_ui.py: ok"
	@python3 -c "import py_compile; py_compile.compile('gui/qvm-remote-gui', doraise=True)" && echo "gui/qvm-remote-gui: ok"
	@python3 -c "import py_compile; py_compile.compile('gui/qvm-remote-dom0-gui', doraise=True)" && echo "gui/qvm-remote-dom0-gui: ok"
	@python3 -c "import py_compile; py_compile.compile('gui2/qubes_admin_ui.py', doraise=True)" && echo "gui2/qubes_admin_ui.py: ok"
	@python3 -c "import py_compile; py_compile.compile('gui2/qubes-global-admin', doraise=True)" && echo "gui2/qubes-global-admin: ok"
	@python3 -c "import py_compile; py_compile.compile('gui2/qubes-global-admin-dom0', doraise=True)" && echo "gui2/qubes-global-admin-dom0: ok"
	@python3 -c "import py_compile; py_compile.compile('webui/qubes-global-admin-web', doraise=True)" && echo "webui/qubes-global-admin-web: ok"
	@bash -n install/install-dom0.sh && echo "install/install-dom0.sh: ok"
	@bash -n upgrade-dom0.sh && echo "upgrade-dom0.sh: ok"

test:
	@python3 test/test_qvm_remote.py -v
	@python3 test/test_gui.py -v
	@python3 test/test_gui_wiring.py -v
	@python3 test/test_gui_integration.py -v

clean:
	rm -rf build/

# ── Distribution tarballs ──────────────────────────────────────────

dist: clean
	mkdir -p build/SOURCES build/SPECS
	# dom0 tarball
	mkdir -p build/stage/qvm-remote-dom0-$(VERSION)
	cp -a dom0/ etc/ Makefile version \
	    build/stage/qvm-remote-dom0-$(VERSION)/
	sed 's/@VERSION@/$(VERSION)/g' \
	    rpm_spec/qvm-remote-dom0.spec \
	    > build/SPECS/qvm-remote-dom0.spec
	tar czf build/SOURCES/$(TARBALL_DOM0) \
	    -C build/stage qvm-remote-dom0-$(VERSION)
	# vm tarball
	mkdir -p build/stage/qvm-remote-$(VERSION)
	cp -a vm/ Makefile version \
	    build/stage/qvm-remote-$(VERSION)/
	sed 's/@VERSION@/$(VERSION)/g' \
	    rpm_spec/qvm-remote-vm.spec \
	    > build/SPECS/qvm-remote-vm.spec
	tar czf build/SOURCES/$(TARBALL_VM) \
	    -C build/stage qvm-remote-$(VERSION)
	# gui-vm tarball
	mkdir -p build/stage/qvm-remote-gui-$(VERSION)
	cp -a gui/ Makefile version \
	    build/stage/qvm-remote-gui-$(VERSION)/
	sed 's/@VERSION@/$(VERSION)/g' \
	    rpm_spec/qvm-remote-gui-vm.spec \
	    > build/SPECS/qvm-remote-gui-vm.spec
	tar czf build/SOURCES/qvm-remote-gui-$(VERSION).tar.gz \
	    -C build/stage qvm-remote-gui-$(VERSION)
	# gui-dom0 tarball
	mkdir -p build/stage/qvm-remote-gui-dom0-$(VERSION)
	cp -a gui/ Makefile version \
	    build/stage/qvm-remote-gui-dom0-$(VERSION)/
	sed 's/@VERSION@/$(VERSION)/g' \
	    rpm_spec/qvm-remote-gui-dom0.spec \
	    > build/SPECS/qvm-remote-gui-dom0.spec
	tar czf build/SOURCES/qvm-remote-gui-dom0-$(VERSION).tar.gz \
	    -C build/stage qvm-remote-gui-dom0-$(VERSION)
	rm -rf build/stage
	@echo ""
	@echo "Source tarballs ready:"
	@echo "  build/SOURCES/$(TARBALL_DOM0)"
	@echo "  build/SOURCES/$(TARBALL_VM)"
	@echo "  build/SOURCES/qvm-remote-gui-$(VERSION).tar.gz"
	@echo "  build/SOURCES/qvm-remote-gui-dom0-$(VERSION).tar.gz"

# ── RPM build ──────────────────────────────────────────────────────

rpm: dist
	mkdir -p build/RPMS build/SRPMS build/BUILD build/BUILDROOT
	@for spec in qvm-remote-dom0 qvm-remote-vm qvm-remote-gui-vm qvm-remote-gui-dom0; do \
	    rpmbuild --define "_topdir $(CURDIR)/build" \
	             --define "_sourcedir $(CURDIR)/build/SOURCES" \
	             --define "_specdir $(CURDIR)/build/SPECS" \
	             --define "_rpmdir $(CURDIR)/build/RPMS" \
	             --define "_srpmdir $(CURDIR)/build/SRPMS" \
	             --define "_builddir $(CURDIR)/build/BUILD" \
	             --define "_buildrootdir $(CURDIR)/build/BUILDROOT" \
	             -ba build/SPECS/$$spec.spec ; \
	done
	@echo ""
	@echo "RPMs built:"
	@find build/RPMS -name '*.rpm' 2>/dev/null
	@find build/SRPMS -name '*.rpm' 2>/dev/null

# ── RPM signing ────────────────────────────────────────────────────

rpm-sign:
	rpm --define '_gpg_name $(GPG_NAME)' \
	    --addsign build/RPMS/noarch/*.rpm build/SRPMS/*.rpm
	@echo ""
	@echo "Signed. Verify with: rpm -K build/RPMS/noarch/*.rpm"

# ── Docker/Podman build ───────────────────────────────────────────

docker-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.test -t qvm-remote-test .
	@echo ""
	@echo "Docker integration tests passed."

dom0-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.dom0-sim -t qvm-remote-dom0-sim .
	@echo ""
	@echo "Dom0 simulation tests passed."

arch-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.arch -t qvm-remote-arch-test .
	@echo ""
	@echo "Arch Linux client tests passed."

gui-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.gui -t qvm-remote-gui-test .
	@echo ""
	@echo "GUI build and import tests passed."

gui-integration-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.gui-integration -t qvm-remote-gui-integration .
	@echo ""
	@echo "GUI Xvfb integration tests passed."

backup-e2e-test:
	$(CONTAINER_ENGINE) build -f test/Dockerfile.backup-e2e -t qvm-remote-backup-e2e .
	@echo ""
	@echo "Backup E2E tests passed."

all-test: check test docker-test dom0-test arch-test gui-test gui-integration-test backup-e2e-test
	@echo ""
	@echo "======================================"
	@echo "  ALL TESTS PASSED (all distros)"
	@echo "======================================"

deb:
	dpkg-buildpackage -us -uc -b
	@echo ""
	@echo "Debian packages built in parent directory."

docker-rpm:
	$(CONTAINER_ENGINE) build -f Dockerfile.build -t qvm-remote-build .
	$(CONTAINER_ENGINE) create --name qr-extract qvm-remote-build 2>/dev/null || \
	    ($(CONTAINER_ENGINE) rm qr-extract && $(CONTAINER_ENGINE) create --name qr-extract qvm-remote-build)
	rm -rf build/RPMS build/SRPMS
	mkdir -p build
	$(CONTAINER_ENGINE) cp qr-extract:/build/build/RPMS build/RPMS
	$(CONTAINER_ENGINE) cp qr-extract:/build/build/SRPMS build/SRPMS
	$(CONTAINER_ENGINE) rm qr-extract
	@echo ""
	@echo "RPMs extracted to build/RPMS/ and build/SRPMS/"
	@find build/RPMS -name '*.rpm' 2>/dev/null
	@find build/SRPMS -name '*.rpm' 2>/dev/null
