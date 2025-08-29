"""
パス解決ユーティリティ
相対パス・絶対パス・クロスプラットフォーム対応
"""

import sys
from pathlib import Path
from typing import Tuple, Optional, Dict, Any


class PathResolver:
    """パス解決ユーティリティ
    相対パス・絶対パスの両方に対応
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Args:
            base_dir: 基準ディレクトリ（省略時は現在のディレクトリ）
        """
        self.base_dir = base_dir or Path.cwd()
        self.is_windows = sys.platform == "win32"

    def resolve_path(self, path_str: str) -> Path:
        """パスを解決（相対・絶対両対応）

        Args:
            path_str: パス文字列

        Returns:
            解決されたPathオブジェクト
        """
        path = Path(path_str)

        # 絶対パスの場合はそのまま返す
        if path.is_absolute():
            return path

        # 相対パスの場合は基準ディレクトリからの相対パスとして解決
        return (self.base_dir / path).resolve()

    def get_cli_paths(self, config: Dict[str, Any]) -> Tuple[Path, Path]:
        """CLI設定からパスを取得

        Args:
            config: CLI設定辞書

        Returns:
            (CLIルートパス, CLI仮想環境パス)
        """
        cli_root = self.resolve_path(config["cli_root_path"])
        cli_venv = self.resolve_path(config["cli_venv_path"])

        return cli_root, cli_venv

    def get_python_executable(self, venv_path: Path) -> Path:
        """プラットフォームに応じたPython実行ファイルパスを取得

        Args:
            venv_path: 仮想環境のパス

        Returns:
            Python実行ファイルのパス
        """
        if self.is_windows:
            return venv_path / "Scripts" / "python.exe"
        else:
            return venv_path / "bin" / "python"

    def get_accelerate_executable(self, venv_path: Path) -> Path:
        """プラットフォームに応じたAccelerate実行ファイルパスを取得

        Args:
            venv_path: 仮想環境のパス

        Returns:
            Accelerate実行ファイルのパス
        """
        if self.is_windows:
            return venv_path / "Scripts" / "accelerate.exe"
        else:
            return venv_path / "bin" / "accelerate"

    def normalize_script_path(self, script_path: str) -> str:
        """スクリプトパスを正規化（JSONに保存用）

        Args:
            script_path: スクリプトパス文字列

        Returns:
            正規化されたパス文字列
        """
        # pathlib.Pathで正規化してから文字列に変換
        return str(Path(script_path))

    def validate_cli_paths(self, cli_root: Path, cli_venv: Path) -> Dict[str, Any]:
        """CLIパスの検証（クロスプラットフォーム対応）

        Args:
            cli_root: CLIルートパス
            cli_venv: CLI仮想環境パス

        Returns:
            検証結果の辞書
        """
        result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "platform": "Windows" if self.is_windows else "Unix-like",
        }

        # CLIルートの確認
        if not cli_root.exists():
            result["valid"] = False
            result["errors"].append(f"CLIルートパスが存在しません: {cli_root}")

        # 仮想環境の確認
        if not cli_venv.exists():
            result["valid"] = False
            result["errors"].append(f"CLI仮想環境が存在しません: {cli_venv}")
        else:
            # Pythonインタープリタの確認
            python_exe = self.get_python_executable(cli_venv)
            if not python_exe.exists():
                result["valid"] = False
                result["errors"].append(
                    f"Pythonインタープリタが見つかりません: {python_exe}"
                )

            # Accelerateの確認
            accelerate_exe = self.get_accelerate_executable(cli_venv)
            if not accelerate_exe.exists():
                result["warnings"].append(
                    f"Accelerateが見つかりません: {accelerate_exe}"
                )

        # スクリプトの存在確認
        scripts = {
            "precache": "src/musubi_tuner/qwen_image_cache_latents.py",
            "text_encoder": "src/musubi_tuner/qwen_image_cache_text_encoder_outputs.py",
            "training": "src/musubi_tuner/qwen_image_train_network.py",
        }

        for name, script_path in scripts.items():
            full_path = cli_root / script_path
            if not full_path.exists():
                result["warnings"].append(
                    f"{name}スクリプトが見つかりません: {full_path}"
                )

        return result

    def get_log_directory(self, config: Dict[str, Any]) -> Path:
        """ログディレクトリのパスを取得

        Args:
            config: CLI設定辞書

        Returns:
            ログディレクトリのパス
        """
        log_dir = config.get("execution_settings", {}).get(
            "log_dir", "data/logs/executions"
        )
        return self.resolve_path(log_dir)
