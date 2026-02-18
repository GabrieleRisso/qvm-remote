RPM_SPEC_FILES.dom0 := rpm_spec/qubes-remote-dom0.spec
RPM_SPEC_FILES.vm := rpm_spec/qubes-remote-vm.spec

RPM_SPEC_FILES := $(RPM_SPEC_FILES.$(PACKAGE_SET))
