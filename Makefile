PREFIX    ?= /usr
BINDIR    ?= $(PREFIX)/bin
SYSCONFDIR ?= /etc
UNITDIR   ?= /etc/systemd/system
DESTDIR   ?=

VERSION   := $(shell cat version)
TARBALL_DOM0 = qvm-remote-dom0-$(VERSION).tar.gz
TARBALL_VM   = qvm-remote-$(VERSION).tar.gz

GPG_NAME  ?= qvm-remote
CONTAINER_ENGINE ?= $(shell command -v podman 2>/dev/null || echo docker)

.PHONY: help install-vm install-dom0 uninstall-vm uninstall-dom0 \
        check test clean dist rpm rpm-sign docker-rpm docker-test dom0-test arch-test

help:
	@echo "qvm-remote $(VERSION)"
	@echo ""
	@echo "Install targets:"
	@echo "  install-vm      Install VM-side client (run inside the VM)"
	@echo "  install-dom0    Install dom0-side daemon (run in dom0)"
	@echo "  uninstall-vm    Remove VM-side client"
	@echo "  uninstall-dom0  Remove dom0-side daemon"
	@echo ""
	@echo "Build targets:"
	@echo "  dist            Create source tarballs in build/SOURCES/"
	@echo "  rpm             Build RPMs (requires rpmbuild)"
	@echo "  rpm-sign        Sign built RPMs with GPG key (GPG_NAME=$(GPG_NAME))"
	@echo "  docker-rpm      Build RPMs inside a Fedora 41 container"
	@echo ""
	@echo "Other:"
	@echo "  check           Syntax-check all scripts"
	@echo "  test            Run full test suite"
	@echo "  docker-test     Run RPM install test in Fedora 41 container"
	@echo "  dom0-test       Run full dom0 simulation (daemon E2E) in container"
	@echo "  arch-test       Run client test in Arch Linux container"
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

uninstall-vm:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote

uninstall-dom0:
	rm -f $(DESTDIR)$(BINDIR)/qvm-remote-dom0
	rm -f $(DESTDIR)$(UNITDIR)/qvm-remote-dom0.service

check:
	@python3 -c "import py_compile; py_compile.compile('vm/qvm-remote', doraise=True)" && echo "vm/qvm-remote: ok"
	@python3 -c "import py_compile; py_compile.compile('dom0/qvm-remote-dom0', doraise=True)" && echo "dom0/qvm-remote-dom0: ok"
	@bash -n install/install-dom0.sh && echo "install/install-dom0.sh: ok"

test:
	@python3 test/test_qvm_remote.py -v

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
	rm -rf build/stage
	@echo ""
	@echo "Source tarballs ready:"
	@echo "  build/SOURCES/$(TARBALL_DOM0)"
	@echo "  build/SOURCES/$(TARBALL_VM)"

# ── RPM build ──────────────────────────────────────────────────────

rpm: dist
	mkdir -p build/RPMS build/SRPMS build/BUILD build/BUILDROOT
	rpmbuild --define "_topdir $(CURDIR)/build" \
	         --define "_sourcedir $(CURDIR)/build/SOURCES" \
	         --define "_specdir $(CURDIR)/build/SPECS" \
	         --define "_rpmdir $(CURDIR)/build/RPMS" \
	         --define "_srpmdir $(CURDIR)/build/SRPMS" \
	         --define "_builddir $(CURDIR)/build/BUILD" \
	         --define "_buildrootdir $(CURDIR)/build/BUILDROOT" \
	         -ba build/SPECS/qvm-remote-dom0.spec
	rpmbuild --define "_topdir $(CURDIR)/build" \
	         --define "_sourcedir $(CURDIR)/build/SOURCES" \
	         --define "_specdir $(CURDIR)/build/SPECS" \
	         --define "_rpmdir $(CURDIR)/build/RPMS" \
	         --define "_srpmdir $(CURDIR)/build/SRPMS" \
	         --define "_builddir $(CURDIR)/build/BUILD" \
	         --define "_buildrootdir $(CURDIR)/build/BUILDROOT" \
	         -ba build/SPECS/qvm-remote-vm.spec
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
