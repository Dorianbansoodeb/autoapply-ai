"""OS, CPU architecture, and RAM. Used to warn, never to crash."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareReport:
    os: str
    arch: str
    ram_gb: float | None
    tier: str
    message: str


def detect_hardware() -> HardwareReport:
    system = platform.system() or "unknown"
    arch = platform.machine() or "unknown"
    ram = _ram_gb()
    if ram is None:
        tier = "unknown"
        message = "Could not read RAM. Use a small local model and stay in assisted mode."
    elif ram < 12:
        tier = "limited"
        message = (
            f"About {ram:.0f} GB RAM. Prep mode with a small (~3B) model only. "
            "Not for autonomous operation."
        )
    elif ram < 20:
        tier = "practical"
        message = f"About {ram:.0f} GB RAM. Practical floor for a 7–8B model plus the browser."
    else:
        tier = "comfortable"
        message = f"About {ram:.0f} GB RAM. Comfortable for a 7–8B model plus the browser."
    if system.lower() == "linux":
        message += " Linux is outside the v1 support target; the CLI may still run."
    return HardwareReport(os=system, arch=arch, ram_gb=ram, tier=tier, message=message)


def _ram_gb() -> float | None:
    if sys.platform == "win32":
        return _windows_ram_gb()
    try:
        pages = sysconf("SC_PHYS_PAGES")
        size = sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return None
    if not pages or not size:
        return None
    return (pages * size) / (1024**3)


def sysconf(name: str) -> int:
    import os

    return int(os.sysconf(name))


def _windows_ram_gb() -> float | None:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullTotalPhys / (1024**3)
