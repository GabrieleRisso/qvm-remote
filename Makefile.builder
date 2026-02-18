RPM_SPEC_FILES.dom0 := rpm_spec/qvm-remote-dom0.spec rpm_spec/qvm-remote-gui-dom0.spec
RPM_SPEC_FILES.vm := rpm_spec/qvm-remote-vm.spec rpm_spec/qvm-remote-gui-vm.spec

RPM_SPEC_FILES := $(RPM_SPEC_FILES.$(PACKAGE_SET))
