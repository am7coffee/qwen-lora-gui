"""
CLI環境でのファイルパス検証
CLI環境の作業ディレクトリからの相対パスを考慮
"""

import json
from pathlib import Path
from typing import Tuple
from core.config.path_resolver import PathResolver


class CLIFileValidator:
    """CLI環境を考慮したファイル検証クラス"""

    def __init__(self):
        self.path_resolver = PathResolver()
        self.cli_config = self._load_cli_config()

        # CLI環境のルートパスを取得
        try:
            self.cli_root, self.cli_venv = self.path_resolver.get_cli_paths(
                self.cli_config
            )
        except Exception:
            # フォールバック：現在のディレクトリを使用
            self.cli_root = Path.cwd()

    def _load_cli_config(self) -> dict:
        """CLI設定を読み込み"""
        config_path = Path("data/config/cli_settings.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"cli_root_path": "../musubi-tuner"}  # デフォルト

    def validate_file_path(
        self, file_path: str, param_name: str = "file"
    ) -> Tuple[bool, str]:
        """
        ファイルパスをCLI環境基準で検証（汎用版）

        Args:
            file_path: 検証対象のファイルパス
            param_name: パラメータ名（エラーメッセージ用）

        Returns:
            (is_valid, message): 検証結果とメッセージ
        """
        if not file_path or file_path.strip() == "":
            return True, ""

        try:
            # 不完全なクォーテーションをチェック
            stripped_path = file_path.strip()
            quote_count_double = stripped_path.count('"')
            quote_count_single = stripped_path.count("'")

            # 奇数個のクォーテーションがある場合はエラー
            if quote_count_double % 2 != 0:
                return (
                    False,
                    f"--{param_name}: 不完全なダブルクォーテーション: {file_path}",
                )
            if quote_count_single % 2 != 0:
                return (
                    False,
                    f"--{param_name}: 不完全なシングルクォーテーション: {file_path}",
                )

            # ダブルクォーテーションを除去
            cleaned_path = stripped_path.strip('"').strip("'")

            # CLI環境基準でパス解決
            if Path(cleaned_path).is_absolute():
                # 絶対パス
                resolved_path = Path(cleaned_path)
            else:
                # 相対パス：CLI環境のルートからの相対
                resolved_path = self.cli_root / cleaned_path

            if resolved_path.exists() and resolved_path.is_file():
                return True, f"--{param_name}: ファイル存在確認: {resolved_path}"
            else:
                return (
                    False,
                    f"--{param_name}: ファイルが見つかりません: {resolved_path}",
                )

        except Exception as e:
            return False, f"--{param_name}: パス検証エラー: {str(e)}"

    def validate_dit_file_path(self, file_path: str) -> Tuple[bool, str]:
        """--ditファイルパス検証（後方互換用）"""
        return self.validate_file_path(file_path, "dit")


# グローバルインスタンス（1回だけ初期化）
_validator_instance = None


def get_cli_file_validator() -> CLIFileValidator:
    """CLIファイル検証インスタンスを取得（シングルトン）"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = CLIFileValidator()
    return _validator_instance
