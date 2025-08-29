"""
プロセス管理ユーティリティ
キューシステムプロセスの起動、状態確認、終了制御を行う
"""

import json
import subprocess
import sys
import requests
from pathlib import Path
from typing import Optional, Dict, Any


class QueueProcessManager:
    """キューシステムプロセス管理クラス"""

    def __init__(self):
        # apps/gui/components/process_manager.py から プロジェクトルートまで4階層上
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.config_path = self.project_root / "data" / "config" / "queue_config.json"
        self.launch_script = self.project_root / "launch_queue.py"

    def load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"queue_system": {"default_port": 7862, "host": "127.0.0.1"}}

    def get_default_port(self) -> int:
        """設定ファイルからデフォルトポートを取得"""
        config = self.load_config()
        return config.get("queue_system", {}).get("default_port", 7862)

    def is_queue_system_running(self, port: Optional[int] = None) -> bool:
        """キューシステムが稼働中かチェック"""
        if port is None:
            port = self.get_default_port()

        try:
            response = requests.get(f"http://127.0.0.1:{port}", timeout=3)
            return response.status_code == 200
        except (requests.RequestException, requests.ConnectionError):
            return False

    def launch_queue_system(
        self, port: Optional[int] = None
    ) -> tuple[bool, str, Optional[int]]:
        """
        キューシステムを起動

        Returns:
            (成功フラグ, メッセージ, PID)
        """
        if port is None:
            port = self.get_default_port()

        # 既に稼働中かチェック
        if self.is_queue_system_running(port):
            return False, f"WARN: キューシステムは既にポート {port} で稼働中です", None

        try:
            # 現在のGUIプロセスと同じPython実行ファイルを使用
            # 正しいプロジェクトルートから launch_queue.py を起動
            process = subprocess.Popen(
                [sys.executable, str(self.launch_script), "--port", str(port)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
                if sys.platform == "win32"
                else 0,
                cwd=str(self.project_root),
            )

            return (
                True,
                f"SUCCESS: キューシステムをポート {port} で起動しました (PID: {process.pid})",
                process.pid,
            )

        except Exception as e:
            return False, f"ERROR: 起動に失敗しました: {str(e)}", None

    def get_status_message(self, port: Optional[int] = None) -> str:
        """キューシステムの状態メッセージを取得"""
        if port is None:
            port = self.get_default_port()

        if self.is_queue_system_running(port):
            return f"RUNNING: キューシステム稼働中 (ポート: {port})"
        else:
            return f"STOPPED: キューシステム停止中 (ポート: {port})"
