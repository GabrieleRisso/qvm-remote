# qvm-remote Salt Formula

Automated deployment of qvm-remote in dom0.

## Setup (run in dom0)

Copy all Salt files from the VM to dom0:

```bash
VM=dev-vm  # the VM where qvm-remote source is available

# Salt state
mkdir -p /srv/salt/qvm-remote/files
qvm-run --pass-io --no-gui $VM 'cat /path/to/qvm-remote/salt/qvm-remote/init.sls' \
    > /srv/salt/qvm-remote/init.sls

# Dom0 binary and service file (served by Salt file server)
qvm-run --pass-io --no-gui $VM 'cat /usr/bin/qvm-remote-dom0' \
    > /srv/salt/qvm-remote/files/qvm-remote-dom0
qvm-run --pass-io --no-gui $VM 'cat /path/to/qvm-remote/dom0/qvm-remote-dom0.service' \
    > /srv/salt/qvm-remote/files/qvm-remote-dom0.service

# Top file
qvm-run --pass-io --no-gui $VM 'cat /path/to/qvm-remote/salt/qvm-remote.top' \
    > /srv/salt/qvm-remote.top

# Pillar
mkdir -p /srv/pillar/base
qvm-run --pass-io --no-gui $VM 'cat /path/to/qvm-remote/salt/pillar/qvm-remote.sls' \
    > /srv/pillar/base/qvm-remote.sls
```

Edit the pillar to set your VM name:

```bash
vi /srv/pillar/base/qvm-remote.sls
```

## Apply

```bash
qubesctl top.enable qvm-remote
qubesctl state.apply qvm-remote
```

## What it does

1. Creates a hardened, networkless AppVM (configurable name, default: `dev-remote`)
2. Installs `qvm-remote-dom0` daemon and systemd service in dom0
3. Writes `/etc/qubes/remote.conf` with the VM name
4. Starts the service (transient -- stops on reboot, never enabled)
