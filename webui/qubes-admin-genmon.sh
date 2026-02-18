#!/bin/bash
# qubes-admin-genmon.sh -- XFCE genmon panel plugin for qvm-remote service status
#
# Shows a compact status indicator in the XFCE panel:
#   Green circle = all services healthy
#   Yellow circle = partial (some services down)
#   Red circle = critical (daemon or web down)
#
# Clicking opens the web admin UI or triggers restart.
#
# Install: Configure genmon plugin with command=/usr/local/bin/qubes-admin-genmon.sh
#          Update period: 15 seconds

HEALTH_URL="http://127.0.0.1:9876/api/health"
ADMIN_URL="http://127.0.0.1:9876"

# Single curl + single python3 to parse JSON (2 processes total)
eval "$(curl -sf --max-time 3 "$HEALTH_URL" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k in ('daemon', 'web', 'vm', 'vm_name'):
        v = d.get(k, '?')
        print(f'{k}={v}')
except Exception:
    print('daemon=?\nweb=?\nvm=?\nvm_name=?')
" 2>/dev/null)"

if [ "$web" = "True" ] && [ "$daemon" = "True" ] && [ "$vm" = "True" ]; then
    icon="🟢"
    tooltip="<b>qvm-remote</b>  Daemon: ✓  Web: ✓  VM ($vm_name): ✓"
    click="xdg-open $ADMIN_URL"
elif [ "$web" = "True" ] && [ "$daemon" = "True" ]; then
    icon="🟡"
    tooltip="<b>qvm-remote</b>  Daemon: ✓  Web: ✓  VM ($vm_name): ✗"
    click="xdg-open $ADMIN_URL"
elif [ "$daemon" = "?" ] && [ "$web" = "?" ]; then
    # curl failed -- web server is down
    if systemctl is-active --quiet qvm-remote-dom0 2>/dev/null; then
        icon="🟡"
        tooltip="<b>qvm-remote</b>  Daemon: ✓  Web: ✗ (down)"
        click="sudo systemctl restart qubes-global-admin-web"
    else
        icon="🔴"
        tooltip="<b>qvm-remote</b>  Daemon: ✗  Web: ✗"
        click="sudo systemctl restart qvm-remote-dom0 qubes-global-admin-web"
    fi
else
    icon="🔴"
    tooltip="<b>qvm-remote</b>  Daemon: ✗  Web: ${web}"
    click="sudo systemctl restart qvm-remote-dom0 qubes-global-admin-web"
fi

echo "<txt>$icon</txt>"
echo "<tool>$tooltip</tool>"
echo "<txtclick>$click</txtclick>"
