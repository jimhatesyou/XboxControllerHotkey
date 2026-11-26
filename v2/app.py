"""
XboxControllerHotkey V2
Minimal Windows system-tray controller monitor and Xbox Game Bar hotkey utility.

Requires Windows 10/11, Python 3.10+, PySide6, and pygame.
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
import threading
import re
import json
import hashlib
import subprocess
import tempfile
import shutil
import base64
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QSize, QThread, Signal, QUrl, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QBrush, QPixmap, QPainterPath, QRegion, QDesktopServices, QMovie, QLinearGradient
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QGraphicsOpacityEffect,
    QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget, QTabWidget, QStackedWidget, QMessageBox, QScrollArea, QListWidget, QCheckBox
)

# The app lives in the tray while games own foreground focus. SDL disables
# background joystick updates by default unless this is set before SDL init.
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

try:
    import pygame
    # SDL's GameController layer distinguishes mapped gamepads from generic
    # HID/joystick interfaces (some keyboards expose these).
    from pygame._sdl2 import controller as sdl_controller
except ImportError:
    pygame = None
    sdl_controller = None

try:
    # Optional Python/WinRT projection. When available, Windows Gaming Input
    # can expose remaining/full capacity for a connected gamepad.
    from winsdk.windows.gaming.input import Gamepad as WinRTGamepad
except Exception:
    WinRTGamepad = None


APP_NAME = "XboxControllerHotkey"
APP_VERSION = "2.0.20"
ACCESSORIES_AUMID = r"Microsoft.XboxDevices_8wekyb3d8bbwe!App"
ACCESSORIES_STORE_URI = "ms-windows-store://pdp/?productid=9NBLGGH30XJ3"
CAPTURE_SETTINGS_URI = "ms-settings:gaming-gamedvr"

# pygame's common XInput mapping for Xbox controllers:
# 6 = View/Back, 7 = Menu/Start. These are kept as constants so they
# can be adjusted if a controller/driver exposes a different mapping.
BACK_BUTTON = 6
START_BUTTON = 7
GAME_BAR_RECORD_THAT = True
GITHUB_RELEASES_API = "https://api.github.com/repos/jimhatesyou/XboxControllerHotkey/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/jimhatesyou/XboxControllerHotkey/releases"
GITHUB_REPO = "https://github.com/jimhatesyou/XboxControllerHotkey"
DEFAULT_SHORTCUT = [6, 7]
BUTTON_NAMES = {0:"A", 1:"B", 2:"X", 3:"Y",
                4:"LB", 5:"RB", 6:"Back",
                7:"Start", 8:"Left Stick", 9:"Right Stick", 10:"Guide"}




# XInput is read-only/shared with games and does not depend on SDL window focus.
# This is the preferred input path for Xbox controllers, including the Xbox
# Wireless Adapter. SDL/Pygame remains the fallback for other mapped gamepads.
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


XINPUT_BUTTON_MAP = {
    0x1000: "button:0",   # A
    0x2000: "button:1",   # B
    0x4000: "button:2",   # X
    0x8000: "button:3",   # Y
    0x0100: "button:4",   # LB
    0x0200: "button:5",   # RB
    0x0020: "button:6",   # Back / View
    0x0010: "button:7",   # Start / Menu
    0x0040: "button:8",   # Left stick click
    0x0080: "button:9",   # Right stick click
}

XINPUT_DPAD_MAP = {
    0x0001: "hat:0:up",
    0x0002: "hat:0:down",
    0x0004: "hat:0:left",
    0x0008: "hat:0:right",
}

def xinput_flags_to_controls(flags: int):
    """Translate XInput digital button flags into the app's configurable control IDs."""
    pressed = {
        control for mask, control in XINPUT_BUTTON_MAP.items()
        if flags & mask
    }
    pressed.update(
        control for mask, control in XINPUT_DPAD_MAP.items()
        if flags & mask
    )
    return pressed

@dataclass
class ControllerInfo:
    name: str
    instance_id: int
    guid: str = ""
    connection: str = "Connection type unavailable"
    battery: str = "Battery unavailable"
    battery_detail: str = ""


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def paint_custom_background(widget, asset_name: str, radius: int = 16, overlay_alpha: int = 105):
    """Paint a cover-scaled background image inside a genuinely rounded surface."""
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    rect = widget.rect()
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    painter.setClipPath(path)
    pix = QPixmap(resource_path(os.path.join("assets", asset_name)))
    if not pix.isNull():
        scaled = pix.scaled(
            rect.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        x = (scaled.width() - rect.width()) // 2
        y = (scaled.height() - rect.height()) // 2
        painter.drawPixmap(0, 0, scaled, x, y, rect.width(), rect.height())
    else:
        painter.fillPath(path, QColor("#111318"))
    painter.fillPath(path, QColor(0, 0, 0, overlay_alpha))
    painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.end()


def rounded_widget_mask(widget, radius: int):
    path = QPainterPath()
    path.addRoundedRect(widget.rect(), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def make_tray_icon(connected: bool) -> QIcon:
    """
    Use the supplied white controller silhouette as the app/tray identity.
    A compact status badge sits in the upper-right corner:
      green circle + check = controller connected
      red circle + X = no supported controller detected
    """
    from PySide6.QtGui import QPolygon
    from PySide6.QtCore import QPoint

    canvas = QPixmap(64, 64)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    image = QPixmap(resource_path(os.path.join("assets", "controller-icon.png")))
    if not image.isNull():
        # Fit the wide controller silhouette into the tray icon while preserving
        # transparent padding around its outline.
        fitted = image.scaled(
            QSize(54, 54),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap((64 - fitted.width()) // 2, (64 - fitted.height()) // 2 + 3, fitted)

    # Status badge overlays the controller's top-right free area.
    badge_color = QColor("#27B765") if connected else QColor("#E04444")
    painter.setPen(QPen(QColor("#171A20"), 2))
    painter.setBrush(QBrush(badge_color))
    painter.drawEllipse(QRect(43, 1, 20, 20))

    painter.setPen(QPen(QColor("#FFFFFF"), 2.5, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if connected:
        # Check mark
        painter.drawLine(48, 11, 52, 14)
        painter.drawLine(52, 14, 58, 7)
    else:
        # X mark for disconnected / not detected
        painter.drawLine(49, 7, 57, 15)
        painter.drawLine(57, 7, 49, 15)

    painter.end()
    return QIcon(canvas)


def send_game_bar_record_that() -> None:
    """Send Win+Alt+G using the same pynput path as the working V1.25 release."""
    if os.name != "nt":
        return

    try:
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        # Press modifiers first, then the trigger; release in reverse order.
        keyboard.press(Key.cmd)
        keyboard.press(Key.alt)
        keyboard.press("g")
        keyboard.release("g")
        keyboard.release(Key.alt)
        keyboard.release(Key.cmd)
        return
    except Exception:
        # Keep a native fallback so a missing/broken pynput import does not
        # silently disable capture. The primary supported build installs pynput.
        pass

    user32 = ctypes.windll.user32
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_LWIN, VK_MENU, VK_G = 0x5B, 0x12, 0x47

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

    def key(vk: int, up: bool = False):
        extra = ctypes.c_ulong(0)
        return INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(
            vk, 0, KEYEVENTF_KEYUP if up else 0, 0, ctypes.pointer(extra)
        )))

    sequence = [key(VK_LWIN), key(VK_MENU), key(VK_G),
                key(VK_G, True), key(VK_MENU, True), key(VK_LWIN, True)]
    arr = (INPUT * len(sequence))(*sequence)
    user32.SendInput(len(sequence), ctypes.byref(arr), ctypes.sizeof(INPUT))


def get_xinput_battery() -> str:
    """
    XInput reports a coarse battery state (empty/low/medium/full), not a
    reliable percentage. Some Bluetooth/third-party drivers expose no data.
    """
    if os.name != "nt":
        return "Battery unavailable"
    class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
        _fields_ = [("BatteryType", ctypes.c_ubyte), ("BatteryLevel", ctypes.c_ubyte)]

    battery_types = {0: "Disconnected", 1: "Wired", 2: "Alkaline", 3: "NiMH"}
    levels = {0: "Empty", 1: "Low", 2: "Medium", 3: "Full"}
    for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(dll_name)
            fn = dll.XInputGetBatteryInformation
            fn.argtypes = [ctypes.c_uint, ctypes.c_ubyte, ctypes.POINTER(XINPUT_BATTERY_INFORMATION)]
            fn.restype = ctypes.c_uint
            for user_index in range(4):
                info = XINPUT_BATTERY_INFORMATION()
                # BATTERY_DEVTYPE_GAMEPAD = 0
                if fn(user_index, 0, ctypes.byref(info)) == 0:
                    if info.BatteryType == 0:
                        continue
                    if info.BatteryType == 1:
                        return "Wired power"
                    level = levels.get(info.BatteryLevel, "Unknown")
                    return level
        except (OSError, AttributeError):
            continue
    return "Battery unavailable"


def _read_attr(obj, *names):
    for name in names:
        try:
            value = getattr(obj, name)
            if value is not None:
                return value
        except Exception:
            pass
    return None


def get_precise_gamepad_battery(active_guid: str = "") -> Optional[str]:
    """Use a WinRT battery report only when its raw controller VID/PID matches SDL."""
    if WinRTGamepad is None:
        return None
    wanted = _guid_vid_pid(active_guid)
    if not wanted:
        return None
    try:
        matching_reports = []
        for gamepad in list(WinRTGamepad.gamepads):
            raw = _read_attr(gamepad, "raw_game_controller", "RawGameController")
            if raw is None:
                continue
            vendor = _read_attr(raw, "hardware_vendor_id", "HardwareVendorId")
            product = _read_attr(raw, "hardware_product_id", "HardwareProductId")
            if vendor is None or product is None:
                continue
            if (int(vendor), int(product)) != wanted:
                continue
            report = gamepad.try_get_battery_report()
            if report is None:
                continue
            remaining = _read_attr(report, "remaining_capacity_in_milliwatt_hours", "RemainingCapacityInMilliwattHours")
            full = _read_attr(report, "full_charge_capacity_in_milliwatt_hours", "FullChargeCapacityInMilliwattHours")
            if remaining is None or full is None or int(full) <= 0:
                continue
            matching_reports.append((float(remaining), float(full)))
        # VID/PID identifies a model, not a unique physical controller. If
        # multiple identical controllers are present, do not guess which report
        # belongs to the active SDL instance.
        if len(matching_reports) != 1:
            return None
        remaining, full = matching_reports[0]
        percent = round(max(0, min(100, (remaining / full) * 100)))
        return f"{percent}%"
    except Exception:
        return None


def get_controller_battery(active_guid: str = "") -> str:
    precise = get_precise_gamepad_battery(active_guid)
    if precise is not None:
        return precise
    # XInput exposes only Empty/Low/Medium/Full, not a numeric percentage.
    return get_xinput_battery()


def _guid_vid_pid(guid: str):
    """Extract VID/PID from SDL's standard 32-hex-character joystick GUID."""
    value = re.sub(r"[^0-9a-fA-F]", "", str(guid or ""))
    if len(value) != 32:
        return None
    try:
        # SDL encodes the USB vendor/product bytes little-endian in the GUID.
        vid = int.from_bytes(bytes.fromhex(value[8:12]), "little")
        pid = int.from_bytes(bytes.fromhex(value[12:16]), "little")
        if not vid or not pid:
            return None
        return vid, pid
    except Exception:
        return None


_PNP_CACHE = {"time": 0.0, "devices": []}
_PNP_CACHE_LOCK = threading.Lock()

def _windows_pnp_devices():
    """Read present Xbox PnP nodes and their parent chains from Windows."""
    if os.name != "nt":
        return []
    now = time.monotonic()
    with _PNP_CACHE_LOCK:
        if now - _PNP_CACHE["time"] < 3.0:
            return _PNP_CACHE["devices"]
        ps = r"""$ErrorActionPreference='SilentlyContinue'
$all = Get-PnpDevice -PresentOnly
$map = @{}
foreach ($d in $all) {
  if ($d.InstanceId -match 'VID_045E|VID&02045E|^BTHLE\\DEV_|^BTHLEDEVICE\\') {
    $parent = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data
    $enum = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_EnumeratorName' -ErrorAction SilentlyContinue).Data
    $hw = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
    $map[$d.InstanceId] = [pscustomobject]@{ id=$d.InstanceId; name=$d.FriendlyName; class=$d.Class; parent=$parent; enum=$enum; hw=@($hw) }
  }
}
$out = @()
foreach ($d in $map.Values) {
  $chain = @(); $next = $d.id; $seen = @{}
  for ($i=0; $i -lt 12 -and $next -and -not $seen.ContainsKey($next); $i++) {
    $seen[$next]=$true; $chain += $next
    if ($map.ContainsKey($next)) { $next=$map[$next].parent }
    else { $next=(Get-PnpDeviceProperty -InstanceId $next -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data }
  }
  $out += [pscustomobject]@{ id=$d.id; name=$d.name; class=$d.class; enum=$d.enum; hw=$d.hw; chain=$chain }
}
ConvertTo-Json -InputObject @($out) -Depth 5 -Compress"""
        encoded = __import__('base64').b64encode(ps.encode('utf-16le')).decode('ascii')
        try:
            proc = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded], capture_output=True, text=True, timeout=6.0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            data = json.loads(proc.stdout.strip() or "[]") if proc.returncode == 0 else []
            if isinstance(data, dict): data = [data]
            _PNP_CACHE["devices"] = data if isinstance(data, list) else []
            _PNP_CACHE["time"] = now
        except Exception:
            # Keep a short negative cache to avoid spawning PowerShell every poll.
            _PNP_CACHE["devices"] = []
            _PNP_CACHE["time"] = now
        return _PNP_CACHE["devices"]


def _windows_pnp_transport(guid: str, name: str = "") -> str:
    """Match the active SDL controller VID/PID to its Windows gamepad node, then walk parents."""
    devices = _windows_pnp_devices()
    if not devices:
        return "Connection type unavailable"
    wanted = _guid_vid_pid(guid)
    if not wanted:
        return "Connection type unavailable"

    vid, pid = wanted
    pid_tokens = (f"PID_{pid:04X}", f"PID&{pid:04X}")
    candidates = []
    for item in devices:
        iid = str(item.get("id", "")).upper()
        chain = [str(x).upper() for x in item.get("chain", [])]
        evidence = " ".join(
            [iid, str(item.get("name", ""))] +
            [str(x) for x in (item.get("hw", []) or [])]
        ).upper()
        if str(item.get("class", "")).lower() == "keyboard":
            continue
        # The Windows Bluetooth HID spelling is VID&02045E_PID&0B22;
        # USB/XInput nodes commonly use VID_045E&PID_02FF or PID_0B00.
        if f"VID_{vid:04X}" not in evidence and f"VID&02{vid:04X}" not in evidence and f"VID&{vid:04X}" not in evidence:
            continue
        if not any(token in evidence for token in pid_tokens):
            continue
        is_gamepad = (
            "UP:0001_U:0005" in evidence or
            "PID_02FF" in evidence or
            "PID&02FF" in evidence or
            "GAMEPAD" in str(item.get("name", "")).upper() or
            "CONTROLLER" in str(item.get("name", "")).upper()
        )
        if not is_gamepad:
            continue
        candidates.append((item, chain))

    # Some SDL backends expose the controller's XInput child PID rather than
    # the composite controller PID. In that case use the unique present Xbox
    # gamepad interface only; never select unrelated audio/keyboard nodes.
    if not candidates:
        for item in devices:
            iid = str(item.get("id", "")).upper()
            chain = [str(x).upper() for x in item.get("chain", [])]
            evidence = " ".join([iid] + [str(x) for x in (item.get("hw", []) or [])]).upper()
            if str(item.get("class", "")).lower() == "keyboard":
                continue
            if "VID_045E" not in evidence:
                continue
            if "UP:0001_U:0005" in evidence:
                candidates.append((item, chain))

    transports = set()
    for item, chain in candidates:
        full_chain = [str(x).upper() for x in chain]
        if any(x.startswith("USB\\VID_045E&PID_02FE") or x.startswith("USB\\VID_045E&PID_02E6") for x in full_chain):
            transports.add("Xbox Wireless Adapter")
        elif any(x.startswith("BTHLE\\") or x.startswith("BTHLEDEVICE\\") or x.startswith("BTHENUM\\") for x in full_chain):
            transports.add("Bluetooth")
        elif any(x.startswith("USB\\VID_045E&PID_0B00") or x.startswith("USB\\VID_045E&PID_0B22") for x in full_chain):
            transports.add("USB")
        elif str(item.get("enum", "")).upper() == "USB":
            transports.add("USB")

    if len(transports) == 1:
        return next(iter(transports))
    return "Connection type unavailable"


def get_connection_type(name: str, guid: str = "") -> str:
    """Report the active transport using Windows PnP ancestry, not setup preference."""
    return _windows_pnp_transport(guid, name)


class ControllerMonitor:
    def __init__(self):
        self._state_lock = threading.RLock()
        self.joysticks = []
        self.available_devices = []
        self.active: Optional[ControllerInfo] = None
        self.selected_instance_id = None
        self.selected_guid = ""  # GUID of the currently active controller
        self.preferred_guid = ""  # saved model/device preference; never overwritten by fallback
        self._last_seen_by_guid = {}
        self._present_guids = set()
        self.last_hotkey = False
        self.last_pressed_controls = set()
        self.shortcut_controls = [f"button:{b}" for b in DEFAULT_SHORTCUT]
        self.capture_mode = False
        self.last_refresh = 0.0
        self._pygame_ready = False
        self._controller_api_ready = False
        self._xinput_dll = None
        self._xinput_get_state = None
        self._load_xinput()
        if pygame is not None:
            try:
                pygame.init()
                pygame.joystick.init()
                if sdl_controller is not None:
                    sdl_controller.init()
                    self._controller_api_ready = True
                self._pygame_ready = True
            except Exception:
                self._pygame_ready = False
                self._controller_api_ready = False

    def _load_xinput(self):
        """Load the Windows XInput API once; it is safe to poll while a game is focused."""
        if os.name != "nt":
            return
        for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                dll = ctypes.WinDLL(dll_name)
                fn = dll.XInputGetState
                fn.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
                fn.restype = wintypes.DWORD
                self._xinput_dll = dll
                self._xinput_get_state = fn
                return
            except Exception:
                continue

    def xinput_pressed_controls(self):
        """
        Return XInput controls for the first connected XInput pad.
        None means no XInput controller is connected; an empty set means one
        is connected but no digital controls are currently pressed.
        """
        if self._xinput_get_state is None:
            return None
        for user_index in range(4):
            state = XINPUT_STATE()
            result = self._xinput_get_state(user_index, ctypes.byref(state))
            if result != 0:
                continue
            flags = int(state.Gamepad.wButtons)
            return xinput_flags_to_controls(flags)
        return None

    def xinput_activity_level(self):
        """Normalized XInput activity from buttons, triggers and thumbsticks."""
        if self._xinput_get_state is None: return 0.0
        for user_index in range(4):
            state=XINPUT_STATE()
            if self._xinput_get_state(user_index,ctypes.byref(state))!=0: continue
            pad=state.Gamepad
            axes=[abs(int(pad.sThumbLX))/32767.0,abs(int(pad.sThumbLY))/32767.0,
                  abs(int(pad.sThumbRX))/32767.0,abs(int(pad.sThumbRY))/32767.0]
            triggers=[int(pad.bLeftTrigger)/255.0,int(pad.bRightTrigger)/255.0]
            values=[max(0.0,(v-0.12)/0.88) for v in axes]
            values.extend(max(0.0,(v-0.03)/0.97) for v in triggers)
            if int(pad.wButtons): values.append(0.72)
            return max(values)
        return 0.0

    def refresh(self) -> Optional[ControllerInfo]:
        # SDL enumeration can occasionally take noticeable time. The caller
        # runs this method on a dedicated worker; this lock keeps fallback
        # joystick reads from racing the device-list replacement.
        with self._state_lock:
            return self._refresh_unlocked()

    def _refresh_unlocked(self) -> Optional[ControllerInfo]:
        if not self._pygame_ready:
            self.active = None
            return None
        try:
            # Pump SDL so hot-plug and background controller state stays current.
            # Do NOT quit/reinitialize joystick here: that invalidates every open
            # Joystick object and can interrupt the independent hotkey poller.
            pygame.event.pump()
            if self._controller_api_ready:
                # Only accept devices SDL recognizes as actual game controllers.
                # This excludes generic HID interfaces such as keyboard extras.
                controller_indices = [
                    index for index in range(pygame.joystick.get_count())
                    if sdl_controller.is_controller(index)
                ]
            else:
                # Fail closed: without SDL GameController classification, do not
                # treat arbitrary joystick/HID devices as game controllers.
                controller_indices = []

            if not controller_indices:
                self._present_guids.clear()
                self.active = None
                self.joysticks = []
                self.available_devices = []
                self.selected_instance_id = None
                return None

            devices = []
            for index in controller_indices:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                devices.append(joystick)

            self.joysticks = devices
            self.available_devices = []
            for joystick in devices:
                name = joystick.get_name() or "Game Controller"
                instance_id = joystick.get_instance_id()
                guid = joystick.get_guid() if hasattr(joystick, "get_guid") else ""
                self.available_devices.append(ControllerInfo(
                    name=name,
                    instance_id=instance_id,
                    guid=guid,
                    # Connection transport is intentionally not displayed in
                    # the current UI. Do not run the Windows PnP/PowerShell
                    # resolver during controller refresh: it can block the Qt
                    # UI thread for several seconds. Keep the field at its
                    # neutral default until transport detection is moved to a
                    # dedicated background worker.
                    battery="Battery pending",
                ))

            now = time.monotonic()
            current_guids = {item.guid or f"instance:{item.instance_id}" for item in self.available_devices}
            # Refresh the recency timestamp only on a newly observed connection.
            for item in self.available_devices:
                key = item.guid or f"instance:{item.instance_id}"
                if key not in self._present_guids:
                    self._last_seen_by_guid[key] = now
            self._present_guids = current_guids

            # Saved controller is a priority, not a hard lock. If it is absent,
            # automatically fall back to whichever supported controller most
            # recently appeared. Its priority returns when it reconnects.
            preferred_index = next(
                (i for i, item in enumerate(self.available_devices)
                 if self.preferred_guid and item.guid == self.preferred_guid),
                None,
            )
            if preferred_index is not None:
                chosen_index = preferred_index
            else:
                chosen_index = max(
                    range(len(self.available_devices)),
                    key=lambda i: self._last_seen_by_guid.get(
                        self.available_devices[i].guid or f"instance:{self.available_devices[i].instance_id}", 0
                    ),
                )

            chosen = self.available_devices[chosen_index]
            self.selected_instance_id = chosen.instance_id
            self.selected_guid = chosen.guid
            self.active = ControllerInfo(
                name=chosen.name,
                instance_id=chosen.instance_id,
                guid=chosen.guid,
                connection=chosen.connection,
                battery=chosen.battery,
            )
            return self.active
        except Exception:
            self.active = None
            self.joysticks = []
            return None

    def refresh_battery(self) -> str:
        if self.active is None:
            return "Unavailable"
        battery = get_controller_battery(self.active.guid)
        self.active.battery = battery
        for item in self.available_devices:
            if item.instance_id == self.active.instance_id:
                item.battery = battery
                break
        return battery

    def select_device(self, instance_id: int):
        self.selected_instance_id = instance_id
        selected = next(
            (item for item in self.available_devices if item.instance_id == instance_id),
            None
        )
        if selected:
            self.selected_guid = selected.guid
            self.preferred_guid = selected.guid
            self.active = ControllerInfo(
                name=selected.name,
                instance_id=selected.instance_id,
                guid=selected.guid,
                connection=selected.connection,
                battery=selected.battery,
            )

    def pressed_controls(self):
        """Read digital controls, preferring focus-independent Windows XInput."""
        xinput_controls = self.xinput_pressed_controls()
        if xinput_controls is not None:
            self.last_pressed_controls = xinput_controls
            return xinput_controls
        with self._state_lock:
            if not self._pygame_ready or not self.joysticks:
                self.last_pressed_controls = set()
                return set()
            try:
                pygame.event.pump()
                joystick = self.joysticks[0]
                if not joystick.get_init():
                    return set()
                pressed = {
                    f"button:{i}" for i in range(joystick.get_numbuttons())
                    if joystick.get_button(i)
                }
                # D-pads are commonly exposed as SDL hats, not joystick buttons.
                for hat_index in range(joystick.get_numhats()):
                    x, y = joystick.get_hat(hat_index)
                    if x < 0: pressed.add(f"hat:{hat_index}:left")
                    if x > 0: pressed.add(f"hat:{hat_index}:right")
                    if y > 0: pressed.add(f"hat:{hat_index}:up")
                    if y < 0: pressed.add(f"hat:{hat_index}:down")
                self.last_pressed_controls = pressed
                return pressed
            except Exception:
                self.last_pressed_controls = set()
                return set()

    def pressed_buttons(self):
        # Backwards-compatible internal alias.
        return self.pressed_controls()

    def poll_hotkey(self) -> bool:
        """Trigger once when every configured control is held simultaneously."""
        if self.capture_mode:
            self.last_hotkey = False
            return False
        pressed = self.pressed_controls()
        combo = len(self.shortcut_controls) >= 2 and all(
            control in pressed for control in self.shortcut_controls
        )
        triggered = bool(combo and not self.last_hotkey)
        self.last_hotkey = combo
        return triggered

    def close(self):
        if pygame is not None:
            try:
                pygame.quit()
            except Exception:
                pass



class ControllerScanWorker(QThread):
    """Run SDL device enumeration away from Qt's UI thread."""
    scan_finished = Signal(object)

    def __init__(self, monitor, parent=None):
        super().__init__(parent)
        self.monitor = monitor

    def run(self):
        try:
            info = self.monitor.refresh()
        except Exception:
            info = None
        self.scan_finished.emit(info)


class FirstLaunchNotice(QDialog):
    """Required first-launch explanation with a five-second skip countdown."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.seconds_remaining = 10
        self.setWindowTitle(APP_NAME + " — Important information")
        self.setFixedWidth(500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QDialog { background:transparent; color:#F2F4F7; }
            QLabel { color:#F2F4F7; background:transparent; }
            QLabel#heading { font-size:18px; font-weight:700; }
            QLabel#muted { color:#A7AFBB; font-size:11px; }
            QFrame#notice { background:rgba(20,24,30,220); border:1px solid rgba(130,140,155,65); border-radius:10px; }
            QPushButton { background:#00D451; color:white; border:0; border-radius:9px; padding:11px; font-weight:650; }
            QPushButton:disabled { background:#343B46; color:#9BA3AF; }
            QPushButton#settings { background:#292F39; color:#E5EAF1; }
            QPushButton#link { background:transparent; color:#76B7FF; padding:2px; text-align:left; font-weight:500; }
        """)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(18,18,18,24)
        outer.setSpacing(12)

        heading=QLabel("Before you get started")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        card=QFrame()
        card.setObjectName("notice")
        content=QVBoxLayout(card)
        content.setContentsMargins(15,14,15,14)
        content.setSpacing(10)

        important=QLabel("XboxControllerHotkey is not a standalone clipping app.")
        important.setStyleSheet("font-size:14px;font-weight:700;color:#FFFFFF;")
        important.setWordWrap(False)
        content.addWidget(important)

        explanation=QLabel(
            "<ul style='margin:0;padding-left:18px;'>"
            "<li>It does not record, encode or store video clips itself.</li>"
            "<li>It adds a controller-button shortcut that triggers your existing "
            "Xbox Game Bar &ldquo;RECORD THAT&rdquo; feature in Windows.</li>"
            "<li>Xbox Game Bar and its capture feature must already be installed, "
            "enabled and configured on your PC.</li>"
            "<li>Your capture length, audio, video quality and save location are "
            "controlled by your Windows settings.</li>"
            "</ul>"
        )
        explanation.setTextFormat(Qt.TextFormat.RichText)
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "font-size:12px;line-height:145%;color:#DCE2EA;"
        )
        content.addWidget(explanation)

        settings_link=QPushButton("Open XBOX DVR Capture Settings  ↗")
        settings_link.setObjectName("link")
        settings_link.clicked.connect(open_capture_settings)
        content.addWidget(settings_link)
        outer.addWidget(card)

        foot=QLabel(
            "You can return to capture settings at any time from the main app panel."
        )
        foot.setObjectName("muted")
        foot.setWordWrap(True)
        outer.addWidget(foot)

        self.continue_button=QPushButton("Continue  (10)")
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.accept)
        outer.addWidget(self.continue_button)

        self.countdown=QTimer(self)
        self.countdown.setInterval(1000)
        self.countdown.timeout.connect(self._tick)
        self.countdown.start()

    def paintEvent(self,event):
        paint_custom_background(self,"setup-background.png",radius=16,overlay_alpha=118)
        super().paintEvent(event)

    def resizeEvent(self,event):
        rounded_widget_mask(self,16)
        super().resizeEvent(event)

    def reject(self):
        # The notice cannot be dismissed before its countdown completes.
        if self.seconds_remaining <= 0:
            super().reject()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _tick(self):
        self.seconds_remaining -= 1
        if self.seconds_remaining > 0:
            self.continue_button.setText(f"Continue  ({self.seconds_remaining})")
        else:
            self.countdown.stop()
            self.continue_button.setEnabled(True)
            self.continue_button.setText("Continue")


def open_capture_settings():
    """Open Windows Settings directly to Gaming > Captures (Game DVR)."""
    try:
        return QDesktopServices.openUrl(QUrl(CAPTURE_SETTINGS_URI))
    except Exception:
        return False


class FirstRunSetup(QDialog):
    """First-run connection preference and controller enrollment."""
    METHODS = [
        ("Xbox Wireless Adapter", "Microsoft proprietary wireless adapter", "radio-tower", "xbox_adapter"),
        ("Bluetooth", "Built-in or USB Bluetooth", "bluetooth", "bluetooth"),
        ("USB cable", "Direct wired connection", "usb", "usb"),
    ]

    def __init__(self, monitor: ControllerMonitor, settings: QSettings, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self.settings = settings
        self.selected_method = "auto"
        self.detected_info = None
        self.setWindowTitle(APP_NAME + " — Setup")
        self.setFixedWidth(390)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            QDialog { background:transparent; color:#F2F4F7; }
            QLabel { color:#F2F4F7; background:transparent; }
            QLabel#muted { color:#9BA3AF; font-size:11px; }
            QLabel#heading { font-size:18px; font-weight:700; }
            QPushButton#method {
                text-align:left; background:rgba(25,29,36,205); border:1px solid rgba(120,130,145,90);
                border-radius:10px; padding:13px; color:#F2F4F7; font-size:12px;
            }
            QPushButton#method:hover { background:rgba(42,49,60,225); border:1px solid #647184; }
            QPushButton#method:checked { background:rgba(32,56,43,235); border:1px solid #38B56A; }
            QPushButton#continue {
                background:#00D451; color:white; border:0; border-radius:9px;
                padding:11px; font-weight:650;
            }
            QPushButton#continue:disabled { background:#343A44; color:#858D99; }
            QPushButton#footer {
                background:transparent; border:0; color:#8DBCF0; font-size:11px;
                padding:5px;
            }
            QPushButton#footer:hover { color:#C1DEFF; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(11)

        app_header = QLabel("XboxControllerHotkey")
        app_header.setStyleSheet("color:#D8DEE8;font-size:10px;font-weight:600;")
        layout.addWidget(app_header)

        title = QLabel("Connect your controller")
        title.setObjectName("heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        intro = QLabel("How do you normally connect your controller?")
        intro.setObjectName("muted")
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro)
        layout.addSpacing(5)

        self.method_buttons = []
        for title_text, subtitle, icon_name, method_key in self.METHODS:
            btn = QPushButton(f"{title_text}\n{subtitle}")
            icon_assets = {
                "xbox_adapter": "xbox-icon.png",
                "bluetooth": "bluetooth-icon.png",
                "usb": "usb-icon.png",
            }
            icon_path = resource_path(os.path.join("assets", icon_assets[method_key]))
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(28, 28))
            btn.setObjectName("method")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked=False, m=method_key: self.choose_method(m))
            layout.addWidget(btn)
            self.method_buttons.append(btn)

        footer = QPushButton("Not sure?  Let the app detect it")
        footer.setObjectName("footer")
        footer.clicked.connect(lambda: self.choose_method("auto"))
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.status = QLabel("Choose a connection method, then connect your controller.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        self.continue_button = QPushButton("Waiting for controller…")
        self.continue_button.setObjectName("continue")
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.finish_setup)
        layout.addWidget(self.continue_button)

        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(1000)
        self.scan_timer.timeout.connect(self.scan)
        self.scan_timer.start()
        self.scan()

    def paintEvent(self, event):
        paint_custom_background(self, "setup-background.png", radius=16, overlay_alpha=115)
        super().paintEvent(event)

    def resizeEvent(self, event):
        rounded_widget_mask(self, 16)
        super().resizeEvent(event)

    def choose_method(self, method):
        self.selected_method = method
        if method == "auto":
            self.status.setText("Automatic detection selected. Connect your controller.")
        else:
            display = next((x[0] for x in self.METHODS if x[3] == method), method)
            self.status.setText(f"Preferred connection: {display}. Connect your controller.")
        self.scan()

    def scan(self):
        info = self.monitor.refresh()
        if info:
            self.detected_info = info
            self.status.setText(f"Detected: {info.name}\nIs this the controller you want to use?")
            self.continue_button.setText("Use this controller")
            self.continue_button.setEnabled(True)
        else:
            self.detected_info = None
            self.continue_button.setText("Waiting for controller…")
            self.continue_button.setEnabled(False)

    def finish_setup(self):
        if not self.detected_info:
            return
        info = self.detected_info
        self.settings.setValue("setupComplete", True)
        self.settings.setValue("preferredConnection", self.selected_method)
        self.settings.setValue("controllerGuid", info.guid)
        self.settings.setValue("selectedControllerGuid", info.guid)
        self.settings.setValue("controllerName", info.name)
        self.settings.setValue("exclusiveDevice", True)
        self.accept()



class ShortcutDialog(QDialog):
    MAX_SLOTS = 2  # Record That requires exactly two simultaneous controls.

    def __init__(self, monitor: ControllerMonitor, settings: QSettings, parent=None):
        super().__init__(parent)
        self.monitor=monitor
        self.settings=settings
        self.original_controls=list(monitor.shortcut_controls)
        self.slots=list(self.original_controls[:2])
        while len(self.slots)<2:
            self.slots.append(None)
        self.capture_slot=None
        self.waiting_for_release=False
        self.setWindowTitle("Configure Record That")
        self.setFixedWidth(370)
        self.setStyleSheet("""
            QDialog{background:#171A20;color:#F2F4F7;}
            QLabel{color:#F2F4F7;background:transparent;}
            QLabel#muted{color:#A7AFBB;font-size:11px;}
            QPushButton{background:#00D451;color:white;border:0;border-radius:8px;padding:9px;font-weight:600;}
            QPushButton:hover{background:#12E56A;}
            QPushButton#secondary{background:#292F39;color:#D8DEE8;}
            QPushButton#back{background:transparent;color:#A7AFBB;padding:3px 5px;}
            QPushButton#slot{background:#252B35;color:#F2F4F7;border:1px solid #343C48;padding:12px;}
        """)
        lay=QVBoxLayout(self)
        lay.setContentsMargins(18,15,18,24)
        lay.setSpacing(10)

        top=QHBoxLayout()
        back=QPushButton("←  Back")
        back.setObjectName("back")
        back.clicked.connect(self.reject)
        top.addWidget(back)
        top.addStretch()
        lay.addLayout(top)

        title=QLabel("Record That shortcut")
        title.setStyleSheet("font-size:17px;font-weight:750;")
        lay.addWidget(title)
        intro=QLabel("Assign each button separately. All selected controls must be held together to trigger Record That.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.preview=QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "background:#252B35;border:1px solid #343C48;border-radius:9px;"
            "padding:12px;font-size:13px;font-weight:700;color:#F2F4F7;"
        )
        lay.addWidget(self.preview)

        self.slot_buttons=[]
        for index in range(self.MAX_SLOTS):
            row=QHBoxLayout()
            slot=QPushButton()
            slot.setObjectName("slot")
            slot.setMinimumHeight(48)
            slot.clicked.connect(lambda checked=False, i=index: self.begin_slot_capture(i))
            row.addWidget(slot,1)
            self.slot_buttons.append(slot)
            lay.addLayout(row)

        self.capture_status=QLabel("Default: Back / View + Start / Menu")
        self.capture_status.setObjectName("muted")
        self.capture_status.setWordWrap(True)
        lay.addWidget(self.capture_status)

        warning=QLabel("Choose distinct controls. Custom combinations can trigger accidentally or conflict with gameplay. Back + Start is the recommended default.")
        warning.setObjectName("muted")
        warning.setWordWrap(True)
        lay.addWidget(warning)

        actions=QHBoxLayout()
        reset=QPushButton("Revert to default")
        reset.setObjectName("secondary")
        reset.clicked.connect(self.reset_default)
        save=QPushButton("Save shortcut")
        save.clicked.connect(self.save)
        actions.addWidget(reset)
        actions.addWidget(save)
        lay.addLayout(actions)

        self.timer=QTimer(self)
        self.timer.setInterval(12)
        self.timer.timeout.connect(self.capture_poll)
        self.monitor.capture_mode=True
        self.update_slots()

    @staticmethod
    def control_name(control):
        if not control:
            return "Not configured"
        if control.startswith("button:"):
            try:
                index=int(control.split(":")[1])
                return BUTTON_NAMES.get(index, f"Button {index+1}")
            except Exception:
                return "Controller button"
        if control.startswith("hat:"):
            _, index, direction=control.split(":")
            return f"D-pad {direction.title()}"
        return "Controller control"

    @staticmethod
    def shortcut_text(controls):
        return " + ".join(ShortcutDialog.control_name(c) for c in controls if c) if controls else "Not configured"

    def update_slots(self):
        for i,button in enumerate(self.slot_buttons):
            value=self.slots[i]
            button.setText(f"Button {i+1}     {self.control_name(value)}")
        configured=[self.control_name(x) for x in self.slots if x]
        self.preview.setText("  +  ".join(configured) if configured else "No shortcut configured")
        count=len(configured)
        self.capture_status.setText(
            f"{count}-button combination configured. Select a slot to assign or replace its control."
        )

    def begin_slot_capture(self,index):
        self.capture_slot=index
        self.waiting_for_release=True
        self.monitor.last_hotkey=False
        self.capture_status.setText(
            f"Button {index+1}: release all controls, then press ONE button or D-pad direction."
        )
        self.slot_buttons[index].setText("Listening… release, then press one control")
        self.timer.start()

    def capture_poll(self):
        pressed=self.monitor.pressed_controls()
        if self.waiting_for_release:
            if not pressed:
                self.waiting_for_release=False
                self.capture_status.setText(
                    f"Button {self.capture_slot+1}: now press and release one controller control."
                )
            return
        if pressed and self.capture_slot is not None:
            if len(pressed)!=1:
                self.capture_status.setText("One control at a time, please. Release and try again.")
                return
            control=next(iter(pressed))
            if control in [x for i,x in enumerate(self.slots) if x and i!=self.capture_slot]:
                self.capture_status.setText("That control is already assigned to another slot. Choose a different one.")
                return
            self.slots[self.capture_slot]=control
            self.capture_slot=None
            self.timer.stop()
            self.monitor.last_hotkey=False
            self.update_slots()

    def clear_slot(self,index):
        if index<2:
            self.capture_status.setText("Both shortcut buttons are required.")
            return
        self.slots[index]=None
        self.update_slots()

    def reset_default(self):
        self.timer.stop()
        self.capture_slot=None
        self.slots=[f"button:{b}" for b in DEFAULT_SHORTCUT]
        self.update_slots()
        self.capture_status.setText("Default restored: Back / View + Start / Menu. Save to apply.")

    def reject(self):
        self.timer.stop()
        self.monitor.capture_mode=False
        self.monitor.last_hotkey=False
        self.monitor.shortcut_controls=list(self.original_controls)
        super().reject()

    def save(self):
        controls=[x for x in self.slots if x]
        if len(controls)<2:
            self.capture_status.setText("Assign at least two different controls.")
            return
        self.timer.stop()
        self.monitor.shortcut_controls=controls
        self.monitor.capture_mode=False
        self.monitor.last_hotkey=False
        self.settings.setValue("shortcutControls", controls)
        self.settings.setValue("shortcutButtons", [
            int(x.split(":")[1]) for x in controls if x.startswith("button:")
        ])
        self.accept()


class UpdateCheckWorker(QThread):
    result=Signal(str, str, str, str, str)

    def run(self):
        import urllib.error
        import urllib.request
        headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        try:
            request=urllib.request.Request(GITHUB_RELEASES_API,headers=headers)
            with urllib.request.urlopen(request,timeout=5.0) as response:
                data=json.loads(response.read().decode("utf-8"))
            if not isinstance(data,dict) or data.get("draft") or data.get("prerelease"):
                self.result.emit("","","GitHub did not return a published stable release.","",""); return
            tag=data.get("tag_name",""); url=data.get("html_url",GITHUB_RELEASES_PAGE)
            assets={a.get("name",""):a.get("browser_download_url","") for a in data.get("assets",[]) if isinstance(a,dict)}
            exe_url=assets.get("XboxControllerHotkey.exe","")
            sha_url=assets.get("XboxControllerHotkey.exe.sha256","")
            if not tag:
                self.result.emit("","","The latest GitHub release has no version tag.","",""); return
            self.result.emit(tag,url,"release",exe_url,sha_url)
        except urllib.error.HTTPError as exc:
            detail = "No published GitHub release was found. Publish a stable release to enable version checks." if exc.code==404 else ("GitHub refused the request (possibly API rate-limited). Try again later." if exc.code==403 else f"GitHub returned HTTP {exc.code}.")
            self.result.emit("","",detail,"","")
        except Exception as exc:
            self.result.emit("","",f"Could not reach GitHub: {exc}","","")


class UpdatePromptDialog(QDialog):
    def __init__(self, latest_version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update available")
        self.setModal(True)
        self.setFixedWidth(390)
        self.setStyleSheet("""
            QDialog{background:#17191F;color:#F2F4F7;}
            QLabel{color:#F2F4F7;}
            QPushButton{background:#00D451;color:#06130A;border:0;border-radius:9px;padding:11px;font-weight:700;min-height:20px;}
            QPushButton:hover{background:#12E56A;}
            QPushButton#secondary{background:#262D38;color:#E8EDF4;border:1px solid #414956;}
            QPushButton#secondary:hover{background:#343D4A;color:white;}
            QCheckBox{color:#AEB7C4;font-size:11px;spacing:7px;}
        """)
        self.choice = "later"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel("Do you want to update now?")
        title.setStyleSheet("font-size:16px;font-weight:750;color:#F2F4F7;")
        layout.addWidget(title)

        versions = QLabel(
            f"XboxControllerHotkey v{APP_VERSION} is installed.\n"
            f"Version v{latest_version} is available."
        )
        versions.setStyleSheet("color:#C5CCD6;font-size:12px;padding:7px 0;")
        layout.addWidget(versions)

        update = QPushButton("Update Now")
        update.setDefault(True)
        update.clicked.connect(self._update)
        layout.addWidget(update)

        later = QPushButton("Remind me later")
        later.setObjectName("secondary")
        later.clicked.connect(self.reject)
        layout.addWidget(later)

        layout.addStretch(1)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 8, 0, 0)
        self.do_not_ask = QCheckBox("Do not ask me again")
        footer.addWidget(self.do_not_ask)
        footer.addStretch(1)
        layout.addLayout(footer)

    def _update(self):
        self.choice = "update"
        self.accept()

class UpdateDownloadWorker(QThread):
    result=Signal(bool,str)
    def __init__(self, exe_url, sha_url, parent=None):
        super().__init__(parent); self.exe_url=exe_url; self.sha_url=sha_url
    def run(self):
        import urllib.request
        try:
            if not self.exe_url or not self.sha_url:
                raise RuntimeError("This GitHub release is missing the EXE or SHA-256 checksum asset.")
            with urllib.request.urlopen(self.sha_url, timeout=20) as r: expected=r.read().decode("ascii").strip().split()[0].lower()
            fd, path=tempfile.mkstemp(prefix="XboxControllerHotkey-update-",suffix=".exe"); os.close(fd)
            digest=hashlib.sha256()
            with urllib.request.urlopen(self.exe_url, timeout=90) as r, open(path,"wb") as out:
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk: break
                    out.write(chunk); digest.update(chunk)
            if digest.hexdigest().lower()!=expected:
                os.remove(path); raise RuntimeError("The downloaded update failed its SHA-256 verification.")
            self.result.emit(True,path)
        except Exception as exc:
            self.result.emit(False,str(exc))


STARTUP_REGISTRY_KEY = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
STARTUP_VALUE_NAME = "XboxControllerHotkey"


def startup_command():
    """Return a quoted command that starts this exact portable/installed copy."""
    executable = os.path.abspath(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    script = os.path.abspath(__file__)
    return f'"{executable}" "{script}"'


def is_startup_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY,
                            0, winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
        return str(value).strip() == startup_command()
    except OSError:
        return False


def set_startup_enabled(enabled):
    """Enable/disable launch-at-sign-in for the current Windows user only."""
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY,
                                0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ,
                                  startup_command())
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def version_tuple(value: str):
    """Normalize v-prefixed dotted release versions for numeric comparison."""
    parts = re.findall(r"\d+", (value or "").strip())
    return tuple(int(part) for part in parts) if parts else (0,)


def controller_family(name: str) -> str:
    n=(name or "").lower()
    if any(x in n for x in ("playstation", "dualsense", "dualshock", "wireless controller")):
        return "playstation"
    if any(x in n for x in ("nintendo", "switch pro", "joy-con")):
        return "switch"
    if any(x in n for x in ("xbox", "xinput", "elite")):
        return "xbox"
    return "generic"


class ControllerSelectionDialog(QDialog):
    """Choose which currently connected mapped gamepad the app should monitor."""
    def __init__(self, monitor: ControllerMonitor, settings: QSettings, open_accessories, parent=None):
        super().__init__(parent)
        self.monitor=monitor
        self.settings=settings
        self.open_accessories_callback=open_accessories
        self.setWindowTitle("Select controller")
        self.setFixedWidth(350)
        self.setStyleSheet("""
            QDialog{background:#171A20;color:#F2F4F7;}
            QLabel{color:#F2F4F7;background:transparent;}
            QLabel#muted{color:#A7AFBB;font-size:11px;}
            QListWidget{background:#222731;color:#F2F4F7;border:1px solid #343A44;border-radius:8px;padding:4px;}
            QListWidget::item{padding:10px;border-radius:6px;}
            QListWidget::item:selected{background:#087A3A;}
            QPushButton{background:#00D451;color:white;border:0;border-radius:8px;padding:9px;font-weight:600;}
            QPushButton#secondary{background:#292F39;color:#D8DEE8;}
        """)
        lay=QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16)
        lay.setSpacing(10)
        title=QLabel("Choose your controller")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        lay.addWidget(title)
        hint=QLabel("Select which connected gamepad XboxControllerHotkey should monitor.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.devices=QListWidget()
        self.device_ids=[]
        self.monitor.refresh()
        for item in self.monitor.available_devices:
            self.devices.addItem(item.name)
            self.device_ids.append(item.instance_id)
        if self.device_ids:
            selected=self.monitor.selected_instance_id
            idx=self.device_ids.index(selected) if selected in self.device_ids else 0
            self.devices.setCurrentRow(idx)
        else:
            self.devices.addItem("No supported controllers detected")
            self.devices.setEnabled(False)
        lay.addWidget(self.devices)
        choose=QPushButton("Use selected controller")
        choose.clicked.connect(self.apply_selection)
        lay.addWidget(choose)
        accessories=QPushButton("Open Xbox Accessories")
        accessories.setObjectName("secondary")
        accessories.clicked.connect(self.open_accessories_callback)
        lay.addWidget(accessories)

    def apply_selection(self):
        row=self.devices.currentRow()
        if row<0 or row>=len(self.device_ids):
            return
        self.monitor.select_device(self.device_ids[row])
        self.settings.setValue("selectedControllerGuid", self.monitor.selected_guid)
        self.settings.setValue("selectedControllerName", self.monitor.active.name if self.monitor.active else "")
        self.accept()


class ActivityGraph(QWidget):
    """Transparent, continuously scrolling controller-input waveform."""
    def __init__(self,parent=None):
        super().__init__(parent); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,True)
        self.setFixedHeight(54); self.samples=[0.0]*180; self.activity_source=lambda:0.0
        self.timer=QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.sample); self.timer.start()
    def sample(self):
        try: value=max(0.0,min(1.0,float(self.activity_source())))
        except Exception: value=0.0
        self.samples.pop(0); self.samples.append(value); self.update()
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=max(1,self.width()); h=self.height(); baseline=h-20; path=QPainterPath()
        for i,value in enumerate(self.samples):
            x=(i/(len(self.samples)-1))*w; y=baseline-value*(h-29)
            if i==0: path.moveTo(x,y)
            else: path.lineTo(x,y)
        points=[]
        for i,value in enumerate(self.samples):
            x=(i/(len(self.samples)-1))*w
            y=baseline-value*(h-29)
            points.append(QPoint(int(x),int(y)))
        for i in range(1,len(points)):
            area=QPainterPath()
            area.moveTo(points[i-1]); area.lineTo(points[i])
            area.lineTo(points[i].x(),h); area.lineTo(points[i-1].x(),h); area.closeSubpath()
            alpha=int(26+76*max(self.samples[i-1],self.samples[i]))
            gradient=QLinearGradient(0,0,0,h)
            gradient.setColorAt(0,QColor(0,212,81,alpha))
            gradient.setColorAt(1,QColor(0,212,81,0))
            painter.fillPath(area,gradient)
        painter.setPen(QPen(QColor("#00D451"),2.0,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path); painter.end()


def capture_folder_path():
    """Resolve the user's configured Windows Gaming Captures folder."""
    fallback=os.path.join(os.path.expanduser("~"),"Videos","Captures")
    if os.name!="nt": return fallback
    try:
        import winreg
        key_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        value_name="{EDC0FE71-98D8-4F4A-B920-C8DC133CB165}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path) as key:
            value,_=winreg.QueryValueEx(key,value_name)
        return os.path.expandvars(str(value))
    except Exception: return fallback


class StatusPopover(QFrame):
    def __init__(self, monitor: ControllerMonitor, tray: QSystemTrayIcon, settings: QSettings, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.monitor = monitor
        self.tray = tray
        self.settings = settings
        self.setObjectName("popover")
        self.setFixedSize(430,650)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()
        self.refresh()

    def paintEvent(self, event):
        paint_custom_background(self, "tray-background.png", radius=16, overlay_alpha=120)
        super().paintEvent(event)

    def resizeEvent(self, event):
        rounded_widget_mask(self, 16)
        if hasattr(self,"close_button"):
            self.close_button.setGeometry(self.width()-30,2,30,30)
            self.close_button.raise_()
        super().resizeEvent(event)

    def _build_ui(self):
        self.setStyleSheet("""
            QFrame#popover {
                background: transparent;
                border: 0;
                border-radius: 16px;
            }
            QStackedWidget, QStackedWidget > QWidget {
                background: transparent;
                border: 0;
            }
            QLabel { color: #F2F4F7; background: transparent; }
            QLabel#muted { color: #B8C1CE; font-size: 12px; }
            QLabel#title { font-size: 27px; font-weight: 750; }
            QLabel#subtitle { color: #C3CBD6; font-size: 13px; font-weight: 500; }
            QLabel#section { color: #C3CBD6; font-size: 13px; font-weight: 500; }
            QLabel#value { font-size: 13px; font-weight: 650; }
            QFrame#details { background: rgba(20,24,30,215); border: 1px solid rgba(130,140,155,55); border-radius: 10px; }
            QPushButton {
                background: #00D451; color: white; border: 0;
                border-radius: 9px; padding: 8px 10px;
                min-height: 38px; max-height: 38px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton:hover { background: #12E56A; }
            QPushButton:pressed { background: #00B948; }
            QPushButton#actionButton {
                background:#00D451; color:#FFFFFF; border:0; border-radius:9px;
                padding:0px; min-height:74px; max-height:74px;
                font-size:11px; font-weight:700;
            }
            QPushButton#actionButton:hover { background:#12E56A; }
            QPushButton#actionButton:pressed { background:#00B948; }
            QPushButton#secondary {
                background: rgba(38,45,56,225); color: #E8EDF4;
                border: 1px solid rgba(130,140,155,65);
                border-radius: 9px; padding: 8px 10px;
                min-height: 38px; max-height: 38px;
                font-size: 12px; font-weight: 650;
            }
            QPushButton#secondary:hover { background: #343D4A; color: white; }
            QPushButton#back {
                background: transparent; color: #F2F4F7;
                padding: 0; text-align: left;
                font-size: 14px; font-weight: 700;
                min-height: 26px; max-height: 26px;
            }
            QPushButton#back:hover { color: #8AD7A8; background: transparent; }
        """)

        outer=QVBoxLayout(self)
        outer.setContentsMargins(16,14,16,0)
        outer.setSpacing(0)

        self.pages=QStackedWidget()
        outer.addWidget(self.pages)

        # ---------------- HOME ----------------
        self.home_page=QWidget()
        root=QVBoxLayout(self.home_page)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(6)

        header=QHBoxLayout()
        header.setContentsMargins(0,-7,0,0)
        brand_col=QVBoxLayout()
        brand_col.setSpacing(1)
        brand=QLabel(APP_NAME)
        brand.setObjectName("title")
        brand_font=QFont(brand.font())
        brand_font.setPointSizeF(20.5)
        brand_font.setWeight(QFont.Weight.Bold)
        brand_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,-0.45)
        brand.setFont(brand_font)
        brand_col.addWidget(brand)
        app_version=QLabel(f"Version {APP_VERSION}")
        app_version.setStyleSheet("color:#A7AFBB;font-size:10px;font-weight:500;")
        brand_col.addWidget(app_version)
        header.addLayout(brand_col)
        header.addStretch()
        close_button=QPushButton("×")
        close_button.setToolTip("Hide to system tray")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setFixedSize(30,30)
        close_button.setStyleSheet(
            "QPushButton{background:transparent;color:#FFFFFF;border:0;padding:0;"
            "font-size:30px;font-weight:400;min-height:30px;max-height:30px;}"
            "QPushButton:hover{color:#00D451;background:transparent;}"
        )
        close_button.clicked.connect(self.hide)
        self.close_button=close_button
        close_button.setParent(self)
        close_button.setGeometry(self.width()-30,2,30,30)
        close_button.raise_()
        root.addLayout(header)

        # Connection state is intentionally shown in the lower-left footer,
        # matching the user's preferred home-panel composition.
        status_wrap=QWidget()
        status_layout=QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(0,0,0,0)
        status_layout.setSpacing(6)
        self.state_dot=QLabel("●")
        self.state_dot.setFixedSize(12,18)
        self.state_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_dot.setStyleSheet("color:#A7AFBB;font-size:10px;padding:0;margin:0;")
        self.state_text=QLabel("Disconnected")
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.state_text.setStyleSheet("color:#B8C1CE;font-size:12px;font-weight:650;")
        status_layout.addWidget(self.state_dot,alignment=Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self.state_text,alignment=Qt.AlignmentFlag.AlignVCenter)

        self.controller_icon=QLabel()
        self.controller_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controller_icon.setFixedHeight(72)
        controller_pix=QPixmap(resource_path(os.path.join("assets","controller-icon.png")))
        if not controller_pix.isNull():
            self.controller_icon.setPixmap(controller_pix.scaled(
                QSize(190,100),Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        root.addWidget(self.controller_icon)

        self.controller_name=QLabel("No controller detected")
        self.controller_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controller_name.setWordWrap(True)
        self.controller_name.setStyleSheet("font-size:20px;font-weight:700;")
        controller_name_font=QFont(self.controller_name.font())
        controller_name_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,-0.30)
        self.controller_name.setFont(controller_name_font)
        self.controller_subtitle=QLabel("Connect an Xbox controller to get started")
        self.controller_subtitle.setObjectName("subtitle")
        self.controller_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        identity_layout=QVBoxLayout()
        identity_layout.setContentsMargins(0,0,0,0)
        identity_layout.setSpacing(1)
        identity_layout.addWidget(self.controller_name)
        identity_layout.addWidget(self.controller_subtitle)
        root.addLayout(identity_layout)

        info_row=QHBoxLayout(); info_row.setSpacing(8)
        battery_card=QFrame(); battery_card.setObjectName("details")
        battery_lay=QHBoxLayout(battery_card); battery_lay.setContentsMargins(10,7,8,7); battery_lay.setSpacing(7)
        battery_icon=QLabel("▰"); battery_icon.setStyleSheet("font-size:22px;color:#FFFFFF;"); battery_lay.addWidget(battery_icon)
        battery_text=QVBoxLayout(); battery_text.setSpacing(1)
        battery_label=QLabel("Battery"); battery_label.setObjectName("section")
        self.battery_value=QLabel("—"); self.battery_value.setObjectName("value")
        battery_text.addWidget(battery_label); battery_text.addWidget(self.battery_value); battery_lay.addLayout(battery_text,1)
        info_row.addWidget(battery_card,1)
        shortcut_card=QFrame(); shortcut_card.setObjectName("details")
        shortcut_lay=QHBoxLayout(shortcut_card); shortcut_lay.setContentsMargins(10,7,8,7); shortcut_lay.setSpacing(7)
        shortcut_icon=QLabel("▣"); shortcut_icon.setStyleSheet("font-size:22px;color:#FFFFFF;"); shortcut_lay.addWidget(shortcut_icon)
        shortcut_text=QVBoxLayout(); shortcut_text.setSpacing(1)
        shortcut_label=QLabel("Record That shortcut"); shortcut_label.setObjectName("section")
        self.hotkey_value=QLabel(ShortcutDialog.shortcut_text(self.monitor.shortcut_controls)); self.hotkey_value.setObjectName("value")
        shortcut_text.addWidget(shortcut_label); shortcut_text.addWidget(self.hotkey_value); shortcut_lay.addLayout(shortcut_text,1)
        info_row.addWidget(shortcut_card,1); root.addLayout(info_row)
        action_row=QHBoxLayout(); action_row.setSpacing(7)
        self._add_icon_button(action_row,"Configure\\nshortcut","configure-shortcut.png.b64",self.show_shortcut_page)
        self._add_icon_button(action_row,"Configure\\ncontroller","xbox-icon.png",self.show_controller_page)
        self._add_icon_button(action_row,"Capture\\nsettings","capture-settings.svg",open_capture_settings)
        root.addLayout(action_row)
        secondary_row=QHBoxLayout(); secondary_row.setSpacing(8)
        self.clips_button=QPushButton(); self.clips_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clips_button.setStyleSheet("QPushButton{background:rgba(38,45,56,225);color:#FFFFFF;border:2px solid #00D451;border-radius:12px;padding:5px;min-height:48px;max-height:48px;} QPushButton:hover{background:#25342D;}")
        clips_lay=QHBoxLayout(self.clips_button); clips_lay.setContentsMargins(8,2,8,2); clips_lay.setSpacing(7)
        clips_icon=QLabel("▣"); clips_icon.setStyleSheet("font-size:22px;color:#FFFFFF;"); clips_lay.addWidget(clips_icon)
        clips_label=QLabel("Clips Captured"); clips_label.setStyleSheet("font-size:12px;color:#E8EDF4;"); clips_lay.addWidget(clips_label); clips_lay.addStretch()
        self.clip_count_value=QLabel("0"); self.clip_count_value.setStyleSheet("font-size:22px;font-weight:800;color:#FFFFFF;"); clips_lay.addWidget(self.clip_count_value)
        self.clips_button.clicked.connect(self.open_captures_folder); secondary_row.addWidget(self.clips_button,1)
        about_button=QPushButton("ⓘ   About"); about_button.setObjectName("secondary"); about_button.clicked.connect(self.open_about)
        secondary_row.addWidget(about_button,1); root.addLayout(secondary_row)
        footer=QHBoxLayout()
        footer.setSpacing(6)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(status_wrap,alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addStretch()
        powered=QLabel("Powered by")
        powered.setObjectName("subtitle")
        footer.addWidget(powered,alignment=Qt.AlignmentFlag.AlignVCenter)
        logo=QLabel()
        logo.setFixedSize(48,48)
        logo.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.powered_movie=QMovie(resource_path(os.path.join("assets","powered-by-logo.gif")))
        if self.powered_movie.isValid():
            self.powered_movie.setScaledSize(QSize(48,48))
            logo.setMovie(self.powered_movie)
            self.powered_movie.start()
        else:
            logo_pix=QPixmap(resource_path(os.path.join("assets","powered-by-logo.png")))
            if not logo_pix.isNull():
                logo.setPixmap(logo_pix.scaled(QSize(48,48),Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
        footer.addWidget(logo,alignment=Qt.AlignmentFlag.AlignBottom)
        root.addLayout(footer)
        self.activity_graph=ActivityGraph(self.home_page)
        self.activity_graph.activity_source=lambda: getattr(self,"activity_source",lambda:0.0)()
        root.addWidget(self.activity_graph)
        self.pages.addWidget(self.home_page)

        # ---------------- ABOUT ----------------
        self.about_page=QWidget()
        about_lay=QVBoxLayout(self.about_page)
        about_lay.setContentsMargins(0,0,0,0)
        about_lay.setSpacing(10)
        about_header=QHBoxLayout()
        about_back=QPushButton("Back")
        about_back.setObjectName("back")
        about_back.setIcon(QIcon(resource_path(os.path.join("assets","arrow-back-white.png"))))
        about_back.setIconSize(QSize(16,16))
        about_back.setFixedHeight(26)
        about_back.clicked.connect(self.show_home)
        about_header.addWidget(about_back)
        about_header.addStretch()
        about_lay.addLayout(about_header)

        about_title=QLabel(APP_NAME)
        about_title.setStyleSheet("font-size:18px;font-weight:750;")
        about_lay.addWidget(about_title)
        about_version=QLabel(f"Version {APP_VERSION}")
        about_version.setStyleSheet("color:#A7AFBB;font-size:11px;")
        about_lay.addWidget(about_version)
        description=QLabel(
            "Use a two-button controller shortcut to trigger Windows Xbox Game Bar's "
            "Record That feature. Monitor controller connections and battery status "
            "from the system tray."
        )
        description.setWordWrap(True)
        about_lay.addWidget(description)

        created=QLabel(
            'Created by <a href="https://linktr.ee/jimhatesyou" '
            'style="color:#B8C1CE;text-decoration:underline;">James Cavanaugh</a>.'
        )
        created.setTextFormat(Qt.TextFormat.RichText)
        created.setOpenExternalLinks(True)
        created.setStyleSheet("color:#B8C1CE;font-size:12px;")
        created.setWordWrap(True)
        about_lay.addWidget(created)

        self.update_status=QLabel("Checking GitHub releases…")
        self.update_status.setStyleSheet("color:#A7AFBB;font-size:11px;")
        self.update_status.setWordWrap(True)
        about_lay.addWidget(self.update_status)

        self.check_button=QPushButton("Check for updates")
        self.check_button.clicked.connect(self.check_updates)
        about_lay.addWidget(self.check_button)

        self.install_update_button=QPushButton("Update now")
        self.install_update_button.setVisible(False)
        self.install_update_button.clicked.connect(self.begin_auto_update)
        about_lay.addWidget(self.install_update_button)

        faq_button=QPushButton("FAQs")
        faq_button.setObjectName("secondary")
        faq_button.clicked.connect(self.show_faq)
        about_lay.addWidget(faq_button)

        self.release_button=QPushButton("View latest release")
        self.release_button.setObjectName("secondary")
        self.release_button.setVisible(False)
        self.release_button.clicked.connect(self.open_latest_release)
        about_lay.addWidget(self.release_button)

        github=QPushButton("View GitHub project")
        github.setObjectName("secondary")
        github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_REPO)))
        about_lay.addWidget(github)
        first_launch_button=QPushButton("View first-launch notice")
        first_launch_button.setObjectName("secondary")
        first_launch_button.clicked.connect(self.show_first_launch_notice)
        about_lay.addWidget(first_launch_button)

        about_lay.addStretch(1)

        thank_you=QLabel("Thank you for using XboxControllerHotkey.")
        thank_you.setStyleSheet("color:#FFFFFF;font-size:14px;")
        thank_you.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_lay.addWidget(thank_you)

        coffee=QLabel('<a href="https://www.buymeacoffee.com/jimhatesyou" style="color:#00D451; text-decoration:underline;">Buy me a coffee</a>')
        coffee.setOpenExternalLinks(True)
        coffee.setTextFormat(Qt.TextFormat.RichText)
        coffee.setStyleSheet("QLabel { color:#00D451; font-size:12px; padding:4px 0; }")
        coffee.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_lay.addWidget(coffee)
        self.pages.addWidget(self.about_page)

        # ---------------- FAQ ----------------
        self.faq_page=QWidget()
        faq_lay=QVBoxLayout(self.faq_page)
        faq_lay.setContentsMargins(0,0,0,0)
        faq_lay.setSpacing(9)
        faq_header=QHBoxLayout()
        faq_back=QPushButton("Back")
        faq_back.setObjectName("back")
        faq_back.setIcon(QIcon(resource_path(os.path.join("assets","arrow-back-white.png"))))
        faq_back.setIconSize(QSize(16,16))
        faq_back.setFixedHeight(26)
        faq_back.clicked.connect(self.show_about)
        faq_header.addWidget(faq_back)
        faq_header.addStretch()
        faq_lay.addLayout(faq_header)
        faq_title=QLabel("Frequently asked questions")
        faq_title.setStyleSheet("font-size:16px;font-weight:700;")
        faq_lay.addWidget(faq_title)

        faq_scroll=QScrollArea()
        faq_scroll.setWidgetResizable(True)
        faq_scroll.setFrameShape(QFrame.Shape.NoFrame)
        faq_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        faq_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        faq_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 7px;
                margin: 3px 1px 3px 1px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #586272;
                min-height: 30px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00D451;
            }
            QScrollBar::handle:vertical:pressed {
                background: #00B947;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        faq_content=QWidget()
        faq_content_lay=QVBoxLayout(faq_content)
        faq_content_lay.setContentsMargins(2,2,8,2)
        faq_content_lay.setSpacing(9)
        faqs=[
            ("Which controllers are supported?",
             "Xbox controllers are the primary target. PlayStation and Nintendo controllers may work when Windows and SDL expose them as mapped game controllers. Compatibility varies by model, connection method and driver."),
            ("Does the app record gameplay?",
             "No. It detects your configured controller-button combination and sends the Windows Xbox Game Bar Record That shortcut (Win + Alt + G). Xbox Game Bar handles the capture."),
            ("Why does my battery level say Full or Unavailable?",
             "Battery reporting depends on what the controller and Windows driver expose. Some connection methods provide only broad battery states, and some controllers do not expose battery data to this app."),
            ("Can I use the same controller wirelessly and over USB?",
             "The app can detect supported controller connections, but identifying two Windows device instances as the same physical controller is not guaranteed for every model or adapter."),
            ("Can I change the Record That shortcut?",
             "Yes. Open Configure shortcut, assign two or three controller controls, and save. Back + Start is the default. Choose a combination that is unlikely to occur during normal gameplay."),
            ("Why does Record That not start?",
             "Make sure Xbox Game Bar is installed and configured, its Record That shortcut is enabled, and the app is running with the intended controller connected. The app sends Win + Alt + G by default."),
        ]
        for question,answer in faqs:
            q=QLabel(question)
            q.setStyleSheet("font-size:13px;font-weight:700;color:#FFFFFF;")
            q.setWordWrap(True)
            a=QLabel(answer)
            a.setStyleSheet("color:#B8C1CE;font-size:12px;")
            a.setWordWrap(True)
            faq_content_lay.addWidget(q)
            faq_content_lay.addWidget(a)
        faq_content_lay.addStretch(1)
        faq_scroll.setWidget(faq_content)
        faq_lay.addWidget(faq_scroll,1)
        self.pages.addWidget(self.faq_page)

        # ---------------- CONFIGURE SHORTCUT (IN-POPOVER PAGE) ----------------
        self.shortcut_page=QWidget()
        shortcut_lay=QVBoxLayout(self.shortcut_page)
        shortcut_lay.setContentsMargins(0,0,0,0)
        shortcut_lay.setSpacing(10)
        shortcut_header=QHBoxLayout()
        shortcut_back=QPushButton("Back")
        shortcut_back.setObjectName("back")
        shortcut_back.setIcon(QIcon(resource_path(os.path.join("assets","arrow-back-white.png"))))
        shortcut_back.setIconSize(QSize(16,16))
        shortcut_back.setFixedHeight(26)
        shortcut_back.clicked.connect(self.cancel_shortcut_page)
        shortcut_header.addWidget(shortcut_back)
        shortcut_header.addStretch()
        shortcut_lay.addLayout(shortcut_header)

        shortcut_title=QLabel("Configure Record That shortcut")
        shortcut_title.setStyleSheet("font-size:17px;font-weight:700;")
        shortcut_lay.addWidget(shortcut_title)
        shortcut_hint=QLabel("Assign two controller buttons. Both must be held simultaneously.")
        shortcut_hint.setObjectName("subtitle")
        shortcut_hint.setWordWrap(True)
        shortcut_lay.addWidget(shortcut_hint)

        self.shortcut_preview=QLabel()
        self.shortcut_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.shortcut_preview.setStyleSheet(
            "background:rgba(35,42,52,220);border:1px solid rgba(130,140,155,70);"
            "border-radius:9px;padding:13px;font-size:14px;font-weight:700;"
        )
        shortcut_lay.addWidget(self.shortcut_preview)

        self.shortcut_slots=[]
        for slot_index in range(2):
            slot_row=QHBoxLayout()
            slot_button=QPushButton()
            slot_button.setObjectName("secondary")
            slot_button.setMinimumHeight(42)
            slot_button.clicked.connect(lambda checked=False,i=slot_index:self.begin_shortcut_capture(i))
            slot_row.addWidget(slot_button,1)
            self.shortcut_slots.append(slot_button)
            shortcut_lay.addLayout(slot_row)

        self.shortcut_capture_status=QLabel("Default combination: Back + Start")
        self.shortcut_capture_status.setObjectName("subtitle")
        self.shortcut_capture_status.setWordWrap(True)
        shortcut_lay.addWidget(self.shortcut_capture_status)
        shortcut_warning=QLabel(
            "Custom combinations may trigger accidentally or conflict with gameplay. "
            "Back + Start is the recommended default because it is rarely pressed together."
        )
        shortcut_warning.setObjectName("subtitle")
        shortcut_warning.setWordWrap(True)
        shortcut_lay.addWidget(shortcut_warning)

        shortcut_actions=QHBoxLayout()
        reset_shortcut=QPushButton("Revert to default")
        reset_shortcut.setObjectName("secondary")
        reset_shortcut.clicked.connect(self.reset_shortcut_page)
        save_shortcut=QPushButton("Save shortcut")
        save_shortcut.clicked.connect(self.save_shortcut_page)
        shortcut_actions.addWidget(reset_shortcut,1)
        shortcut_actions.addWidget(save_shortcut,1)
        shortcut_lay.addLayout(shortcut_actions)
        shortcut_lay.addStretch(1)
        self.pages.addWidget(self.shortcut_page)

        # ---------------- CONFIGURE CONTROLLER (IN-POPOVER PAGE) ----------------
        self.controller_page=QWidget()
        controller_lay=QVBoxLayout(self.controller_page)
        controller_lay.setContentsMargins(0,0,0,0)
        controller_lay.setSpacing(10)
        controller_header=QHBoxLayout()
        controller_back=QPushButton("Back")
        controller_back.setObjectName("back")
        controller_back.setIcon(QIcon(resource_path(os.path.join("assets","arrow-back-white.png"))))
        controller_back.setIconSize(QSize(16,16))
        controller_back.setFixedHeight(26)
        controller_back.clicked.connect(self.show_home)
        controller_header.addWidget(controller_back)
        controller_header.addStretch()
        controller_lay.addLayout(controller_header)

        controller_title=QLabel("Configure controller")
        controller_title.setStyleSheet("font-size:17px;font-weight:700;")
        controller_lay.addWidget(controller_title)
        controller_hint=QLabel("Choose which connected controller XboxControllerHotkey should monitor.")
        controller_hint.setObjectName("subtitle")
        controller_hint.setWordWrap(True)
        controller_lay.addWidget(controller_hint)

        self.controller_devices=QListWidget()
        self.controller_devices.setStyleSheet(
            "QListWidget{background:rgba(24,29,37,225);color:#F2F4F7;"
            "border:1px solid rgba(130,140,155,70);border-radius:9px;padding:5px;font-size:13px;}"
            "QListWidget::item{padding:11px;border-radius:6px;}"
            "QListWidget::item:selected{background:#087A3A;}"
        )
        controller_lay.addWidget(self.controller_devices,1)

        refresh_devices=QPushButton("Refresh device list")
        refresh_devices.setObjectName("secondary")
        refresh_devices.clicked.connect(self.refresh_controller_page)
        controller_lay.addWidget(refresh_devices)
        use_controller=QPushButton("Use selected controller")
        use_controller.clicked.connect(self.apply_controller_selection)
        controller_lay.addWidget(use_controller)
        accessories_button=QPushButton("Open Xbox Accessories")
        accessories_button.setObjectName("secondary")
        accessories_button.clicked.connect(self.open_accessories)
        controller_lay.addWidget(accessories_button)
        self.pages.addWidget(self.controller_page)

        # Internal-page state; no child modal windows are used for configuration.
        self.shortcut_original=list(self.monitor.shortcut_controls)
        self.shortcut_slots_state=list(self.shortcut_original[:2])
        while len(self.shortcut_slots_state)<2:
            self.shortcut_slots_state.append(None)
        self.shortcut_capture_slot=None
        self.shortcut_waiting_release=False
        self.shortcut_capture_timer=QTimer(self)
        self.shortcut_capture_timer.setInterval(12)
        self.shortcut_capture_timer.timeout.connect(self.poll_shortcut_capture)
        self.device_refresh_timer=QTimer(self)
        self.device_refresh_timer.setInterval(1500)
        self.device_refresh_timer.timeout.connect(self.refresh_controller_page)
        self.update_checked=False

        self.pages.setCurrentWidget(self.home_page)
        self.pages.setFixedSize(398,632)

        # Update checks run off the UI thread with bounded network timeouts.
        self.update_worker=None
        self.update_workers=[]
        self.update_request_id=0
        self.update_timed_out=False
        self.update_timeout_timer=QTimer(self)
        self.update_timeout_timer.setSingleShot(True)
        self.update_timeout_timer.setInterval(7000)
        self.update_timeout_timer.timeout.connect(self.on_update_timeout)
        self.latest_release_url=GITHUB_RELEASES_PAGE
        self.latest_release_tag=""
        self.latest_exe_url=""
        self.latest_sha_url=""
        self.update_checked=False
        self.update_download_worker=None
        self.pending_update_prompt=False
        self.update_prompt_deferred=False

    def _show_page(self,page):
        self.pages.setCurrentWidget(page)
        self.pages.setVisible(True)
        self.pages.setFixedSize(398,632)
        if hasattr(self,"activity_graph"):
            self.activity_graph.setVisible(self.controller_connected and page is self.home_page)
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def show_home(self):
        self.shortcut_capture_timer.stop()
        self.device_refresh_timer.stop()
        if self.monitor.capture_mode:
            self.monitor.capture_mode=False
            self.monitor.last_hotkey=False
        self._show_page(self.home_page)
        self.refresh()
        self._maybe_show_update_prompt()

    def show_about(self):
        self._show_page(self.about_page)
        if not self.update_checked:
            self.check_updates()

    def show_faq(self):
        self._show_page(self.faq_page)

    def show_first_launch_notice(self):
        notice=FirstLaunchNotice(self)
        result=notice.exec()
        if result == QDialog.DialogCode.Accepted:
            self.show_home()
            if not self.isVisible():
                self.show_near_tray()

    def show_shortcut_page(self):
        self.shortcut_original=list(self.monitor.shortcut_controls)
        self.shortcut_slots_state=list(self.shortcut_original[:2])
        while len(self.shortcut_slots_state)<2:
            self.shortcut_slots_state.append(None)
        self.shortcut_capture_slot=None
        self.shortcut_waiting_release=False
        self.monitor.capture_mode=False
        self.monitor.last_hotkey=False
        self.update_shortcut_page()
        self._show_page(self.shortcut_page)

    def cancel_shortcut_page(self):
        self.shortcut_capture_timer.stop()
        self.monitor.capture_mode=False
        self.monitor.last_hotkey=False
        self.monitor.shortcut_controls=list(self.shortcut_original)
        self._show_page(self.home_page)

    def update_shortcut_page(self):
        for index,button in enumerate(self.shortcut_slots):
            control=self.shortcut_slots_state[index] if index<len(self.shortcut_slots_state) else None
            name=ShortcutDialog.control_name(control)
            button.setText(f"Button {index+1}     {name}")
        configured=[ShortcutDialog.control_name(x) for x in self.shortcut_slots_state if x]
        self.shortcut_preview.setText("  +  ".join(configured) if configured else "No shortcut configured")

    def begin_shortcut_capture(self,index):
        self.shortcut_capture_slot=index
        self.shortcut_waiting_release=True
        self.monitor.capture_mode=True
        self.monitor.last_hotkey=False
        self.shortcut_capture_status.setText(
            f"Button {index+1}: release all controls, then press ONE button or D-pad direction."
        )
        self.shortcut_slots[index].setText("Listening… release, then press one control")
        self.shortcut_capture_timer.start()

    def poll_shortcut_capture(self):
        pressed=self.monitor.pressed_controls()
        if self.shortcut_waiting_release:
            if not pressed:
                self.shortcut_waiting_release=False
                self.shortcut_capture_status.setText(
                    f"Button {self.shortcut_capture_slot+1}: now press one controller control."
                )
            return
        if pressed and self.shortcut_capture_slot is not None:
            if len(pressed)!=1:
                self.shortcut_capture_status.setText("One control at a time. Release and try again.")
                return
            control=next(iter(pressed))
            if control in [x for i,x in enumerate(self.shortcut_slots_state) if x and i!=self.shortcut_capture_slot]:
                self.shortcut_capture_status.setText("That control is already assigned to another slot.")
                return
            self.shortcut_slots_state[self.shortcut_capture_slot]=control
            self.shortcut_capture_slot=None
            self.shortcut_capture_timer.stop()
            self.monitor.capture_mode=False
            self.monitor.last_hotkey=False
            self.update_shortcut_page()
            self.shortcut_capture_status.setText("Control captured. Save shortcut or assign another button.")

    def clear_shortcut_slot(self,index):
        if index<2:
            self.shortcut_capture_status.setText("The first two buttons are required.")
            return
        self.shortcut_slots_state[index]=None
        self.update_shortcut_page()

    def reset_shortcut_page(self):
        self.shortcut_capture_timer.stop()
        self.shortcut_capture_slot=None
        self.monitor.capture_mode=False
        self.shortcut_slots_state=[f"button:{b}" for b in DEFAULT_SHORTCUT]
        self.update_shortcut_page()
        self.shortcut_capture_status.setText("Default restored: Back + Start. Save to apply.")

    def save_shortcut_page(self):
        controls=[x for x in self.shortcut_slots_state if x]
        if len(controls)<2:
            self.shortcut_capture_status.setText("Assign at least two different controls.")
            return
        self.shortcut_capture_timer.stop()
        self.monitor.capture_mode=False
        self.monitor.last_hotkey=False
        self.monitor.shortcut_controls=list(controls)
        self.settings.setValue("shortcutControls",controls)
        self.settings.setValue("shortcutButtons",[int(x.split(":")[1]) for x in controls if x.startswith("button:")])
        self.hotkey_value.setText(ShortcutDialog.shortcut_text(controls))
        self._show_page(self.home_page)

    def show_controller_page(self):
        self.refresh_controller_page()
        self._show_page(self.controller_page)
        self.device_refresh_timer.start()

    def refresh_controller_page(self):
        # This page only renders the latest background scan. Never enumerate
        # SDL devices from the UI thread.
        selected=self.monitor.selected_instance_id
        self.controller_devices.clear()
        for device in self.monitor.available_devices:
            label=device.name
            if device.connection and device.connection!="Connection type unavailable":
                label+=f"  ·  {device.connection}"
            item_text=label
            self.controller_devices.addItem(item_text)
            item=self.controller_devices.item(self.controller_devices.count()-1)
            item.setData(Qt.ItemDataRole.UserRole,device.instance_id)
            if device.instance_id==selected:
                self.controller_devices.setCurrentItem(item)
        if not self.monitor.available_devices:
            self.controller_devices.addItem("No supported controllers detected")
            self.controller_devices.setEnabled(False)
        else:
            self.controller_devices.setEnabled(True)

    def apply_controller_selection(self):
        item=self.controller_devices.currentItem()
        if item is None:
            return
        instance_id=item.data(Qt.ItemDataRole.UserRole)
        if instance_id is None:
            return
        self.monitor.select_device(int(instance_id))
        self.settings.setValue("selectedControllerGuid",self.monitor.selected_guid)
        self.settings.setValue("selectedControllerName",self.monitor.active.name if self.monitor.active else "")
        self.device_refresh_timer.stop()
        self.refresh()
        self._show_page(self.home_page)

    def check_updates(self, automatic=False):
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        self.update_request_id += 1
        request_id=self.update_request_id
        if hasattr(self, "check_button"):
            self.check_button.setEnabled(False)
            self.check_button.setVisible(True)
        if hasattr(self, "release_button"): self.release_button.setVisible(False)
        if hasattr(self, "install_update_button"): self.install_update_button.setVisible(False)
        if not automatic and hasattr(self, "update_status"): self.update_status.setText("Checking GitHub releases…")
        self.update_checked=False; self.update_timed_out=False
        worker=UpdateCheckWorker(self); self.update_worker=worker; self.update_workers.append(worker)
        worker.result.connect(lambda tag,url,detail,exe,sha,rid=request_id,w=worker,a=automatic:
            self.on_update_result_for_request(rid,w,tag,url,detail,exe,sha,a))
        worker.finished.connect(lambda w=worker: self._cleanup_update_worker(w))
        self.update_timeout_timer.start(); worker.start()

    def _cleanup_update_worker(self, worker):
        if worker in self.update_workers: self.update_workers.remove(worker)

    def on_update_timeout(self):
        worker=self.update_worker
        if worker is None: return
        if worker.isRunning():
            self.update_timed_out=True; worker.requestInterruption(); self.update_worker=None
            if hasattr(self, "check_button"):
                self.check_button.setEnabled(True)
                self.check_button.setVisible(True)
            if hasattr(self, "update_status"): self.update_status.setText("GitHub did not respond within 7 seconds. Check your connection or retry.")
            self.update_checked=True

    def on_update_result_for_request(self,request_id,worker,tag,url,detail,exe_url,sha_url,automatic=False):
        if request_id != self.update_request_id or worker is not self.update_worker: return
        self.update_timeout_timer.stop()
        if hasattr(self, "check_button"): self.check_button.setEnabled(True)
        self.update_checked=True
        if not tag:
            if hasattr(self, "check_button"): self.check_button.setVisible(True)
            if not automatic and hasattr(self, "update_status"): self.update_status.setText(detail or "Unable to check GitHub releases. Try again.")
            self.update_worker=None; return
        self.latest_release_url=url if url.startswith("https://github.com/") else GITHUB_RELEASES_PAGE
        self.latest_release_tag=re.sub(r"^[vV]+", "", tag.strip())
        self.latest_exe_url=exe_url; self.latest_sha_url=sha_url
        latest=version_tuple(self.latest_release_tag); current=version_tuple(APP_VERSION)
        if latest>current:
            self.update_status.setText(f"Update available: v{self.latest_release_tag} (installed: v{APP_VERSION}).")
            self.release_button.setVisible(True)
            if hasattr(self, "install_update_button"):
                self.install_update_button.setVisible(True)
            if hasattr(self, "check_button"):
                self.check_button.setVisible(False)
            self.pending_update_prompt = True
            self._maybe_show_update_prompt()
        elif latest==current:
            if hasattr(self, "update_status"): self.update_status.setText(f"You're up to date — v{APP_VERSION}.")
        else:
            if hasattr(self, "update_status"): self.update_status.setText(f"You're running v{APP_VERSION}, newer than the latest published release v{self.latest_release_tag}. This is a development build.")
        self.update_worker=None

    def _maybe_show_update_prompt(self):
        if not self.pending_update_prompt or self.update_prompt_deferred:
            return
        if bool(self.settings.value("disableUpdatePrompts", False, type=bool)):
            self.pending_update_prompt = False
            return
        # Keep the startup update check silent while the app is tray-only.
        # Present the prompt only while the main popover view is open.
        if not self.isVisible() or self.pages.currentWidget() is not self.home_page:
            return

        self.pending_update_prompt = False
        prompt = UpdatePromptDialog(self.latest_release_tag, self)
        prompt_result = prompt.exec()
        if prompt.do_not_ask.isChecked():
            self.settings.setValue("disableUpdatePrompts", True)
        if prompt_result == QDialog.DialogCode.Accepted and prompt.choice == "update":
            self.begin_auto_update()
        else:
            # Remind me later means the next popover opening, not immediately.
            self.update_prompt_deferred = True

    def begin_auto_update(self):
        if not getattr(sys,"frozen",False) or os.name!="nt":
            QMessageBox.information(self,APP_NAME,"Automatic replacement is available in the compiled Windows EXE. For a source run, download the release manually.")
            return
        self.update_status.setText("Downloading and verifying update…")
        self.check_button.setEnabled(False)
        self.update_download_worker=UpdateDownloadWorker(self.latest_exe_url,self.latest_sha_url,self)
        self.update_download_worker.result.connect(self.finish_auto_update)
        self.update_download_worker.start()

    def finish_auto_update(self,success,value):
        self.check_button.setEnabled(True)
        if not success:
            QMessageBox.warning(self,APP_NAME,f"The update could not be installed.\n\n{value}")
            self.update_status.setText("Update failed. You can retry from About.")
            return
        current=os.path.abspath(sys.executable); downloaded=os.path.abspath(value)
        helper=os.path.join(tempfile.gettempdir(),f"XboxControllerHotkey-updater-{os.getpid()}.ps1")
        log_path=os.path.join(tempfile.gettempdir(),"XboxControllerHotkey-update.log")
        # The running EXE must exit before Windows can replace it. Stage beside
        # the target, verify the staged copy, then use a rename/rollback fallback
        # for filesystems where File.Replace is unavailable or denied.
        script=("param()\n"+
            "$ErrorActionPreference='Stop'\n"+
            f"$pidToWait={os.getpid()}\n$source='{downloaded.replace(chr(39), chr(39)*2)}'\n$target='{current.replace(chr(39), chr(39)*2)}'\n"+
            f"$log='{log_path.replace(chr(39), chr(39)*2)}'\n"+
            "$tmp=$target+'.new'\n$backup=$target+'.old'\n"+
            "function Write-UpdateLog($message) { Add-Content -LiteralPath $log -Value ('['+(Get-Date -Format o)+'] '+$message) }\n"+
            "try {\n"+
            "  Write-UpdateLog 'Updater started; waiting for application exit.'\n"+
            "  while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 250 }\n"+
            "  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Verified download is missing.' }\n"+
            "  $targetDir=Split-Path -Parent $target\n"+
            "  if (-not (Test-Path -LiteralPath $targetDir -PathType Container)) { throw 'Application folder no longer exists.' }\n"+
            "  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue\n"+
            "  Copy-Item -LiteralPath $source -Destination $tmp -Force\n"+
            "  if (-not (Test-Path -LiteralPath $tmp -PathType Leaf)) { throw 'Could not stage the downloaded executable.' }\n"+
            "  if ((Get-Item -LiteralPath $tmp).Length -ne (Get-Item -LiteralPath $source).Length) { throw 'Staged executable size does not match the verified download.' }\n"+
            "  Write-UpdateLog 'New executable staged; beginning replacement.'\n"+
            "  $installed=$false\n"+
            "  for ($i=0; $i -lt 20 -and -not $installed; $i++) {\n"+
            "    try {\n"+
            "      if (Test-Path -LiteralPath $target -PathType Leaf) { [System.IO.File]::Replace($tmp,$target,$backup,$true) } else { [System.IO.File]::Move($tmp,$target) }\n"+
            "      $installed=$true\n"+
            "    } catch {\n"+
            "      Write-UpdateLog ('Atomic replace attempt '+($i+1)+' failed: '+$_.Exception.Message)\n"+
            "      if ($i -lt 19) { Start-Sleep -Milliseconds 500 }\n"+
            "    }\n"+
            "  }\n"+
            "  if (-not $installed) {\n"+
            "    Write-UpdateLog 'Atomic replace unavailable; trying backup-and-rename fallback.'\n"+
            "    if (Test-Path -LiteralPath $target -PathType Leaf) {\n"+
            "      Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue\n"+
            "      [System.IO.File]::Move($target,$backup)\n"+
            "    }\n"+
            "    try { [System.IO.File]::Move($tmp,$target); $installed=$true }\n"+
            "    catch {\n"+
            "      if ((Test-Path -LiteralPath $backup -PathType Leaf) -and -not (Test-Path -LiteralPath $target)) { [System.IO.File]::Move($backup,$target) }\n"+
            "      throw ('Replacement failed after fallback: '+$_.Exception.Message)\n"+
            "    }\n"+
            "  }\n"+
            "  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'Replacement reported success but the executable is missing.' }\n"+
            "  Write-UpdateLog 'Replacement succeeded; launching updated application.'\n"+
            "  Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue\n"+
            "  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue\n"+
            "  Start-Process -FilePath $target\n"+
            "  Start-Sleep -Seconds 3\n"+
            "  if (Get-Process -Name ([System.IO.Path]::GetFileNameWithoutExtension($target)) -ErrorAction SilentlyContinue) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue; Write-UpdateLog 'Updated app started successfully.' } else { Write-UpdateLog 'Updated app did not remain running; backup retained for recovery.' }\n"+
            "} catch {\n"+
            "  Write-UpdateLog ('UPDATE FAILED: '+($_ | Out-String))\n"+
            "  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue\n"+
            "  if (-not (Test-Path -LiteralPath $target -PathType Leaf) -and (Test-Path -LiteralPath $backup -PathType Leaf)) { [System.IO.File]::Move($backup,$target) }\n"+
            "  if (Test-Path -LiteralPath $target -PathType Leaf) { Start-Process -FilePath $target }\n"+
            "}\n")
        try:
            with open(helper,"w",encoding="utf-8") as f: f.write(script)
            subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",helper],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),close_fds=True)
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self,APP_NAME,f"Could not launch the updater: {exc}")

    def open_latest_release(self):
        QDesktopServices.openUrl(QUrl(self.latest_release_url))

    def open_about(self):
        if not self.isVisible():
            self.show_near_tray()
        self.show_about()

    def _open_page_after_tray_menu(self, page_callback):
        def show_page():
            if not self.isVisible():
                self.show_near_tray()
            page_callback()
        QTimer.singleShot(120, show_page)

    def open_shortcut_settings(self):
        self._open_page_after_tray_menu(self.show_shortcut_page)

    def open_controller_selection(self):
        self._open_page_after_tray_menu(self.show_controller_page)

    def _add_icon_button(self,layout,label,icon_file,callback):
        button=QPushButton(); button.setObjectName("actionButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(74); button.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        inner=QVBoxLayout(button); inner.setContentsMargins(3,3,3,3); inner.setSpacing(1)
        icon=QLabel(); icon.setFixedSize(36,30); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix=QPixmap()
        try:
            if icon_file.endswith(".b64"):
                with open(resource_path(os.path.join("assets",icon_file)),"r",encoding="ascii") as source:
                    pix.loadFromData(base64.b64decode(source.read().strip()))
            else:
                pix=QPixmap(resource_path(os.path.join("assets",icon_file)))
        except Exception:
            pass
        if not pix.isNull():
            icon.setPixmap(pix.scaled(QSize(30,30),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        icon.setStyleSheet("background:transparent;")
        text=QLabel(label.replace("\\n","\n")); text.setFixedHeight(30); text.setAlignment(Qt.AlignmentFlag.AlignCenter); text.setWordWrap(True)
        text.setStyleSheet("color:#FFFFFF;font-size:10px;font-weight:700;background:transparent;")
        inner.addWidget(icon,0,Qt.AlignmentFlag.AlignHCenter)
        inner.addWidget(text,0)
        button.clicked.connect(callback); layout.addWidget(button,1)
        return button

    def open_captures_folder(self):
        folder=capture_folder_path()
        try:
            os.makedirs(folder,exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(folder)):
                raise OSError("Windows could not open the Captures folder.")
        except Exception as exc:
            QMessageBox.warning(self,APP_NAME,f"Could not open the configured Captures folder.\\n\\n{exc}")

    def _detail_row(self, layout, label, value):
        row = QHBoxLayout()
        left = QLabel(label)
        left.setObjectName("section")
        right = QLabel(value)
        right.setObjectName("value")
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(left)
        row.addStretch()
        row.addWidget(right)
        layout.addLayout(row)
        return right

    def refresh(self):
        info = self.monitor.active
        self.controller_connected = info is not None
        if hasattr(self, "activity_graph"):
            self.activity_graph.setVisible(self.controller_connected and self.pages.currentWidget() is self.home_page)
        if info:
            family = controller_family(info.name)
            family_asset = os.path.join("assets", f"{family}-controller.png")
            family_pix = QPixmap(resource_path(family_asset))
            if not family_pix.isNull():
                self.controller_icon.setPixmap(family_pix.scaled(
                    QSize(190, 100), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                generic_pix = QPixmap(resource_path(os.path.join("assets", "controller-icon.png")))
                if not generic_pix.isNull():
                    self.controller_icon.setPixmap(generic_pix.scaled(
                        QSize(190, 100), Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
            self.state_dot.setStyleSheet("color:#00D451;font-size:10px;padding:0;margin:0;")
            self.state_text.setText("Connected")
            self.state_text.setStyleSheet("color:#00D451;font-size:12px;font-weight:650;")
            self.controller_icon.setStyleSheet("background:transparent;")
            self.controller_name.setText(info.name)
            self.controller_subtitle.setText("Controller detected and ready")
            self.battery_value.setText(info.battery)
        else:
            self.state_dot.setStyleSheet("color:#A7AFBB;font-size:10px;padding:0;margin:0;")
            self.state_text.setText("Disconnected")
            self.state_text.setStyleSheet("color:#B8C1CE;font-size:12px;font-weight:650;")
            self.controller_icon.setStyleSheet("background:transparent;")
            self.controller_name.setText("No controller detected")
            self.controller_subtitle.setText("Connect an Xbox controller to get started")
            self.battery_value.setText("Unavailable")

    def open_accessories(self):
        if os.name == "nt":
            try:
                result=ctypes.windll.shell32.ShellExecuteW(
                    None, "open", f"shell:AppsFolder\\{ACCESSORIES_AUMID}",
                    None, None, 1
                )
                if result > 32:
                    return
            except Exception:
                pass
        QMessageBox.information(
            self, "Xbox Accessories unavailable",
            "Windows could not launch Xbox Accessories. Make sure the app is installed from Microsoft Store."
        )

    def show_near_tray(self):
        self.pages.setCurrentWidget(self.home_page)
        self.refresh()
        self.adjustSize()
        rect = self.tray.geometry()
        if rect.isValid():
            screen = QApplication.screenAt(rect.center()) or QApplication.primaryScreen()
            available = screen.availableGeometry()
            x = rect.center().x() - self.width() // 2
            y = rect.top() - self.height() - 8
            if y < available.top():
                y = rect.bottom() + 8
            x = max(available.left() + 6, min(x, available.right() - self.width() - 6))
            y = max(available.top() + 6, min(y, available.bottom() - self.height() - 6))
            self.move(QPoint(x, y))
        else:
            screen = QApplication.primaryScreen()
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 12, geo.bottom() - self.height() - 12)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.update_prompt_deferred = False
        self._maybe_show_update_prompt()


class XInputHotkeyWorker(threading.Thread):
    """Dedicated low-latency XInput poller for Xbox controllers during gameplay."""
    def __init__(self, monitor, log_callback, activity_callback=None, record_callback=None):
        super().__init__(name="XboxControllerHotkey-XInput", daemon=True)
        self.monitor = monitor
        self.log_callback = log_callback
        self.activity_callback = activity_callback or (lambda value: None)
        self.record_callback = record_callback or (lambda: None)
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        # Slightly favor the input poller without raising the whole app's priority.
        if os.name == "nt":
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.GetCurrentThread.restype = wintypes.HANDLE
                kernel32.SetThreadPriority(kernel32.GetCurrentThread(), 1)  # ABOVE_NORMAL
            except Exception:
                pass

        previous_controls = None
        previous_combo = False
        was_connected = False
        if self.monitor._xinput_get_state is None:
            self.log_callback("XInput API unavailable; Xbox controller hotkey polling cannot start.")
        else:
            self.log_callback("XInput background poller started (125 Hz).")
        while not self.stop_event.is_set():
            try:
                controls = self.monitor.xinput_pressed_controls()
                self.activity_callback(self.monitor.xinput_activity_level())
                if controls is None:
                    if was_connected:
                        self.log_callback("XInput controller disconnected.")
                    was_connected = False
                    previous_controls = None
                    previous_combo = False
                    self.stop_event.wait(0.008)
                    continue

                if not was_connected:
                    self.log_callback("XInput controller connected; monitoring controller buttons.")
                was_connected = True
                self.monitor.last_pressed_controls = controls
                if controls != previous_controls:
                    self.log_callback(f"XInput controls: {sorted(controls)}")
                    previous_controls = set(controls)

                if self.monitor.capture_mode:
                    combo = False
                else:
                    configured = tuple(self.monitor.shortcut_controls)
                    combo = len(configured) >= 2 and all(
                        control in controls for control in configured
                    )

                if combo and not previous_combo:
                    self.log_callback(
                        f"XInput shortcut matched ({self.monitor.shortcut_controls}); sending Win+Alt+G"
                    )
                    self.record_callback()
                    send_game_bar_record_that()

                previous_combo = bool(combo)
            except Exception as exc:
                self.log_callback(f"XInput poll error: {exc!r}")
                previous_combo = False

            self.stop_event.wait(0.008)



class ConnectionToast(QWidget):
    """Five-second, dismissible controller-status notification."""
    def __init__(self, app, tray=None):
        super().__init__(None, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.app = app
        self.tray = tray
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(360, 104)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fade_animation.setDuration(220)
        self.fade_animation.finished.connect(self.hide)

        shell = QFrame(self)
        shell.setObjectName("toastShell")
        shell.setGeometry(0, 0, 360, 104)
        shell.setStyleSheet("""
            QFrame#toastShell {
                background: #17191F;
                border: 1px solid #343943;
                border-radius: 13px;
            }
            QLabel#toastTitle {
                color: #F4F6F8;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: 0;
            }
            QLabel#toastBody {
                color: #C7CDD6;
                font-size: 12px;
                background: transparent;
                border: 0;
            }
        """)

        layout = QHBoxLayout(shell)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: 0;")
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("toastTitle")
        self.body_label = QLabel()
        self.body_label.setObjectName("toastBody")
        self.body_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.body_label)
        layout.addLayout(text_layout, 1)

        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(22, 22)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip("Close notification")
        self.close_button.setStyleSheet(
            "QPushButton{color:#AEB7C4;background:transparent;border:0;"
            "font-size:20px;font-weight:400;padding:0;margin:0;}"
            "QPushButton:hover{color:#FFFFFF;}"
        )
        self.close_button.clicked.connect(self.fade_out)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)

    def fade_out(self):
        self.hide_timer.stop()
        self.fade_animation.stop()
        if not self.isVisible():
            return
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

    def show_status(self, connected, device_name="", initial=False):
        icon = make_tray_icon(bool(connected)).pixmap(42, 42)
        self.icon_label.setPixmap(icon)
        if connected:
            self.body_label.setText(f"{device_name} connected. Your controller is ready.")
        elif initial:
            self.body_label.setText("No controller detected.\nAwaiting connection...")
        else:
            self.body_label.setText("Controller disconnected.\nAwaiting connection...")
        self.hide_timer.stop()
        self.fade_animation.stop()
        self.opacity_effect.setOpacity(1.0)
        self._position_near_taskbar()
        self.show()
        self.raise_()
        # Every controller-status notification has the same five-second lifetime.
        self.hide_timer.start(5000)

    def _position_near_taskbar(self):
        # Anchor the toast to the notification-area icon. availableGeometry()
        # can extend beneath an auto-hidden taskbar while it is sliding out.
        tray_rect = self.tray.geometry() if self.tray is not None else QRect()
        screen = (self.app.screenAt(tray_rect.center()) if tray_rect.isValid()
                  else self.app.primaryScreen())
        if screen is None:
            return

        bounds = screen.geometry()
        area = screen.availableGeometry()
        if tray_rect.isValid():
            # Keep the toast outside the system-tray area. For a bottom
            # taskbar, show above the tray; for a top taskbar, show below it.
            above = tray_rect.center().y() >= bounds.center().y()
            y = (tray_rect.top() - self.height() - 10 if above
                 else tray_rect.bottom() + 10)
            x = tray_rect.left() - self.width() - 12
            if x < bounds.left() + 8:
                x = tray_rect.right() + 12
            x = max(bounds.left() + 8, min(x, bounds.right() - self.width() - 8))
            y = max(bounds.top() + 8, min(y, bounds.bottom() - self.height() - 8))
            self.move(x, y)
            return

        # Fallback until Windows exposes the tray icon's screen rectangle.
        x = area.right() - self.width() - 12
        y = area.bottom() - self.height() - 12
        self.move(max(area.left(), x), max(area.top(), y))


class TrayApplication:
    def __init__(self, app: QApplication):
        self.app = app
        self.settings = QSettings("JimHatesYou", APP_NAME)
        self.monitor = ControllerMonitor()
        self.monitor.preferred_guid = str(
            self.settings.value("selectedControllerGuid", self.settings.value("controllerGuid", "")) or ""
        )
        stored_controls = self.settings.value("shortcutControls", None)
        if stored_controls:
            self.monitor.shortcut_controls = [str(x) for x in stored_controls]
        else:
            stored_shortcut = self.settings.value("shortcutButtons", DEFAULT_SHORTCUT)
            try:
                self.monitor.shortcut_controls = [f"button:{int(x)}" for x in stored_shortcut]
            except Exception:
                self.monitor.shortcut_controls = [f"button:{b}" for b in DEFAULT_SHORTCUT]
        self.tray = QSystemTrayIcon(make_tray_icon(False), app)
        self.tray.setToolTip(self.tray_tooltip_text(None))
        self.connection_toast = ConnectionToast(app, self.tray)
        self.input_activity = 0.0
        self.popover = StatusPopover(self.monitor, self.tray, self.settings)
        self.popover.activity_source = lambda: self.input_activity
        self.clip_count = int(self.settings.value("lifetimeClipCount",0,type=int))
        self.pending_capture_triggers = [float(x) for x in (self.settings.value("pendingCaptureTriggers",[]) or [])]
        self.capture_trigger_lock = threading.Lock()
        self.known_capture_files = {os.path.normcase(os.path.abspath(path)) for path,created,size in self._capture_files() if not any(-3 <= created-trigger <= 180 for trigger in self.pending_capture_triggers)}
        self.capture_file_states = {}
        self._counted_capture_files = set(self.settings.value("countedCaptureFiles",[]) or [])
        self.popover.clip_count_value.setText(str(self.clip_count))
        self.capture_scan_timer = QTimer()
        self.capture_scan_timer.setInterval(2000)
        self.capture_scan_timer.timeout.connect(self.scan_capture_files)
        self.capture_scan_timer.start()
        self.last_connected = False
        self.has_checked_connection = False
        self.last_logged_controls = set()
        self.battery_timer = QTimer()
        self.battery_timer.setInterval(5 * 60 * 1000)
        self.battery_timer.timeout.connect(self.refresh_battery)
        self._build_tray_menu()
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        # Xbox pads use a dedicated XInput thread, independent of the UI loop.
        self.xinput_worker = XInputHotkeyWorker(self.monitor, self._write_input_log,
                                                self.set_input_activity, self.note_record_that_trigger)
        self.xinput_worker.start()

        # SDL fallback poll for supported non-XInput controllers (PlayStation/Switch).
        self.input_timer = QTimer()
        self.input_timer.setInterval(8)
        self.input_timer.timeout.connect(self.poll_input)
        self.input_timer.start()

        # Controller enumeration can block inside SDL/Windows. Never run it
        # on the UI thread. A single worker scans every 2.5 seconds and skips
        # a tick if the previous scan is still running.
        self.scan_worker = None
        self.monitor_timer = QTimer()
        self.monitor_timer.setInterval(2500)
        self.monitor_timer.timeout.connect(self.start_connection_scan)
        self.start_connection_scan()
        self.monitor_timer.start()
        if not bool(self.settings.value("disableStartupUpdateChecks", False, type=bool)):
            QTimer.singleShot(6500, lambda: self.popover.check_updates(automatic=True))

    def _build_tray_menu(self):
        menu = QMenu()
        open_action = menu.addAction("Open")
        open_action.triggered.connect(self.toggle_popover)
        configure_action = menu.addAction("Select Controller")
        configure_action.triggered.connect(self.popover.open_controller_selection)
        capture_action = menu.addAction("Configure Capture Settings")
        capture_action.triggered.connect(open_capture_settings)
        shortcut_action = menu.addAction("Configure Record That Shortcut")
        shortcut_action.triggered.connect(self.popover.open_shortcut_settings)
        about_action = menu.addAction("About")
        about_action.triggered.connect(self.popover.open_about)
        menu.addSeparator()
        self.startup_action = menu.addAction("Start with Windows")
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(is_startup_enabled())
        self.startup_action.toggled.connect(self.toggle_startup)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)

    def toggle_startup(self, enabled):
        if set_startup_enabled(enabled):
            self.settings.setValue("startWithWindows", bool(enabled))
        else:
            self.startup_action.blockSignals(True)
            self.startup_action.setChecked(not enabled)
            self.startup_action.blockSignals(False)
            QMessageBox.warning(
                None, APP_NAME,
                "Windows could not update the per-user startup setting."
            )

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_popover()

    def toggle_popover(self):
        if self.popover.isVisible():
            self.popover.hide()
        else:
            self.popover.show_near_tray()

    def tray_tooltip_text(self, info):
        """Build a compact one-line Windows tray tooltip."""
        version_label = f"{APP_NAME} v{APP_VERSION}"
        if info is None:
            return f"{version_label} | Disconnected | Not ready"
        device_name = " ".join(str(info.name).split())
        if len(device_name) > 25:
            device_name = device_name[:22].rstrip() + "..."
        battery = " ".join(str(info.battery).split())
        if battery.lower() in ("", "unavailable", "unknown"):
            battery = "N/A"
        return f"{version_label} | {device_name} | Battery: {battery} | Ready"

    def start_connection_scan(self):
        worker = self.scan_worker
        if worker is not None and worker.isRunning():
            return
        worker = ControllerScanWorker(self.monitor)
        self.scan_worker = worker
        worker.scan_finished.connect(self.apply_connection_scan)
        worker.finished.connect(lambda w=worker: self._connection_scan_finished(w))
        worker.start()

    def _connection_scan_finished(self, worker):
        if self.scan_worker is worker:
            self.scan_worker = None
        worker.deleteLater()

    def apply_connection_scan(self, info):
        connected = info is not None
        # Keep both icon channels synchronized. QSystemTrayIcon controls the
        # taskbar tray glyph, while QApplication's window icon is also used
        # by Windows/Qt when branding native tray notifications.
        status_icon = make_tray_icon(connected)
        self.tray.setIcon(status_icon)
        self.app.setWindowIcon(status_icon)
        self.tray.setToolTip(self.tray_tooltip_text(info))
        self.popover.refresh()

        if connected and not self.last_connected:
            # Clear a persistent startup/disconnected notice before showing the
            # connected notification after the tray icon has refreshed.
            self.connection_toast.hide()
            # Windows may display the notification before the Explorer tray
            # finishes repainting the changed icon. Delay the toast briefly.
            connected_name = info.name
            QTimer.singleShot(
                1000,
                lambda name=connected_name: self.show_connected_notification(name)
            )
            self.battery_timer.stop()
            QTimer.singleShot(1000, self.refresh_battery)
            self.battery_timer.start()
        elif not connected and self.last_connected:
            self.battery_timer.stop()
            self.connection_toast.show_status(False)
        elif not connected and not self.has_checked_connection:
            # Give the user an explicit startup state instead of leaving them
            # unsure whether the app is running and waiting for a controller.
            self.connection_toast.show_status(False, initial=True)
        self.last_connected = connected
        self.has_checked_connection = True

    def show_connected_notification(self, device_name):
        info = self.monitor.active
        if not self.last_connected or info is None or info.name != device_name:
            return
        # Reassert the connected icon immediately before asking Windows to
        # create the notification. This avoids using a stale startup icon.
        connected_icon = make_tray_icon(True)
        self.tray.setIcon(connected_icon)
        self.app.setWindowIcon(connected_icon)
        self.connection_toast.show_status(True, device_name)

    def refresh_battery(self):
        if self.monitor.active is None:
            return
        self.monitor.refresh_battery()
        self.popover.refresh()
        info=self.monitor.active
        self.tray.setToolTip(self.tray_tooltip_text(info))

    def poll_input(self):
        try:
            # The dedicated worker owns Xbox/XInput hotkey detection.
            if self.monitor.xinput_pressed_controls() is not None:
                return
            triggered = self.monitor.poll_hotkey()
            controls = set(self.monitor.last_pressed_controls)
            if controls != self.last_logged_controls:
                self._write_input_log(f"controller controls: {sorted(controls)}")
                self.last_logged_controls = controls
            if triggered and GAME_BAR_RECORD_THAT:
                self._write_input_log(
                    f"shortcut matched ({self.monitor.shortcut_controls}); sending Win+Alt+G"
                )
                self.note_record_that_trigger()
                send_game_bar_record_that()
            level=0.72 if controls else 0.0
            try:
                for joystick in self.monitor.joysticks:
                    for axis_index in range(joystick.get_numaxes()):
                        axis_value=abs(float(joystick.get_axis(axis_index)))
                        level=max(level,max(0.0,min(1.0,(axis_value-0.12)/0.88)))
            except Exception:
                pass
            self.set_input_activity(level)
        except Exception as exc:
            self._write_input_log(f"poll error: {exc!r}")

    def set_input_activity(self,value):
        self.input_activity=max(0.0,min(1.0,float(value)))

    def _capture_files(self):
        folder=capture_folder_path()
        files=[]
        if not os.path.isdir(folder): return files
        try:
            for root,dirs,names in os.walk(folder):
                dirs[:]=[d for d in dirs if d.lower() not in ("thumbnails","temp")]
                for name in names:
                    if os.path.splitext(name)[1].lower() in (".mp4",".mkv",".mov"):
                        path=os.path.join(root,name)
                        try: files.append((path,os.path.getctime(path),os.path.getsize(path)))
                        except OSError: pass
        except OSError: pass
        return files

    def note_record_that_trigger(self):
        # Called by the 125 Hz input worker; only append under a lock here.
        # QSettings writes are kept on the Qt/UI thread in scan_capture_files().
        now=time.time()
        with self.capture_trigger_lock:
            self.pending_capture_triggers=[t for t in self.pending_capture_triggers if now-t<180]
            self.pending_capture_triggers.append(now)

    def scan_capture_files(self):
        now=time.time()
        with self.capture_trigger_lock:
            self.pending_capture_triggers=[t for t in self.pending_capture_triggers if now-t<180]
            pending=list(self.pending_capture_triggers)
        for path,created,size in self._capture_files():
            normalized=os.path.normcase(os.path.abspath(path))
            if normalized in self.known_capture_files or normalized in self._counted_capture_files: continue
            matching=next((t for t in pending if -3<=created-t<=180),None)
            if matching is None:
                self.known_capture_files.add(normalized)
                continue
            previous=self.capture_file_states.get(normalized)
            stable=previous[1]+1 if previous and previous[0]==size else 0
            self.capture_file_states[normalized]=(size,stable,created)
            if stable>=2:
                self.clip_count+=1
                self.settings.setValue("lifetimeClipCount",self.clip_count)
                self._counted_capture_files.add(normalized)
                self.settings.setValue("countedCaptureFiles",list(self._counted_capture_files)[-5000:])
                with self.capture_trigger_lock:
                    if matching in self.pending_capture_triggers:
                        self.pending_capture_triggers.remove(matching)
                    pending=list(self.pending_capture_triggers)
                self.popover.clip_count_value.setText(str(self.clip_count))
                self.known_capture_files.add(normalized)
                self.capture_file_states.pop(normalized,None)
        with self.capture_trigger_lock:
            pending=list(self.pending_capture_triggers)
        self.settings.setValue("pendingCaptureTriggers",pending)

    def _write_input_log(self, message):
        try:
            import tempfile
            log_dir = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
                                   APP_NAME)
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "input.log"), "a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\\n")
        except Exception:
            pass

    def quit(self):
        self.input_timer.stop()
        self.capture_scan_timer.stop()
        self.xinput_worker.stop()
        self.xinput_worker.join(timeout=1.0)
        self.monitor_timer.stop()
        self.battery_timer.stop()
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.scan_worker.wait(1500)
        self.connection_toast.hide()
        self.tray.hide()
        self.monitor.close()
        self.app.quit()


# Keep one process per interactive Windows session. The kernel automatically
# releases this mutex if the process exits or crashes.
_SINGLE_INSTANCE_MUTEX_HANDLE = None
_SINGLE_INSTANCE_MUTEX_NAME = r"Local\XboxControllerHotkey_V2_SingleInstance"


def acquire_single_instance():
    """Return True only for the first running instance of this application."""
    global _SINGLE_INSTANCE_MUTEX_HANDLE
    if os.name != "nt":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    create_mutex.restype = wintypes.HANDLE

    handle = create_mutex(None, False, _SINGLE_INSTANCE_MUTEX_NAME)
    if not handle:
        # Distinguish a mutex API failure from an existing application instance.
        return None

    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle(handle)
        return False

    _SINGLE_INSTANCE_MUTEX_HANDLE = handle
    return True


def main():
    if os.name != "nt":
        print("XboxControllerHotkey V2 is designed for Windows 10/11.")
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    instance_result = acquire_single_instance()
    if instance_result is False:
        # Show feedback to the user, then exit without starting a second tray app.
        QMessageBox.information(
            None,
            APP_NAME,
            "Another instance of this program is already running.",
            QMessageBox.StandardButton.Ok,
        )
        return 0
    if instance_result is None:
        QMessageBox.critical(
            None,
            APP_NAME,
            "Windows could not check whether another instance is running.\n\n"
            "The application will close to avoid starting duplicate controller monitoring.",
            QMessageBox.StandardButton.Ok,
        )
        return 1
    app.setWindowIcon(QIcon(resource_path(os.path.join("assets", "controller-icon.png"))))
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    settings = QSettings("JimHatesYou", APP_NAME)
    if not settings.value("firstLaunchNoticeAcknowledged", False, type=bool):
        notice = FirstLaunchNotice()
        notice_result = notice.exec()
        if notice_result != QDialog.DialogCode.Accepted:
            return 0
        settings.setValue("firstLaunchNoticeAcknowledged", True)

    if not settings.value("setupComplete", False, type=bool):
        setup_monitor = ControllerMonitor()
        setup = FirstRunSetup(setup_monitor, settings)
        result = setup.exec()
        setup_monitor.close()
        if result != QDialog.DialogCode.Accepted:
            return 0
    tray_app = TrayApplication(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
