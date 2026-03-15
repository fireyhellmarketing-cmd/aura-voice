"""AURA VOICE — Hardware detection for model compatibility."""

import platform
import subprocess
from dataclasses import dataclass, field
from typing import List


@dataclass
class HardwareInfo:
    platform: str           # "darwin", "windows", "linux"
    cpu_name: str
    ram_gb: float
    has_cuda: bool
    cuda_version: str       # "" if none
    gpu_name: str           # "" if none
    vram_gb: float          # 0.0 if no GPU
    has_mps: bool           # True on Apple Silicon with MPS
    recommended_device: str # "cuda", "mps", or "cpu"
    device_label: str       # Human-readable device description


def _get_cpu_name() -> str:
    """Retrieve a human-readable CPU name."""
    sys = platform.system()
    try:
        if sys == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            name = result.stdout.strip()
            if name:
                return name
        elif sys == "Windows":
            result = subprocess.run(
                ["wmic", "cpu", "get", "Name", "/value"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "Name=" in line:
                    return line.split("=", 1)[1].strip()
        else:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line.lower():
                        return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"


def _get_ram_gb() -> float:
    """Return total system RAM in gigabytes."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        pass

    sys = platform.system()
    try:
        if sys == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            return round(int(result.stdout.strip()) / (1024 ** 3), 1)
        elif sys == "Linux":
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
        elif sys == "Windows":
            result = subprocess.run(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "TotalPhysicalMemory=" in line:
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return round(int(val) / (1024 ** 3), 1)
    except Exception:
        pass
    return 8.0  # fallback assumption


def _probe_torch_cuda():
    """Return (has_cuda, cuda_version, gpu_name, vram_gb) using torch."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = round(vram_bytes / (1024 ** 3), 1)
            cuda_ver = torch.version.cuda or ""
            return True, cuda_ver, gpu_name, vram_gb
        return False, "", "", 0.0
    except Exception:
        return False, "", "", 0.0


def _probe_torch_mps() -> bool:
    """Return True if Apple MPS is available."""
    try:
        import torch
        return (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
            and torch.backends.mps.is_built()
        )
    except Exception:
        return False


def _probe_gpu_nvidia_smi():
    """Fallback: probe CUDA/GPU using nvidia-smi if torch not installed."""
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_name = parts[0].strip() if len(parts) > 0 else "NVIDIA GPU"
            vram_mb = float(parts[1].strip()) if len(parts) > 1 else 0
            return True, "", gpu_name, round(vram_mb / 1024, 1)
    except Exception:
        pass
    return False, "", "", 0.0


def detect_hardware() -> HardwareInfo:
    """
    Detect hardware capabilities and return a fully populated HardwareInfo.

    Detection order:
      1. Use torch (most accurate) if available
      2. Fall back to nvidia-smi for CUDA
      3. Fall back to platform/subprocess for CPU/RAM
    """
    sys = platform.system().lower()
    if sys == "darwin":
        plat = "darwin"
    elif sys == "windows":
        plat = "windows"
    else:
        plat = "linux"

    cpu_name = _get_cpu_name()
    ram_gb   = _get_ram_gb()

    # — CUDA probe —
    has_cuda, cuda_version, gpu_name, vram_gb = _probe_torch_cuda()
    if not has_cuda:
        has_cuda, cuda_version, gpu_name, vram_gb = _probe_gpu_nvidia_smi()

    # — MPS probe (Apple Silicon) —
    has_mps = False
    if plat == "darwin":
        has_mps = _probe_torch_mps()
        if has_mps and not gpu_name:
            # Try to get chip name as "GPU"
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5
                )
                chip = result.stdout.strip()
                gpu_name = chip if chip else "Apple Silicon GPU"
            except Exception:
                gpu_name = "Apple Silicon GPU"
            vram_gb = 0.0  # Shared memory; not separately reported

    # — Determine recommended device —
    if has_cuda:
        recommended_device = "cuda"
        device_label = f"NVIDIA CUDA  ({gpu_name})"
        if vram_gb:
            device_label += f"  {vram_gb} GB VRAM"
    elif has_mps:
        recommended_device = "mps"
        device_label = f"Apple MPS  ({gpu_name})"
    else:
        recommended_device = "cpu"
        device_label = f"CPU  ({cpu_name})"

    return HardwareInfo(
        platform=plat,
        cpu_name=cpu_name,
        ram_gb=ram_gb,
        has_cuda=has_cuda,
        cuda_version=cuda_version,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        has_mps=has_mps,
        recommended_device=recommended_device,
        device_label=device_label,
    )


if __name__ == "__main__":
    info = detect_hardware()
    print(f"Platform  : {info.platform}")
    print(f"CPU       : {info.cpu_name}")
    print(f"RAM       : {info.ram_gb} GB")
    print(f"CUDA      : {info.has_cuda}  ver={info.cuda_version}")
    print(f"GPU       : {info.gpu_name}  VRAM={info.vram_gb} GB")
    print(f"MPS       : {info.has_mps}")
    print(f"Device    : {info.recommended_device}  ({info.device_label})")
