-- ┌──────────────────────────────────────────────────────────────────┐
-- │ dom0 - Devilspie2 - Window Placement                           │
-- │                                                                  │
-- │ Screen: 3440×1440 ultrawide (DP-1), XFCE panel 22px bottom     │
-- │                                                                  │
-- │ Qubes window titles:                                             │
-- │   VM windows:  "[vm-name] Window Title"                          │
-- │   dom0 windows: "dom0 Window Title" or just "Window Title"      │
-- │                                                                  │
-- │ Workspace layout (0-indexed for devilspie2):                    │
-- │   0 Admin: Web Admin, Global Config, Qube Manager, Settings     │
-- │   1 Code:  Cursor editors, Thunar, Lain terminal                │
-- │   2 Comms: Chrome, WhatsApp, browsers                           │
-- │   3 Media: Spotify, Bluetooth, audio, display                   │
-- │   4 Ops:   Terminals, VPN, qvm-remote, system tools             │
-- └──────────────────────────────────────────────────────────────────┘

local W = 3440
local H = 1440
local PANEL = 22
local UH = H - PANEL   -- usable height

local title = get_window_name() or ""
local cls   = get_class_instance_name() or ""

-- Skip desktop, panel, notifications, popups
if string.find(title, "Desktop") or
   string.find(title, "xfce4%-panel") or
   string.find(title, "xfce4%-notifyd") or
   string.find(title, "Whisker Menu") then
    return
end

-- ── Placement helpers ─────────────────────────────────────────────

local function place(ws, x, y, w, h)
    set_window_workspace(ws)
    set_window_geometry2(x, y, w, h)
end

local function left(ws)       place(ws, 0, 0, W/2, UH) end
local function right(ws)      place(ws, W/2, 0, W/2, UH) end
local function full(ws)       place(ws, 0, 0, W, UH) end
local function topright(ws)   place(ws, W/2, 0, W/2, UH/2) end
local function botright(ws)   place(ws, W/2, UH/2, W/2, UH/2) end
local function left23(ws)     place(ws, 0, 0, math.floor(W*2/3), UH) end
local function right13(ws)    place(ws, math.floor(W*2/3), 0, math.floor(W/3), UH) end
local function right13top(ws) place(ws, math.floor(W*2/3), 0, math.floor(W/3), UH/2) end
local function right13bot(ws) place(ws, math.floor(W*2/3), UH/2, math.floor(W/3), UH/2) end

-- ═══════════════════════════════════════════════════════════════════
-- WS0: Admin — Web Admin (left), Global Config (top-right),
--              Qube Manager (bottom-right)
-- ═══════════════════════════════════════════════════════════════════

-- dom0 - Web Admin - Firefox
if string.find(title, "Qubes Global Admin") and string.find(title, "Firefox") then
    left(0); return
end

-- dom0 - Global Config
if string.find(title, "Qubes OS Global Config") then
    topright(0); return
end

-- dom0 - Qube Manager
if string.find(title, "Qube Manager") then
    botright(0); return
end

-- dom0 - Settings (VM settings windows)
if string.find(title, "Settings:") then
    place(0, W/2+80, 80, 900, 700); return
end

-- dom0 - VM Selector (zenity from autostart)
if string.find(title, "VM Selector") then
    place(0, W/2-250, UH/2-250, 500, 500); return
end

-- dom0 - Thunar (local home folder) -- matches "<user> - Thunar"
if string.find(title, "Thunar") and not string.find(title, "%]") then
    botright(0); return
end

-- ═══════════════════════════════════════════════════════════════════
-- WS1: Code — Cursor, Lain, dev Thunar
-- ═══════════════════════════════════════════════════════════════════

if string.find(title, "Cursor$") or string.find(title, "- Cursor") then
    if string.find(title, "qubes%-claw") or string.find(title, "Browser Tab") then
        left23(1); return
    end
    if string.find(title, "- fix -") or string.find(title, "recovery") then
        left23(1); return
    end
    full(1); return
end

-- Lain terminal in code workspace
if string.find(title, "Lain") then
    right13(1); return
end

-- VM Thunar (prefixed with [vmname]) in code workspace
if string.find(title, "Thunar") and string.find(title, "%]") then
    right13(1); return
end

-- ═══════════════════════════════════════════════════════════════════
-- WS2: Comms — Chrome left, WhatsApp right
-- ═══════════════════════════════════════════════════════════════════

if string.find(title, "Google Chrome") then
    if string.find(title, "WhatsApp") or string.find(title, "whatsapp") then
        right(2); return
    end
    left(2); return
end

if string.find(title, "WhatsApp") then
    right(2); return
end

-- ═══════════════════════════════════════════════════════════════════
-- WS3: Media — Spotify left 2/3, Bluetooth + audio right 1/3
-- ═══════════════════════════════════════════════════════════════════

if string.find(title, "Spotify") or (string.find(cls, "spotify") or false) then
    left23(3); return
end

-- Music player (matches Maribou State, Elderbrook, etc.)
if string.find(cls, "rhythmbox") or string.find(cls, "vlc") or
   string.find(cls, "mpv") then
    left23(3); return
end

if string.find(title, "Bluetooth") or string.find(title, "JBL") or
   string.find(title, "blueman") then
    right13top(3); return
end

if string.find(title, "Display") and not string.find(title, "Cursor") then
    right13bot(3); return
end

-- ═══════════════════════════════════════════════════════════════════
-- WS4: Ops — Terminals, VPN, qvm-remote
-- ═══════════════════════════════════════════════════════════════════

if string.find(title, "qvm%-remote") then
    left(4); return
end

if string.find(title, "Terminal") or string.find(cls, "xfce4%-terminal") then
    if string.find(title, "sys%-vpn") then
        right(4); return
    end
    left(4); return
end

if string.find(title, "Proton VPN") or string.find(title, "protonvpn") then
    right(4); return
end
