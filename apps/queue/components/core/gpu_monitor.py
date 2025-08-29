"""
GPU情報監視モジュール
"""

from typing import Optional, Dict, Any


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """現在のGPU情報を取得

    Returns:
        Dict: GPU情報（使用率、VRAM、温度）またはNone（エラー時）
    """
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # GPU使用率
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_usage = util.gpu

        # VRAM情報
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_used_mb = mem_info.used // (1024 * 1024)
        vram_total_mb = mem_info.total // (1024 * 1024)
        vram_percent = (mem_info.used / mem_info.total) * 100

        # 温度情報
        try:
            temperature = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except pynvml.NVMLError:
            temperature = None

        pynvml.nvmlShutdown()

        return {
            "gpu_usage": gpu_usage,
            "vram_used_mb": vram_used_mb,
            "vram_total_mb": vram_total_mb,
            "vram_percent": vram_percent,
            "temperature": temperature,
        }

    except ImportError:
        # pynvmlがインストールされていない
        return None
    except Exception:
        # NVIDIA GPU以外またはその他のエラー
        return None


def format_gpu_info_for_slack(gpu_info: Optional[Dict[str, Any]]) -> str:
    """GPU情報をSlack通知用にフォーマット

    Args:
        gpu_info: GPU情報の辞書

    Returns:
        str: フォーマット済みの文字列
    """
    if gpu_info is None:
        return ""

    # 基本情報
    gpu_text = f"GPU: {gpu_info['gpu_usage']}% | VRAM: {gpu_info['vram_used_mb']:,}MB/{gpu_info['vram_total_mb']:,}MB ({gpu_info['vram_percent']:.1f}%)"

    # 温度情報
    if gpu_info["temperature"] is not None:
        temp = gpu_info["temperature"]
        # 温度による絵文字の選択
        if temp >= 85:
            temp_emoji = "🚨"  # 危険
        elif temp >= 80:
            temp_emoji = "🔥"  # 警告
        else:
            temp_emoji = "❄️"  # 正常

        gpu_text += f" | 温度: {temp}°C {temp_emoji}"

    return gpu_text


def is_gpu_available() -> bool:
    """NVIDIA GPUが利用可能かチェック

    Returns:
        bool: 利用可能な場合True
    """
    try:
        import pynvml

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        pynvml.nvmlShutdown()
        return device_count > 0
    except Exception:
        return False
