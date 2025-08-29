"""
ダイレクトターミナル実行モジュール
新規コマンドプロンプトでコマンドを直接実行
"""

import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from core.config.path_resolver import PathResolver


class DirectTerminalExecutor:
    """ダイレクトターミナル実行クラス"""

    def __init__(self):
        """初期化"""
        self.path_resolver = PathResolver()
        self.config = self._load_cli_config()

        # パス解決と検証
        self.cli_root, self.cli_venv = self.path_resolver.get_cli_paths(self.config)
        validation = self.path_resolver.validate_cli_paths(self.cli_root, self.cli_venv)

        if not validation["valid"]:
            raise RuntimeError(f"CLIパス検証エラー: {validation['errors']}")

        # バッチファイル保存用ディレクトリ
        self.batch_dir = Path("data/logs/executions")
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def _load_cli_config(self) -> Dict[str, Any]:
        """CLI設定の読み込み"""
        import json

        config_path = Path("data/config/cli_settings.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"設定ファイル読み込みエラー: {e}")
        return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を取得"""
        return {
            "cli_root_path": "../musubi-tuner",
            "cli_venv_path": "../musubi-tuner/venv",
            "execution_settings": {
                "log_dir": "data/logs/executions",
            },
        }

    def execute_command(self, command_type: str, command_text: str) -> Dict[str, Any]:
        """コマンドを新規ターミナルで実行

        Args:
            command_type: "precache", "text_encoder", "training"
            command_text: 実行するコマンド

        Returns:
            実行結果の辞書
        """
        # コマンドの空チェック
        if not command_text or not command_text.strip():
            return {"success": False, "message": "❌ コマンドが入力されていません"}

        # コマンドの前処理（改行除去）
        clean_command = self._prepare_command(command_text)

        # バッチファイル作成
        batch_file = self._create_batch_file(command_type, clean_command)

        try:
            # 新規コマンドプロンプトで実行
            # startコマンドでタイトル付きの新規ウィンドウを開く
            subprocess.Popen(
                [
                    "start",
                    f"{command_type.upper()} Process",
                    "cmd",
                    "/c",
                    str(batch_file),
                ],
                shell=True,
            )

            return {
                "success": True,
                "message": f"✅ {command_type}プロセスを新しいターミナルで起動しました",
            }

        except Exception as e:
            return {"success": False, "message": f"❌ プロセス起動エラー: {str(e)}"}

    def _prepare_command(self, command_text: str) -> str:
        """コマンドを実行用に準備"""
        # 改行継続のパターンのみを除去（Windowsパスのバックスラッシュは保持）
        # パターン1: バックスラッシュ + 改行
        clean_command = command_text.replace("\\\r\n", " ")  # Windows改行
        clean_command = clean_command.replace("\\\n", " ")  # Unix改行
        clean_command = clean_command.replace("\\\r", " ")  # Mac改行

        # パターン2: バックスラッシュ + スペース + 改行（一般的な継続パターン）
        clean_command = clean_command.replace(" \\\r\n", " ")
        clean_command = clean_command.replace(" \\\n", " ")

        # 通常の改行文字を除去
        clean_command = clean_command.replace("\r\n", " ")
        clean_command = clean_command.replace("\n", " ")
        clean_command = clean_command.replace("\r", " ")

        # 連続した空白を1つにまとめる
        clean_command = " ".join(clean_command.split())

        return clean_command

    def _create_batch_file(self, command_type: str, command: str) -> Path:
        """実行用バッチファイルを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        batch_content = f'''@echo off
echo ========================================
echo Starting {command_type.upper()} Process
echo ========================================
echo.
echo Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
echo.

echo Changing directory to CLI root...
cd /d "{self.cli_root}"
if errorlevel 1 (
    echo [ERROR] Failed to change directory to {self.cli_root}
    pause
    exit /b 1
)

echo Current directory: %CD%
echo.

echo Activating virtual environment...
if exist "{self.cli_venv}\\Scripts\\activate.bat" (
    call "{self.cli_venv}\\Scripts\\activate.bat"
) else (
    echo [ERROR] Virtual environment not found at {self.cli_venv}
    pause
    exit /b 1
)

echo.
echo ========================================
echo Executing command:
echo {command}
echo ========================================
echo.
echo Press Ctrl+C to stop the process
echo.

REM コマンドを実行
{command}

echo.
echo ========================================
if %ERRORLEVEL%==0 (
    echo Process completed successfully!
) else (
    echo Process failed with error code: %ERRORLEVEL%
)
echo ========================================
echo.
echo Window will close in 5 seconds...
timeout /t 5 /nobreak > nul
exit
'''

        batch_file = self.batch_dir / f"{command_type}_{timestamp}.bat"
        with open(batch_file, "w", encoding="shift_jis") as f:
            f.write(batch_content)

        return batch_file


# グローバルインスタンス
direct_terminal_executor = DirectTerminalExecutor()
