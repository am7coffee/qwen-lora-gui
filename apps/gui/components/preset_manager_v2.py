"""
拡張版プリセット管理ユーティリティ
OptimizerArgsManagerと連携してoptimizer_argsを正しく処理
"""

import json
import os
import shlex
import sys
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

from core.presets.optimizer_args_manager import OptimizerArgsManager


class PresetManagerV2:
    """拡張版プリセット管理クラス"""

    def __init__(
        self,
        preset_dir: str = "data/presets/",
        optimizer_args_manager: Optional[OptimizerArgsManager] = None,
    ):
        """
        Args:
            preset_dir: プリセット保存ディレクトリ
            optimizer_args_manager: OptimizerArgsManagerインスタンス
        """
        self.preset_dir = preset_dir
        os.makedirs(preset_dir, exist_ok=True)
        self.optimizer_args_manager = optimizer_args_manager

    def get_preset_list(self) -> List[Dict[str, str]]:
        """プリセットファイルリストを取得"""
        presets = []
        for filename in os.listdir(self.preset_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.preset_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    presets.append(
                        {
                            "name": filename[:-5],  # .json拡張子を除去
                            "display_name": data.get("name", filename[:-5]),
                            "filename": filename,  # UI側で期待されているキー
                        }
                    )
                except Exception:
                    continue
        return sorted(presets, key=lambda x: x["name"])

    def check_preset_exists(self, name: str) -> Tuple[bool, Optional[str]]:
        """プリセットの存在確認"""
        filename = f"{name}.json"
        filepath = os.path.join(self.preset_dir, filename)
        if os.path.exists(filepath):
            return True, filename
        return False, None

    def delete_preset(self, filename: str) -> Tuple[bool, str]:
        """プリセット削除"""
        filepath = os.path.join(self.preset_dir, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True, f"プリセット '{filename}' を削除しました"
            else:
                return False, f"プリセット '{filename}' が見つかりません"
        except Exception as e:
            return False, f"削除エラー: {str(e)}"

    def load_preset(self, filename: str) -> Tuple[bool, Dict[str, Any], str]:
        """プリセット読み込み"""
        filepath = os.path.join(self.preset_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            params = self._convert_preset_to_params(data)
            return True, params, "プリセットを読み込みました"
        except Exception as e:
            return False, {}, f"読み込みエラー: {str(e)}"

    def save_preset(
        self,
        name: str,
        params: Dict[str, Any],
        description: str = "",
        overwrite: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """基本プリセット保存"""
        filename = f"{name}.json"
        filepath = os.path.join(self.preset_dir, filename)

        if os.path.exists(filepath) and not overwrite:
            return False, f"プリセット '{name}' は既に存在します", filename

        try:
            preset_data = self._convert_params_to_preset(params)
            preset_data["name"] = name
            preset_data["description"] = description
            preset_data["created_at"] = datetime.now().isoformat()

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)

            return True, f"プリセット '{name}' を保存しました", filename
        except Exception as e:
            return False, f"保存エラー: {str(e)}", None

    def _convert_params_to_preset(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """パラメータをプリセット形式に変換"""
        # 基本的な変換処理
        preset: Dict[str, Any] = {}
        for key, value in params.items():
            if key.startswith("optimizer_"):
                if "optimizer_args" not in preset:
                    preset["optimizer_args"] = {}
                preset["optimizer_args"][key] = value
            else:
                preset[key] = value
        return preset

    def _convert_preset_to_params(
        self, preset_params: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """プリセット形式をパラメータに変換"""
        params = {}
        for key, value in preset_params.items():
            if key == "optimizer_args" and isinstance(value, dict):
                params.update(value)
            elif key not in ["name", "description", "created_at"]:
                params[key] = value
        return params

    def save_preset_with_optimizer_handling(
        self,
        name: str,
        params: Dict[str, Any],
        optimizer_type: Optional[str] = None,
        description: str = "",
        overwrite: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """optimizer_args専用処理を含むプリセット保存

        Args:
            name: プリセット名
            params: パラメータ辞書
            optimizer_type: オプティマイザータイプ
            description: 説明文
            overwrite: 上書きフラグ

        Returns:
            (成功フラグ, メッセージ, ファイル名)
        """
        # optimizer_argsの特別処理
        if (
            self.optimizer_args_manager
            and optimizer_type
            and "optimizer_args" in params
        ):
            # optimizer_argsを検証
            if isinstance(params["optimizer_args"], dict):
                args_data = params["optimizer_args"]
                if "value" in args_data and isinstance(args_data["value"], dict):
                    # 検証
                    valid, errors = self.optimizer_args_manager.validate_optimizer_args(
                        optimizer_type, args_data["value"]
                    )
                    if not valid:
                        return (
                            False,
                            f"optimizer_args検証エラー: {', '.join(errors)}",
                            None,
                        )

        # 基本の保存処理を呼び出し
        return self.save_preset(name, params, description, overwrite)

    def load_preset_with_optimizer_handling(
        self, filename: str, target_optimizer_type: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """optimizer_args専用処理を含むプリセット読み込み

        Args:
            filename: プリセットファイル名
            target_optimizer_type: 適用先のオプティマイザータイプ

        Returns:
            (成功フラグ, パラメータ辞書, メッセージ)
        """
        # 基本の読み込み処理
        success, params, message = self.load_preset(filename)

        if not success:
            return success, params, message

        # optimizer_argsの変換処理
        if self.optimizer_args_manager and target_optimizer_type:
            if "optimizer_args" in params:
                optimizer_args_data = params["optimizer_args"]

                # プリセットのoptimizer_typeを確認
                preset_optimizer_type = None
                if "optimizer_type" in params:
                    opt_type_data = params["optimizer_type"]
                    if isinstance(opt_type_data, dict) and "value" in opt_type_data:
                        preset_optimizer_type = opt_type_data["value"]

                # optimizer_typeが変更される場合の処理
                if (
                    preset_optimizer_type
                    and preset_optimizer_type != target_optimizer_type
                ):
                    # 異なるオプティマイザー間での変換
                    message += f"\n注意: オプティマイザータイプが {preset_optimizer_type} から {target_optimizer_type} に変更されます"

                    # 新しいオプティマイザーのデフォルト値を取得
                    default_args = self.optimizer_args_manager.get_default_args(
                        target_optimizer_type
                    )

                    # プリセットの値で上書き（互換性のある引数のみ）
                    if (
                        isinstance(optimizer_args_data, dict)
                        and "value" in optimizer_args_data
                    ):
                        old_args = optimizer_args_data["value"]
                        new_args = {}

                        # 新しいテンプレートの引数名を取得
                        template = (
                            self.optimizer_args_manager.get_template_for_optimizer(
                                target_optimizer_type
                            )
                        )
                        valid_arg_names = {arg.name for arg in template}

                        # 互換性のある引数をコピー
                        for arg_name, value in old_args.items():
                            if arg_name in valid_arg_names:
                                new_args[arg_name] = value

                        # デフォルト値で補完
                        for arg_name, default_value in default_args.items():
                            if arg_name not in new_args:
                                new_args[arg_name] = default_value

                        # 更新
                        optimizer_args_data["value"] = new_args

                # レジストリの同期
                self.optimizer_args_manager.sync_registry_with_template(
                    target_optimizer_type
                )

        return success, params, message

    def migrate_old_preset(self, old_preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """旧形式のプリセットを新形式に変換

        Args:
            old_preset_data: 旧形式のプリセットデータ

        Returns:
            新形式のプリセットデータ
        """
        # メタデータのバージョンチェック
        if "metadata" in old_preset_data:
            metadata = old_preset_data["metadata"]
            version = metadata.get("version", "1.0")

            if version == "1.0":
                # v1.0 → v2.0への変換
                # bool型の値をchoice型の文字列に変換
                if "parameters" in old_preset_data:
                    params = old_preset_data["parameters"]

                    # optimizer_argsの処理
                    if "optimizer_args" in params:
                        optimizer_args = params["optimizer_args"]
                        if (
                            isinstance(optimizer_args, dict)
                            and "value" in optimizer_args
                        ):
                            args_value = optimizer_args["value"]

                            # bool値を文字列に変換
                            for key, value in args_value.items():
                                if isinstance(value, bool):
                                    args_value[key] = "true" if value else "false"

                    # 通常パラメータのbool値も変換
                    for param_name, param_data in params.items():
                        if isinstance(param_data, dict) and "value" in param_data:
                            if isinstance(param_data["value"], bool):
                                param_data["value"] = (
                                    "true" if param_data["value"] else "false"
                                )

                # バージョン更新
                metadata["version"] = "2.0"

        return old_preset_data

    def _sanitize_filename(self, name: str) -> str:
        """ファイル名をサニタイズ

        Args:
            name: 元のファイル名

        Returns:
            サニタイズされたファイル名
        """
        import re

        # Windowsで使用できない文字を置換
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
        # 先頭・末尾の空白とドットを削除
        sanitized = sanitized.strip(". ")
        return sanitized if sanitized else "preset"

    def save_preset_extended(
        self,
        name: str,
        preset_data: Dict[str, Any],
        overwrite: bool = False,
    ) -> Tuple[bool, str, Optional[str]]:
        """拡張版：コマンドを含む完全なプリセットデータを保存

        Args:
            name: プリセット名
            preset_data: 完全なプリセットデータ（parameters, commands, metadata含む）
            overwrite: 上書きフラグ

        Returns:
            (success, message, filename)
        """
        try:
            # ファイル名処理
            sanitized_name = self._sanitize_filename(name)
            filename = f"{sanitized_name}.json"
            filepath = os.path.join(self.preset_dir, filename)

            # 既存チェック
            if os.path.exists(filepath) and not overwrite:
                return False, f"プリセット '{name}' は既に存在します", filename

            # 保存（ensure_ascii=Falseで日本語対応）
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, ensure_ascii=False, indent=2)

            return True, f"プリセット '{name}' を保存しました", filename

        except Exception as e:
            return False, f"保存エラー: {str(e)}", None

    def load_preset_with_commands(
        self, filename: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """コマンドを含むプリセットの読み込み（後方互換性あり）

        Args:
            filename: プリセットファイル名

        Returns:
            (success, preset_data, message)
        """
        # 基本の読み込み
        success, params, message = self.load_preset(filename)
        if not success:
            return success, params, message

        # 新形式チェック
        if "commands" not in params:
            # 旧形式の場合、コマンドを生成して追加
            try:
                from core.commands.command_generator import CommandGenerator

                generator = CommandGenerator()
                parameters = params.get("parameters", params)  # 旧形式対応

                # コマンド生成（改行なし）
                commands_text = generator.generate_all_commands(
                    parameters, use_newlines=False
                )

                # リスト形式に変換
                commands_list: Dict[str, List[str]] = {}
                for cmd_type, cmd_text in commands_text.items():
                    commands_list[cmd_type] = shlex.split(
                        cmd_text, posix=(sys.platform != "win32")
                    )

                # プリセットデータを更新
                params["commands"] = commands_list
                params["commands_text"] = commands_text

                # メタデータ追加（旧形式からの変換）
                if "metadata" not in params:
                    params["metadata"] = {
                        "version": "3.1",  # 旧形式
                        "platform": sys.platform,
                        "converted_at": datetime.now().isoformat(),
                    }

            except Exception as e:
                # コマンド生成に失敗しても読み込みは成功とする
                params["commands"] = {}
                params["commands_text"] = {}
                message += f" (コマンド生成警告: {str(e)})"

        return success, params, message
