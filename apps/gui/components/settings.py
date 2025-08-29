"""
UI設定管理ユーティリティ
"""

import json
import os
from datetime import datetime
from typing import Dict, Any


SETTINGS_FILE = "ui_settings.json"


def load_settings() -> Dict[str, Any]:
    """UI設定の読み込み"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"font_size": 14}


def save_settings(font_size: int) -> None:
    """UI設定の保存"""
    settings = {"font_size": font_size, "saved_at": datetime.now().isoformat()}
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
