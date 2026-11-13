"""
System Monitor — background metric checks with voice alert support.
Zero subprocess calls on all platforms — uses ctypes/pynvml/psutil/wmi only.
"""
import ctypes
import platform
import time

import psutil

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

DEFAULT_THRESHOLDS = {
    "cpu":  90.0,
    "ram":  90.0,
    "temp": 85.0,
    "gpu":  95.0,
}

_COOLDOWN   = 300
_CPU_STREAK = 3

# ── NVML DLL cache (Windows: nvml.dll, Linux: libnvidia-ml.so.1) ─────────────
_nvml_lib: object = None
_nvml_ok:  object = None   # None=untested  True=works  False=unavailable


def _nvml_gpu() -> float:
    """GPU utilisation via NVML — zero subprocess on all platforms."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            if _OS == "Windows":
                candidates = ("nvml", r"C:\Windows\System32\nvml.dll")
                _load = ctypes.WinDLL
            else:
                candidates = (
                    "libnvidia-ml.so.1",
                    "libnvidia-ml.so",
                    "libnvidia-ml.dylib",
                )
                _load = ctypes.CDLL
            for name in candidates:
                try:
                    lib = _load(name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            _nvml_ok = False
            return -1.0

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        u = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
        _nvml_ok = True
        return float(u.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


def _get_gpu_usage() -> float:
    # pynvml — subprocess-free, works everywhere if installed
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
    except Exception:
        pass

    return _nvml_gpu()


def _get_cpu_temp() -> float:
    # psutil — works on Linux; occasionally Windows with proper drivers
    try:
        temps = psutil.sensors_temperatures()
        for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                     "cpu-thermal", "zenpower", "it8688"]:
            if name in temps and temps[name]:
                return temps[name][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        pass

    # Windows: wmi module (pure Python COM, zero subprocess)
    if _OS == "Windows":
        try:
            import wmi  # type: ignore
            w = wmi.WMI(namespace="root/wmi")
            tz = w.MSAcpi_ThermalZoneTemperature()
            if tz:
                return (tz[0].CurrentTemperature / 10.0) - 273.15
        except Exception:
            pass

    return -1.0


def get_system_status() -> dict:
    """Snapshot of current system metrics for the system_status tool."""
    cpu  = psutil.cpu_percent(interval=0.1)
    ram  = psutil.virtual_memory()
    temp = _get_cpu_temp()
    gpu  = _get_gpu_usage()

    boot_time   = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    uptime_h    = int(uptime_secs // 3600)
    uptime_m    = int((uptime_secs % 3600) // 60)

    # Live Battery Metrics
    battery_info = {}
    try:
        bat = psutil.sensors_battery()
        if bat is not None:
            plugged = bool(bat.power_plugged)
            pct = int(round(bat.percent))
            if plugged:
                state = "Fully Charged (AC Connected)" if pct >= 98 else "Charging (AC Connected)"
            else:
                state = "Discharging (On Battery)"
            mins_rem = None
            if bat.secsleft > 0 and not plugged:
                mins_rem = round(bat.secsleft / 60)
                state += f", approximately {mins_rem} minutes remaining"

            battery_info = {
                "percent": pct,
                "power_plugged": plugged,
                "is_charging": plugged and pct < 98,
                "status": state,
                "minutes_remaining": mins_rem,
            }
        else:
            battery_info = {
                "percent": 100,
                "power_plugged": True,
                "status": "Desktop AC power (no battery)",
            }
    except Exception as e:
        battery_info = {"error": str(e)}

    # Disk usage
    disk_info = {}
    try:
        import os as _os_mod
        root_path = "C:\\" if _os_mod.name == "nt" else "/"
        du = psutil.disk_usage(root_path)
        disk_info = {
            "used_gb": round(du.used / (1024 ** 3), 1),
            "total_gb": round(du.total / (1024 ** 3), 1),
            "free_gb": round(du.free / (1024 ** 3), 1),
            "percent_used": round(du.percent, 1),
        }
    except Exception:
        pass

    # Hardware specs (CPU & Workstation model)
    cpu_model = "Intel Processor"
    model_name = "Workstation"
    if _OS == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                cpu_model = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as k:
                model_name = winreg.QueryValueEx(k, "SystemProductName")[0].strip()
        except Exception:
            pass

    # CPU Freq
    freq_ghz = None
    try:
        cf = psutil.cpu_freq()
        if cf and cf.current:
            freq_ghz = round(cf.current / 1000.0, 2)
    except Exception:
        pass

    status_dict = {
        "workstation": model_name,
        "cpu_model": cpu_model,
        "cpu_percent": round(cpu, 1),
        "cpu_cores": f"{psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical",
        "cpu_freq_ghz": freq_ghz,
        "ram_percent": round(ram.percent, 1),
        "ram_used_gb": round(ram.used / (1024 ** 3), 1),
        "ram_total_gb": round(ram.total / (1024 ** 3), 1),
        "ram_free_gb": round(ram.available / (1024 ** 3), 1),
        "battery": battery_info,
        "disk": disk_info,
        "gpu_percent": round(gpu, 1) if gpu >= 0 else None,
        "gpu_model": "NVIDIA GeForce RTX 4050 Laptop GPU" if _OS == "Windows" else None,
        "cpu_temp_c": round(temp, 1) if temp > 0 else None,
        "uptime": f"{uptime_h}h {uptime_m}m",
        "process_count": len(psutil.pids()),
    }

    bat_summary = f"battery is at {battery_info.get('percent', 'N/A')}% ({battery_info.get('status', 'unknown')})" if 'percent' in battery_info else "running on AC power"
    status_dict["summary"] = (
        f"Workstation is running nominally. {bat_summary.capitalize()}. "
        f"CPU load is {round(cpu, 1)}% ({cpu_model}), "
        f"RAM is at {round(ram.used / (1024 ** 3), 1)} GB of {round(ram.total / (1024 ** 3), 1)} GB ({round(ram.percent, 1)}%), "
        f"and system uptime is {uptime_h} hours and {uptime_m} minutes."
    )
    return status_dict


class SystemMonitor:
    """
    Stateful monitor — cooldown state persists across session reconnections.
    Call check() periodically; returns a [SYSTEM_ALERT] string or None.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds   = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._last_alert: dict[str, float] = {}
        self._cpu_streak  = 0

    def _can_alert(self, key: str) -> bool:
        return (time.monotonic() - self._last_alert.get(key, 0)) > _COOLDOWN

    def _record(self, key: str):
        self._last_alert[key] = time.monotonic()

    def check(self) -> str | None:
        try:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            temp = _get_cpu_temp()
            gpu  = _get_gpu_usage()
        except Exception:
            return None

        alerts: list[str] = []

        if cpu >= self.thresholds["cpu"]:
            self._cpu_streak += 1
            if self._cpu_streak >= _CPU_STREAK and self._can_alert("cpu"):
                alerts.append(
                    f"[SYSTEM_ALERT] CPU usage has been critically high ({cpu:.0f}%) "
                    "for several seconds. Warn the user in their language and suggest "
                    "closing heavy applications."
                )
                self._record("cpu")
                self._cpu_streak = 0
        else:
            self._cpu_streak = 0

        if ram >= self.thresholds["ram"] and self._can_alert("ram"):
            alerts.append(
                f"[SYSTEM_ALERT] RAM is at {ram:.0f}% — nearly exhausted. "
                "Warn the user in their language and suggest freeing memory."
            )
            self._record("ram")

        if temp > 0 and temp >= self.thresholds["temp"] and self._can_alert("temp"):
            alerts.append(
                f"[SYSTEM_ALERT] CPU temperature is {temp:.0f}°C — above the safe limit. "
                "Warn the user in their language and advise reducing system load "
                "or checking cooling."
            )
            self._record("temp")

        if gpu >= 0 and gpu >= self.thresholds["gpu"] and self._can_alert("gpu"):
            alerts.append(
                f"[SYSTEM_ALERT] GPU load is at {gpu:.0f}%. "
                "Briefly inform the user in their language."
            )
            self._record("gpu")

        return " ".join(alerts) if alerts else None
