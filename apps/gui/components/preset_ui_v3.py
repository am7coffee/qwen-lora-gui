"""
プリセット管理UIコンポーネント v3
OptimizerArgsRegistryと統合した新実装
"""

import shlex
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List, TYPE_CHECKING

import gradio as gr  # type: ignore

from apps.gui.components.optimizer_args_registry import OptimizerArgsRegistry
from apps.gui.components.preset_manager_v2 import PresetManagerV2

if TYPE_CHECKING:
    from apps.gui.components.parameter_collector_v4 import ParameterCollectorV4


class PresetUIV3:
    """プリセット管理UIクラス v3"""

    def __init__(
        self,
        preset_manager: PresetManagerV2,
        args_registry: OptimizerArgsRegistry,
        parameter_collector: Optional["ParameterCollectorV4"] = None,
    ):
        """
        Args:
            preset_manager: PresetManagerインスタンス
            args_registry: OptimizerArgsRegistryインスタンス
            parameter_collector: ParameterCollectorV4インスタンス（コマンド生成用）
        """
        self.preset_manager = preset_manager
        self.args_registry = args_registry
        self.parameter_collector = parameter_collector
        self.pending_save_name: Optional[str] = None
        self.pending_save_params: Optional[Dict[str, Any]] = None
        self.pending_delete_filename: Optional[str] = None

    def create_ui(self) -> Dict[str, Any]:
        """プリセット管理UIを作成

        Returns:
            UIコンポーネントの辞書
        """
        with gr.Row():
            # 左側: プリセット選択・操作
            with gr.Column(scale=2):
                preset_dropdown = gr.Dropdown(
                    label="プリセット選択",
                    choices=[],
                    value=None,
                    interactive=True,
                    elem_id="preset_dropdown",
                )
                with gr.Row():
                    load_btn = gr.Button(
                        "📂 読み込み", variant="secondary", elem_id="preset_load_btn"
                    )
                    delete_btn = gr.Button(
                        "🗑️ 削除", variant="stop", elem_id="preset_delete_btn"
                    )
                    save_btn = gr.Button("💾 保存", variant="primary")

            # 右側: プリセット保存・外部連携
            with gr.Column(scale=3):
                preset_name = gr.Textbox(
                    label="プリセット名",
                    placeholder="プリセット名を入力してください",
                    interactive=True,
                    elem_id="preset_name_input",
                )
                # 外部連携ボタン
                with gr.Row():
                    import_btn = gr.UploadButton(
                        "📥 インポート",
                        variant="secondary",
                        file_types=[".json"],
                        file_count="single",
                    )
                    export_btn = gr.Button("📤 エクスポート", variant="secondary")
                
                # インポート・エクスポート機能説明
                import_export_help = gr.Markdown("""
**📥 インポート**: 外部に保存したプリセットの内容を画面に反映します（リストへは追加しません）  
**📤 エクスポート**: プリセット選択→エクスポート→ファイルサイズをクリックするとダウンロードします
""", elem_id="preset_import_export_help")

        # ステータス表示
        status = gr.Markdown("", visible=False, elem_id="preset_status")

        # エクスポート用ファイルダウンロード
        export_file = gr.File(visible=False, label="エクスポートファイル")

        # 上書き確認UI（初期は非表示）
        with gr.Row(visible=False) as confirm_row:
            confirm_message = gr.Markdown("")
            confirm_yes = gr.Button("はい、上書きする", variant="stop", visible=False)
            confirm_no = gr.Button("キャンセル", variant="secondary", visible=False)

        # 削除確認UI（初期は非表示）
        with gr.Row(visible=False) as delete_confirm_row:
            delete_confirm_message = gr.Markdown("")
            delete_confirm_yes = gr.Button(
                "はい、削除する", variant="stop", visible=False
            )
            delete_confirm_no = gr.Button(
                "キャンセル", variant="secondary", visible=False
            )

        return {
            "dropdown": preset_dropdown,
            "load_btn": load_btn,
            "delete_btn": delete_btn,
            "preset_name": preset_name,
            "save_btn": save_btn,
            "import_btn": import_btn,
            "export_btn": export_btn,
            "export_file": export_file,
            "status": status,
            "confirm_row": confirm_row,
            "confirm_message": confirm_message,
            "confirm_yes": confirm_yes,
            "confirm_no": confirm_no,
            "delete_confirm_row": delete_confirm_row,
            "delete_confirm_message": delete_confirm_message,
            "delete_confirm_yes": delete_confirm_yes,
            "delete_confirm_no": delete_confirm_no,
        }

    def refresh_preset_list(self) -> Any:
        """プリセット一覧を更新"""
        presets = self.preset_manager.get_preset_list()
        choices = [(p["display_name"], p["filename"]) for p in presets]
        return gr.update(choices=choices)

    def save_preset_with_elem_ids(
        self, preset_name_input: str, elem_id_to_value: Dict[str, Any]
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """elem_idベースでプリセットを保存

        Args:
            preset_name_input: プリセット名
            elem_id_to_value: elem_id → 値のマッピング

        Returns:
            UI更新用のタプル
        """
        if not preset_name_input.strip():
            return (
                gr.update(visible=True, value="❌ プリセット名を入力してください"),
                gr.update(),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

        try:
            # elem_idからパラメータを抽出
            params = self._extract_parameters_from_elem_ids(elem_id_to_value)

            # コマンドを生成して含める（プリセット名も渡す）
            preset_data = self._create_preset_data_with_commands(
                params, preset_name_input
            )

            # 既存チェック
            exists, existing_filename = self.preset_manager.check_preset_exists(
                preset_name_input
            )

            if exists:
                # 上書き確認UIを表示
                self.pending_save_name = preset_name_input
                self.pending_save_params = preset_data  # preset_dataを保存

                return (
                    gr.update(visible=False),
                    gr.update(),
                    gr.update(visible=True),
                    gr.update(
                        visible=True,
                        value=f"⚠️ '{existing_filename}' は既に存在します。上書きしますか？",
                    ),
                    gr.update(visible=True),
                    gr.update(visible=True),
                )

            # 新規保存（拡張版メソッドを使用）
            if hasattr(self.preset_manager, "save_preset_extended"):
                success, message, filename = self.preset_manager.save_preset_extended(
                    preset_name_input, preset_data, overwrite=False
                )
            else:
                # 後方互換性（旧形式保存）
                success, message, filename = self.preset_manager.save_preset(
                    preset_name_input, params, overwrite=False
                )

            if success:
                return (
                    gr.update(visible=True, value=f"✅ {message}"),
                    self.refresh_preset_list(),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )
            else:
                return (
                    gr.update(visible=True, value=f"❌ {message}"),
                    gr.update(),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

        except Exception as e:
            return (
                gr.update(visible=True, value=f"❌ エラー: {str(e)}"),
                gr.update(),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

    def confirm_overwrite(
        self,
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """上書き確認後の処理"""
        if self.pending_save_name and self.pending_save_params:
            # 拡張版メソッドを使用（コマンド付き保存）
            if hasattr(self.preset_manager, "save_preset_extended"):
                success, message, filename = self.preset_manager.save_preset_extended(
                    self.pending_save_name, self.pending_save_params, overwrite=True
                )
            else:
                # 後方互換性（旧形式保存）
                if "parameters" in self.pending_save_params:
                    # 新形式から旧形式への変換
                    params = self.pending_save_params["parameters"]
                else:
                    params = self.pending_save_params
                success, message, filename = self.preset_manager.save_preset(
                    self.pending_save_name, params, overwrite=True
                )

            self.pending_save_name = None
            self.pending_save_params = None

            if success:
                return (
                    gr.update(visible=True, value=f"✅ {message}"),
                    self.refresh_preset_list(),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

        return (
            gr.update(visible=True, value="❌ 上書き処理に失敗しました"),
            gr.update(),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    def cancel_overwrite(
        self,
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """上書きキャンセル"""
        self.pending_save_name = None
        self.pending_save_params = None

        return (
            gr.update(visible=True, value="ℹ️ 保存をキャンセルしました"),
            gr.update(),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    def load_preset_with_elem_ids(
        self, selected_filename: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """elem_idベースでプリセットを読み込み

        Args:
            selected_filename: 選択されたプリセットファイル名

        Returns:
            (ステータス更新, elem_id → 値のマッピング)
        """
        if not selected_filename:
            return (
                gr.update(visible=True, value="❌ プリセットを選択してください"),
                {},
            )

        try:
            success, params, message = self.preset_manager.load_preset(
                selected_filename
            )

            if success:
                # パラメータをelem_id形式に変換
                elem_id_updates = self._convert_params_to_elem_ids(params)

                return (
                    gr.update(visible=True, value=f"✅ {message}"),
                    elem_id_updates,
                )
            else:
                return (
                    gr.update(visible=True, value=f"❌ {message}"),
                    {},
                )

        except Exception as e:
            return (
                gr.update(visible=True, value=f"❌ エラー: {str(e)}"),
                {},
            )

    def delete_preset(
        self, selected_filename: str
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """プリセット削除確認を開始"""
        if not selected_filename:
            return (
                gr.update(visible=True, value="❌ プリセットを選択してください"),
                gr.update(),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

        # 削除確認UIを表示
        self.pending_delete_filename = selected_filename
        return (
            gr.update(visible=False),
            gr.update(),
            gr.update(visible=True),
            gr.update(
                value=f"⚠️ '{selected_filename}' を削除しますか？この操作は元に戻せません。",
            ),
            gr.update(visible=True),
            gr.update(visible=True),
        )

    def confirm_delete(
        self,
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """削除確認後の処理"""
        if not self.pending_delete_filename:
            return (
                gr.update(visible=True, value="❌ 削除処理に失敗しました"),
                gr.update(),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

        try:
            success, message = self.preset_manager.delete_preset(
                self.pending_delete_filename
            )
            self.pending_delete_filename = None

            if success:
                return (
                    gr.update(visible=True, value=f"✅ {message}"),
                    self.refresh_preset_list(),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )
            else:
                return (
                    gr.update(visible=True, value=f"❌ {message}"),
                    gr.update(),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

        except Exception as e:
            self.pending_delete_filename = None
            return (
                gr.update(visible=True, value=f"❌ エラー: {str(e)}"),
                gr.update(),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

    def cancel_delete(
        self,
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """削除キャンセル"""
        self.pending_delete_filename = None
        return (
            gr.update(visible=True, value="ℹ️ 削除をキャンセルしました"),
            gr.update(),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    def _extract_parameters_from_elem_ids(
        self, elem_id_to_value: Dict[str, Any]
    ) -> Dict[str, Any]:
        """elem_idからパラメータを抽出

        Args:
            elem_id_to_value: elem_id → 値のマッピング

        Returns:
            パラメータ辞書 {param_name: {"enabled": bool, "value": any}}
        """
        params: Dict[str, Any] = {}

        # 通常パラメータの処理
        for elem_id, value in elem_id_to_value.items():
            if elem_id.startswith("param-") and elem_id.endswith("-enabled"):
                # enabledチェックボックス
                param_name = elem_id.replace("param-", "").replace("-enabled", "")
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["enabled"] = value

            elif elem_id.startswith("param-") and elem_id.endswith("-value"):
                # 値入力
                param_name = elem_id.replace("param-", "").replace("-value", "")
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["value"] = value

        # optimizer_argsの処理（レジストリを使用）
        optimizer_args = self.args_registry.extract_optimizer_args_from_elem_ids(
            elem_id_to_value
        )
        if optimizer_args:
            params["optimizer_args"] = optimizer_args

        return params

    def _convert_params_to_elem_ids(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """パラメータをelem_id形式に変換

        Args:
            params: プリセットパラメータ

        Returns:
            elem_id → 値のマッピング
        """
        elem_id_updates = {}

        for param_name, param_data in params.items():
            if param_name == "optimizer_args":
                # optimizer_argsは特別処理が必要なため、ここではスキップ
                # parameter_collector_v3.pyのload_preset_handlerで処理される
                continue
            else:
                # 通常パラメータ
                if isinstance(param_data, dict):
                    if "enabled" in param_data:
                        elem_id = f"param-{param_name}-enabled"
                        elem_id_updates[elem_id] = param_data["enabled"]
                    if "value" in param_data:
                        elem_id = f"param-{param_name}-value"
                        elem_id_updates[elem_id] = param_data["value"]

        return elem_id_updates

    def _create_preset_data_with_commands(
        self, params: Dict[str, Any], preset_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """パラメータからコマンドを生成してプリセットデータを作成

        Args:
            params: パラメータ辞書
            preset_name: プリセット名

        Returns:
            コマンドを含む完全なプリセットデータ
        """
        preset_data = {
            "parameters": params,
            "metadata": {
                "name": preset_name or "Untitled",  # nameフィールドを追加
                "version": "3.2",
                "platform": sys.platform,
                "created_at": datetime.now().isoformat(),
                "gui_version": "3.0.0",
            },
        }

        # CommandGeneratorでコマンドを生成
        if self.parameter_collector and hasattr(
            self.parameter_collector, "command_generator"
        ):
            try:
                # CommandGenerator用にパラメータを変換
                # optimizer_argsの特殊な構造を処理
                converted_params = {}
                for key, value in params.items():
                    if key == "optimizer_args":
                        # optimizer_argsは特殊構造（各引数がenabledとvalueを持つ）
                        # CommandGeneratorが期待する形式（引数名→値の辞書）に変換
                        if isinstance(value, dict):
                            optimizer_args_dict = {}
                            for arg_name, arg_data in value.items():
                                if isinstance(arg_data, dict):
                                    # enabledがTrueの項目のみ含める
                                    if arg_data.get("enabled", False):
                                        optimizer_args_dict[arg_name] = arg_data.get(
                                            "value", ""
                                        )
                            # optimizer_argsとして設定
                            if optimizer_args_dict:
                                converted_params["optimizer_args"] = optimizer_args_dict
                    else:
                        # 通常のパラメータはenabledとvalueの構造から値を抽出
                        if isinstance(value, dict):
                            if value.get("enabled", False):
                                param_value = value.get("value")
                                if param_value is not None:
                                    converted_params[key] = param_value
                        else:
                            # 辞書でない場合はそのまま
                            converted_params[key] = value

                # コマンド生成（改行なし）
                commands_text = (
                    self.parameter_collector.command_generator.generate_all_commands(
                        converted_params, use_newlines=False
                    )
                )

                # リスト形式に変換
                commands_list: Dict[str, List[str]] = {}
                for cmd_type, cmd_text in commands_text.items():
                    # プラットフォームに応じた適切な分割
                    commands_list[cmd_type] = shlex.split(
                        cmd_text, posix=(sys.platform != "win32")
                    )

                # プリセットデータに追加
                preset_data["commands_text"] = commands_text  # デバッグ・確認用
                preset_data["commands"] = commands_list  # 実行用

            except Exception as e:
                # コマンド生成失敗時も保存は継続
                print(f"コマンド生成警告: {str(e)}")
                preset_data["commands"] = {}
                preset_data["commands_text"] = {}

        return preset_data

    def import_preset(self, uploaded_file) -> str:
        """プリセットファイルをインポート（画面に値反映のみ）

        Args:
            uploaded_file: アップロードされたファイル情報

        Returns:
            インポートファイルパス（preset_load_controllerで処理するため）
        """
        if not uploaded_file:
            return ""

        # アップロードされたファイルのパスを返す
        # 実際の値セットはpreset_load_controllerが行う
        return uploaded_file.name

    def export_preset(self, selected_preset: str) -> Tuple[str, Optional[str]]:
        """プリセットをエクスポート用ファイルとして準備

        Args:
            selected_preset: 選択されたプリセットファイル名

        Returns:
            (ステータスメッセージ, エクスポートファイルパス)
        """
        if not selected_preset:
            return "❌ エクスポートするプリセットを選択してください", None

        try:
            # プリセットファイルパスを取得
            from pathlib import Path

            preset_path = Path(self.preset_manager.preset_dir) / selected_preset

            if not preset_path.exists():
                return (
                    f"❌ プリセットファイル '{selected_preset}' が見つかりません",
                    None,
                )

            # エクスポート用一時ファイルを作成
            import tempfile
            import shutil

            # 拡張子なしのファイル名を取得
            base_name = preset_path.stem

            # 一時ファイル作成
            temp_dir = tempfile.gettempdir()
            export_path = f"{temp_dir}/exported_{base_name}.json"

            # ファイルをコピー
            shutil.copy2(preset_path, export_path)

            return f"✅ プリセット '{base_name}' をエクスポート準備完了", export_path

        except Exception as e:
            return f"❌ エクスポートエラー: {str(e)}", None
