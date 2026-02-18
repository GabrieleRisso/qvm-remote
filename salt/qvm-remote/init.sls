# qvm-remote Salt state — deploy hardened AppVM + dom0 daemon.
#
# Pillar values (see pillar/qvm-remote.sls):
#   qvm-remote:vm-name   — AppVM name       (default: dev-remote)
#   qvm-remote:template  — TemplateVM name   (default: system default)
#   qvm-remote:label     — VM label colour   (default: black)
#   qvm-remote:memory    — Initial memory MB (default: 400)
#   qvm-remote:maxmem    — Max memory MB     (default: 1024)

{% set cfg = salt['pillar.get']('qvm-remote', {}) %}
{% set vm_name = cfg.get('vm-name', 'dev-remote') %}
{% set template = cfg.get('template', '') %}
{% set label    = cfg.get('label', 'black') %}
{% set memory   = cfg.get('memory', 400) %}
{% set maxmem   = cfg.get('maxmem', 1024) %}

# ── 1. Create a hardened, networkless AppVM ────────────────────────

{{ vm_name }}-present:
  qvm.present:
    - name: {{ vm_name }}
{% if template %}
    - template: {{ template }}
{% endif %}
    - label: {{ label }}

{{ vm_name }}-prefs:
  qvm.prefs:
    - name: {{ vm_name }}
    - netvm: ''
    - memory: {{ memory }}
    - maxmem: {{ maxmem }}
    - vcpus: 1
    - autostart: false
    - require:
      - qvm: {{ vm_name }}-present

# ── 2. Install qvm-remote client in the VM ────────────────────────

{{ vm_name }}-install-client:
  cmd.run:
    - name: >-
        qvm-run --pass-io --no-gui --no-autostart {{ vm_name }}
        'sudo make -C /usr/share/qvm-remote install-vm 2>&1 || echo "qvm-remote client already installed"'
    - unless: >-
        qvm-run --pass-io --no-gui --no-autostart {{ vm_name }}
        'test -x /usr/bin/qvm-remote'
    - require:
      - qvm: {{ vm_name }}-prefs

# ── 3. Install qvm-remote-dom0 daemon in dom0 ─────────────────────

qvm-remote-dom0-bin:
  file.managed:
    - name: /usr/bin/qvm-remote-dom0
    - source: salt://qvm-remote/files/qvm-remote-dom0
    - mode: '0755'
    - user: root
    - group: root

qvm-remote-dom0-service:
  file.managed:
    - name: /etc/systemd/system/qvm-remote-dom0.service
    - source: salt://qvm-remote/files/qvm-remote-dom0.service
    - mode: '0644'
    - user: root
    - group: root

# ── 4. Configure ──────────────────────────────────────────────────

qvm-remote-conf:
  file.managed:
    - name: /etc/qubes/remote.conf
    - contents: |
        QVM_REMOTE_VMS={{ vm_name }}
    - mode: '0600'
    - user: root
    - group: root
    - makedirs: true
    - replace: false

# ── 5. Reload and start (transient — NOT enabled) ─────────────────

qvm-remote-daemon-reload:
  cmd.run:
    - name: systemctl daemon-reload
    - onchanges:
      - file: qvm-remote-dom0-service

qvm-remote-dom0-running:
  service.running:
    - name: qvm-remote-dom0
    - enable: false
    - require:
      - file: qvm-remote-dom0-bin
      - file: qvm-remote-dom0-service
      - file: qvm-remote-conf
      - cmd: qvm-remote-daemon-reload
