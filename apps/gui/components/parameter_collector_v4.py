"""
パラメータ収集UI v4 - 識別子ベース静的UI実装 + テーマ・フォント調整機能
設計方針:
1. 識別子ベース静的UI実装を採用（改修案1を完全実装）
2. プリセット/コマンド生成の完全互換性維持（elem_idによる識別子管理継続）
3. 現在の見た目を完全に維持（ラベル: 引数名、info: 日本語説明、デフォルト値・required設定）
4. UIコンポーネント配置のみを静的化、ビジネスロジックは既存のまま
5. component_registryの仕組みをそのまま活用
6. optimizer_argsは動的実装を維持（テンプレート駆動型）

新機能:
- フォントサイズ調整機能（10-24px）：テキストフィールドのみ対象
- フォントサイズリセット機能：デフォルト14pxに戻す
- カスタムCSS/JSによる即時反映：ラベル・ボタン等は対象外
"""

import gradio as gr  # type: ignore
from typing import Any, Dict, List, Tuple, Optional

from apps.gui.components.optimizer_ui_v3 import OptimizerUIV3
from apps.gui.components.preset_ui_v3 import PresetUIV3
from apps.gui.components.direct_terminal_executor import direct_terminal_executor
from apps.gui.components.static_ui_builder import StaticUIBuilder
from core.config.parameters import get_all_parameters
from core.commands.command_generator import CommandGenerator
from core.presets.optimizer_template_manager import OptimizerTemplateManager
from apps.gui.components.preset_manager_v2 import PresetManagerV2
from core.presets.optimizer_args_manager import OptimizerArgsManager
from apps.gui.components.preset_load_controller import PresetLoadController
from apps.gui.components.process_manager import QueueProcessManager
from core.validation.cli_file_validator import get_cli_file_validator

class ParameterCollectorV4:
    """パラメータ収集UI v4 - 識別子ベース静的UI実装"""

    # レイアウト定数（V3から継承）
    COLUMNS_PER_ROW = 3  # 1行あたりの列数（3列レイアウト）

    # elem_idプレフィックス定数（識別子ベース管理を維持）
    PARAM_ENABLED_PREFIX = "param-{}-enabled"
    PARAM_VALUE_PREFIX = "param-{}-value"

    def __init__(self):
        """初期化 - 設計方針に基づく統合アーキテクチャ"""
        self.parameters = get_all_parameters()
        self.command_generator = CommandGenerator()
        self.template_manager = OptimizerTemplateManager()
        self.optimizer_ui = OptimizerUIV3(self.template_manager)

        # OptimizerArgsManager（動的実装維持）
        self.optimizer_args_manager = OptimizerArgsManager(
            self.template_manager, self.optimizer_ui.args_registry
        )

        # キューシステムプロセス管理
        self.queue_manager = QueueProcessManager()

        # 識別子ベース管理のコアレジストリ
        self.component_registry: Dict[str, Dict[str, Any]] = {}
        self.all_inputs: List[Any] = []
        self.optimizer_args_inputs: List[Any] = []  # 動的UI（optimizer専用）
        self._pending_optimizer_args: Optional[Dict[str, Any]] = None

        # 静的UIビルダー（設計方針: UIコンポーネント配置のみを静的化）
        params_dict = self._flatten_parameters(get_all_parameters())
        self.static_builder = StaticUIBuilder(self.component_registry, params_dict)
        self.cli_validator = get_cli_file_validator()  # CLI環境ファイル検証

    def _flatten_parameters(self, parameter_categories):
        """カテゴリ別パラメータを名前をキーとした辞書に変換"""
        flattened = {}
        for category, param_list in parameter_categories.items():
            for param in param_list:
                flattened[param.name] = param
        return flattened

    def _validate_dit_realtime(self, file_path: str):
        """--ditファイルパスのリアルタイム検証"""
        print(f"[DEBUG] _validate_dit_realtime called with: '{file_path}'")

        # 一時的なテスト：空でない場合は常にエラーとする
        if file_path and file_path.strip():
            print("[DEBUG] TEST MODE: Setting error for non-empty path")
            return gr.update(elem_classes=["error"])
        else:
            print("[DEBUG] TEST MODE: Clearing classes for empty path")
            return gr.update(elem_classes=[])

    def register_component(
        self,
        elem_id: str,
        component: Any,
        param_name: str,
        role: str,
        param_config: Any = None,
    ):
        """コンポーネントを登録"""
        self.component_registry[elem_id] = {
            "component": component,
            "param_name": param_name,
            "role": role,  # "enabled" or "value"
            "param_config": param_config,
        }

    def create_parameter_component(self, param: Any) -> Tuple[Any, Any]:
        """
        パラメータ用コンポーネントを作成（設計方針に基づく見た目維持）
        - ラベル: 引数名（param.display_name = --dit, --vae等）をそのまま表示
        - info: 日本語説明（param.help_text）を表示
        - デフォルト値・required設定: ParameterConfigから取得
        - elem_id: 識別子ベース管理を維持
        """
        enabled_elem_id = self.PARAM_ENABLED_PREFIX.format(param.name)
        value_elem_id = self.PARAM_VALUE_PREFIX.format(param.name)

        # enabledチェックボックス（現在の見た目を完全に維持）
        enabled_checkbox = gr.Checkbox(
            label="有効",  # 固定ラベル（現在と同じ）
            value=param.required,  # ParameterConfigのrequired設定
            interactive=True,
            scale=0,
            min_width=80,
            elem_id=enabled_elem_id,
        )

        # 値入力コンポーネント（現在の見た目を完全に維持）
        if param.param_type == "int":
            value_component = gr.Number(
                label=param.display_name,  # 引数名（--dit, --vae等）をそのまま表示
                value=param.default_value,  # ParameterConfigのデフォルト値
                precision=0,
                info=param.help_text,  # 日本語説明をinfoに表示
                scale=3,
                interactive=True,
                elem_id=value_elem_id,
            )
        elif param.param_type == "float":
            value_component = gr.Number(
                label=param.display_name,  # 引数名をそのまま表示
                value=param.default_value,  # ParameterConfigのデフォルト値
                info=param.help_text,  # 日本語説明をinfoに表示
                scale=3,
                interactive=True,
                elem_id=value_elem_id,
            )
        elif param.param_type == "bool":
            value_component = gr.Checkbox(  # type: ignore
                label=param.display_name,  # 引数名をそのまま表示
                value=param.default_value,  # ParameterConfigのデフォルト値
                info=param.help_text,  # 日本語説明をinfoに表示
                scale=3,
                interactive=True,
                elem_id=value_elem_id,
            )
        elif param.param_type == "str" and param.choices:
            value_component = gr.Dropdown(  # type: ignore
                label=param.display_name,  # 引数名をそのまま表示
                choices=param.choices,
                value=param.default_value,  # ParameterConfigのデフォルト値
                info=param.help_text,  # 日本語説明をinfoに表示
                scale=3,
                interactive=True,
                elem_id=value_elem_id,
            )
        else:
            value_component = gr.Textbox(  # type: ignore
                label=param.display_name,  # 引数名をそのまま表示
                value=str(param.default_value)
                if param.default_value is not None
                else "",
                placeholder=param.placeholder_text,
                info=param.help_text,  # 日本語説明をinfoに表示
                scale=3,
                interactive=True,
                elem_id=value_elem_id,
            )

        # component_registryに登録（識別子ベース管理を維持）
        self.register_component(
            enabled_elem_id, enabled_checkbox, param.name, "enabled", param
        )
        self.register_component(
            value_elem_id, value_component, param.name, "value", param
        )

        return enabled_checkbox, value_component

    def create_section(
        self, title: str, params: List[Any], layout_type: str = "three_column"
    ) -> List[Any]:
        """セクション作成（レイアウト対応）"""
        section_inputs = []

        with gr.Accordion(title, open=True):
            if layout_type == "three_column":
                # パラメータを3つずつのグループに分割（3列レイアウト用）
                param_groups = [
                    params[i : i + self.COLUMNS_PER_ROW]
                    for i in range(0, len(params), self.COLUMNS_PER_ROW)
                ]
                for group in param_groups:
                    with gr.Row():
                        for param in group:
                            with gr.Column():
                                with gr.Row():
                                    enabled_cb, value_comp = (
                                        self.create_parameter_component(param)
                                    )
                                    section_inputs.extend([enabled_cb, value_comp])

            elif layout_type == "single_row":
                for param in params:
                    with gr.Row():
                        enabled_cb, value_comp = self.create_parameter_component(param)
                        section_inputs.extend([enabled_cb, value_comp])

            elif layout_type == "two_column":
                if len(params) == 2:
                    # 2項目の場合は1行2列で表示
                    with gr.Row():
                        for param in params:
                            with gr.Column():
                                with gr.Row():
                                    enabled_cb, value_comp = (
                                        self.create_parameter_component(param)
                                    )
                                    section_inputs.extend([enabled_cb, value_comp])
                else:
                    # 3項目以上の場合は2列に分割
                    with gr.Row():
                        with gr.Column():
                            for param in params[:2]:
                                with gr.Row():
                                    enabled_cb, value_comp = (
                                        self.create_parameter_component(param)
                                    )
                                    section_inputs.extend([enabled_cb, value_comp])
                        with gr.Column():
                            for param in params[2:]:
                                with gr.Row():
                                    enabled_cb, value_comp = (
                                        self.create_parameter_component(param)
                                    )
                                    section_inputs.extend([enabled_cb, value_comp])

        return section_inputs

    def create_parameters_ui(
        self, params: List[Any], layout_type: str = "three_column"
    ) -> List[Any]:
        """パラメータUIのみを作成（アコーディオンなし）"""
        section_inputs = []

        if layout_type == "three_column":
            # パラメータを3つずつのグループに分割（3列レイアウト用）
            param_groups = [
                params[i : i + self.COLUMNS_PER_ROW]
                for i in range(0, len(params), self.COLUMNS_PER_ROW)
            ]
            for group in param_groups:
                with gr.Row():
                    for param in group:
                        with gr.Column():
                            with gr.Row():
                                enabled_cb, value_comp = (
                                    self.create_parameter_component(param)
                                )
                                section_inputs.extend([enabled_cb, value_comp])

        elif layout_type == "single_row":
            for param in params:
                with gr.Row():
                    enabled_cb, value_comp = self.create_parameter_component(param)
                    section_inputs.extend([enabled_cb, value_comp])

        elif layout_type == "two_column":
            if len(params) == 2:
                # 2項目の場合は1行2列で表示
                with gr.Row():
                    for param in params:
                        with gr.Column():
                            with gr.Row():
                                enabled_cb, value_comp = (
                                    self.create_parameter_component(param)
                                )
                                section_inputs.extend([enabled_cb, value_comp])
            else:
                # 3項目以上の場合は2列に分割
                with gr.Row():
                    with gr.Column():
                        for param in params[:2]:
                            with gr.Row():
                                enabled_cb, value_comp = (
                                    self.create_parameter_component(param)
                                )
                                section_inputs.extend([enabled_cb, value_comp])
                    with gr.Column():
                        for param in params[2:]:
                            with gr.Row():
                                enabled_cb, value_comp = (
                                    self.create_parameter_component(param)
                                )
                                section_inputs.extend([enabled_cb, value_comp])

        return section_inputs

    def create_static_section(
        self, section_name: str, params: List[Any], accordion_title: str
    ) -> List[Any]:
        """
        StaticUIBuilderを活用した静的セクション作成
        設計方針: UIコンポーネント配置のみを静的化、ビジネスロジックは既存のまま
        """
        components = []

        with gr.Accordion(accordion_title, open=True):
            for param in params:
                with gr.Row():
                    enabled_cb, value_comp = self.create_parameter_component(param)
                    components.extend([enabled_cb, value_comp])

        return components

    def create_enhanced_static_section(self, section_key: str) -> List[Any]:
        """
        StaticUIBuilderの強化版セクション作成機能を活用
        設計方針: 静的UIビルダーでUIコンポーネント配置を管理
        """
        if hasattr(self.static_builder, f"create_{section_key}_section"):
            builder_method = getattr(
                self.static_builder, f"create_{section_key}_section"
            )
            return builder_method()
        else:
            # フォールバック: 従来方式
            return []

    def collect_parameters(self, *args) -> Dict[str, Any]:
        """パラメータ収集（テンプレート駆動型optimizer_args対応）"""
        params = {}

        # 通常パラメータの収集（既存と同じ）
        elem_id_to_value = {}
        for component, value in zip(self.all_inputs, args):
            if hasattr(component, "elem_id") and component.elem_id:
                elem_id_to_value[component.elem_id] = value

        # パラメータ収集
        for elem_id, reg_info in self.component_registry.items():
            if reg_info["role"] == "value":
                param_name = reg_info["param_name"]
                enabled_elem_id = self.PARAM_ENABLED_PREFIX.format(param_name)

                # enabled状態をチェック
                enabled_value = elem_id_to_value.get(enabled_elem_id, False)
                if enabled_value:
                    value = elem_id_to_value.get(elem_id)
                    if value is not None:
                        processed_value = self._process_parameter_value(
                            param_name, value, reg_info["param_config"]
                        )
                        if processed_value is not None:
                            params[param_name] = processed_value

        # optimizer_argsの収集（新方式）
        if self.optimizer_args_inputs:
            optimizer_args_count = len(self.optimizer_args_inputs)
            optimizer_args_values = args[-optimizer_args_count:]
            optimizer_args = self.optimizer_ui.collect_optimizer_args(
                *optimizer_args_values
            )
            if optimizer_args:
                params["optimizer_args"] = optimizer_args

        return params

    def _process_parameter_value(
        self, param_name: str, value: Any, param_config: Any
    ) -> Any:
        """パラメータ値の型変換"""
        if not param_config:
            return str(value)

        try:
            if param_config.param_type == "bool":
                return bool(value)
            elif param_config.param_type == "int":
                return int(value) if value != "" else param_config.default_value
            elif param_config.param_type == "float":
                return float(value) if value != "" else param_config.default_value
            else:
                return str(value) if value != "" else param_config.default_value
        except (ValueError, TypeError):
            return param_config.default_value

    def generate_commands(self, *args) -> Tuple[str, str, str, str]:
        """コマンド生成（ファイル検証付き）"""
        try:
            newline_option = args[-1]
            param_args = args[:-1]

            params = self.collect_parameters(*param_args)

            # ファイルパラメータ検証
            validation_messages = []
            file_params = {
                "dit": "dit",
                "vae": "vae",
                "text_encoder": "text_encoder",
                "config_file": "config_file",
                "dataset_config": "dataset_config",
            }

            from core.validation.cli_file_validator import get_cli_file_validator

            validator = get_cli_file_validator()

            for param_key, param_name in file_params.items():
                file_path = params.get(param_key, "")

                # UIから実際の値を取得
                for component in self.all_inputs:
                    if (
                        hasattr(component, "elem_id")
                        and component.elem_id == f"param-{param_key}-value"
                    ):
                        component_idx = self.all_inputs.index(component)
                        actual_value = (
                            param_args[component_idx]
                            if component_idx < len(param_args)
                            else file_path
                        )
                        break
                else:
                    actual_value = file_path

                # チェックボックスが有効で実際のUIの値がブランクの場合
                if param_key in params and (
                    not actual_value or not actual_value.strip()
                ):
                    validation_messages.append(
                        f"⚠️ --{param_name}: パスが入力されていません"
                    )
                elif actual_value and actual_value.strip():
                    is_valid, message = validator.validate_file_path(
                        actual_value, param_name
                    )
                    if not is_valid:
                        validation_messages.append(f"⚠️ {message}")

            commands = self.command_generator.generate_all_commands(
                params, newline_option
            )

            # 検証結果をステータスに含める
            if validation_messages:
                status_message = "✅ コマンド生成完了！\n" + "\n".join(
                    validation_messages
                )
            else:
                status_message = "✅ コマンド生成完了！"

            return (
                status_message,
                commands["precache"],
                commands["text_encoder"],
                commands["training"],
            )
        except Exception as e:
            return f"❌ エラー: {str(e)}", "", "", ""

    def load_preset_stage1(
        self, filename: str, optimizer_type_comp: Any, all_components: List[Any]
    ) -> Tuple[str, ...]:
        """
        段階的プリセット読み込み - 第1段階（基本パラメータ）
        設計方針: optimizer_argsの段階的更新アプローチを実装
        """
        try:
            # プリセットファイルの読み込み
            success, params, message = self._load_preset_file(filename)
            if not success:
                return tuple([message] + [gr.update() for _ in all_components])  # type: ignore

            # optimizer_args以外のパラメータを更新
            updates = []
            for component in all_components:
                if hasattr(component, "elem_id") and component.elem_id:
                    if "optimizer_type" in component.elem_id:
                        # optimizer_type専用処理
                        param_name = self._extract_param_name(component.elem_id)
                        if param_name in params:
                            updates.append(gr.update(value=params[param_name]))
                        else:
                            updates.append(gr.update())
                    else:
                        # 通常パラメータ処理
                        param_name = self._extract_param_name(component.elem_id)
                        if param_name in params and param_name != "optimizer_args":
                            updates.append(gr.update(value=params[param_name]))
                        else:
                            updates.append(gr.update())
                else:
                    updates.append(gr.update())

            return tuple(["✅ プリセット読み込み完了（第1段階）"] + updates)  # type: ignore

        except Exception as e:
            return tuple(
                [f"❌ エラー（第1段階）: {str(e)}"]
                + [gr.update() for _ in all_components]  # type: ignore
            )

    def load_preset_stage2_delayed_args(
        self, optimizer_args_components: List[Any]
    ) -> List[Any]:
        """
        段階的プリセット読み込み - 第2段階（optimizer_args専用遅延適用）
        設計方針: 段階的更新アプローチでoptimizer_argsの値設定を確実に実行
        """
        try:
            # 遅延適用のためのデータが存在するかチェック
            if (
                hasattr(self, "_pending_optimizer_args")
                and self._pending_optimizer_args
            ):
                # optimizer_argsの値を適用
                updates = []
                for component in optimizer_args_components:
                    if hasattr(component, "elem_id") and component.elem_id:
                        elem_id = component.elem_id
                        if elem_id in self._pending_optimizer_args:
                            updates.append(
                                gr.update(value=self._pending_optimizer_args[elem_id])
                            )
                        else:
                            updates.append(gr.update())
                    else:
                        updates.append(gr.update())

                # 遅延データをクリア
                self._pending_optimizer_args = None

                return updates
            else:
                return [gr.update() for _ in optimizer_args_components]

        except Exception as e:
            print(f"段階的更新エラー（第2段階）: {e}")
            return [gr.update() for _ in optimizer_args_components]

    def _load_preset_file(self, filename: str) -> Tuple[bool, Dict[str, Any], str]:
        """プリセットファイルの読み込み（共通処理）"""
        try:
            # PresetManagerV2を使用してプリセットを読み込み
            if hasattr(self, "preset_manager"):
                params = self.preset_manager.load_preset(filename)
                if params:
                    return True, params, "プリセット読み込み成功"
                else:
                    return False, {}, "プリセットファイルが見つかりません"
            else:
                return False, {}, "プリセットマネージャーが初期化されていません"

        except Exception as e:
            return False, {}, f"プリセット読み込みエラー: {str(e)}"

    def _extract_param_name(self, elem_id: str) -> str:
        """elem_idからパラメータ名を抽出"""
        if elem_id.startswith("param-"):
            parts = elem_id.split("-")
            if len(parts) >= 3:
                return parts[1]  # param-{name}-{role} から {name} を抽出
        return ""

    def store_pending_optimizer_args(self, optimizer_args_data: Dict[str, Any]):
        """optimizer_argsの遅延適用用データを保存"""
        self._pending_optimizer_args = optimizer_args_data

    def launch_queue_system_callback(self):
        """キューシステム起動ボタンのコールバック"""
        success, message, pid = self.queue_manager.launch_queue_system()
        return message

    def update_queue_status(self):
        """キューシステム状態更新"""
        return self.queue_manager.get_status_message()


def create_interface_v4() -> gr.Blocks:
    """
    V4インターフェース - 識別子ベース静的UI実装
    設計方針:
    1. 識別子ベース静的UI実装を採用（改修案1を完全実装）
    2. プリセット/コマンド生成の完全互換性維持（elem_idによる識別子管理継続）
    3. 現在の見た目を完全に維持
    4. UIコンポーネント配置のみを静的化、ビジネスロジックは既存のまま
    5. component_registryの仕組みをそのまま活用
    6. optimizer_argsは動的実装を維持（テンプレート駆動型）
    """
    collector = ParameterCollectorV4()

    # PresetManagerV2とUIを初期化（OptimizerArgsManager連携）
    preset_manager = PresetManagerV2("data/presets/", collector.optimizer_args_manager)

    # 新規統合プリセット読み込みコントローラーを初期化
    preset_load_controller = PresetLoadController(preset_manager, collector)

    # デフォルトオプティマイザーのレジストリを初期化
    default_optimizer = (
        collector.template_manager.get_optimizer_choices()[0]
        if collector.template_manager.get_optimizer_choices()
        else None
    )
    if default_optimizer:
        optimizer_config = collector.template_manager.get_optimizer(default_optimizer)
        if optimizer_config:
            collector.optimizer_ui.args_registry.register_args(
                default_optimizer, optimizer_config.arguments
            )

    # OptimizerUIV3のargs_registryとcollectorを使用
    preset_ui = PresetUIV3(
        preset_manager, collector.optimizer_ui.args_registry, collector
    )

    # カスタムCSS：テーマ切り替え + フォントサイズ調整 + 既存スタイル
    custom_css = """
    /* ファイルパス検証用 赤枠スタイル（エラー時のみ） - 高優先度 */
    #param-dit-value.error input, #param-dit-value.error textarea, #param-dit-value.error input[type="text"],
    #param-vae-value.error input, #param-vae-value.error textarea, #param-vae-value.error input[type="text"],
    #param-text_encoder-value.error input, #param-text_encoder-value.error textarea, #param-text_encoder-value.error input[type="text"],
    #param-config_file-value.error input, #param-config_file-value.error textarea, #param-config_file-value.error input[type="text"],
    #param-dataset_config-value.error input, #param-dataset_config-value.error textarea, #param-dataset_config-value.error input[type="text"],
    div#param-dit-value.error input, div#param-vae-value.error input, div#param-text_encoder-value.error input,
    div#param-config_file-value.error input, div#param-dataset_config-value.error input,
    .gradio-container #param-dit-value.error input, .gradio-container #param-vae-value.error input,
    .gradio-container #param-text_encoder-value.error input, .gradio-container #param-config_file-value.error input,
    .gradio-container #param-dataset_config-value.error input {
        border: 4px solid #ff0000 !important;
        background-color: #ffe6e6 !important;
        color: #ff0000 !important;
        box-shadow: 0 0 10px rgba(255, 0, 0, 0.5) !important;
        outline: 2px solid #ff0000 !important;
    }
    
    /* エラー時フォーカススタイル - さらに強調 */
    #param-dit-value.error input:focus, #param-dit-value.error textarea:focus,
    #param-vae-value.error input:focus, #param-vae-value.error textarea:focus,
    #param-text_encoder-value.error input:focus, #param-text_encoder-value.error textarea:focus,
    #param-config_file-value.error input:focus, #param-config_file-value.error textarea:focus,
    #param-dataset_config-value.error input:focus, #param-dataset_config-value.error textarea:focus,
    div#param-dit-value.error input:focus, div#param-vae-value.error input:focus,
    div#param-text_encoder-value.error input:focus, div#param-config_file-value.error input:focus,
    div#param-dataset_config-value.error input:focus {
        border: 4px solid #ff0000 !important;
        background-color: #ffe6e6 !important;
        color: #ff0000 !important;
        outline: 3px solid #ff0000 !important;
        outline-offset: 2px !important;
        box-shadow: 0 0 15px rgba(255, 0, 0, 0.7) !important;
    }
    
    /* 正常時は通常スタイル（デフォルト） */
    #param-dit-value input,
    #param-dit-value textarea {
        /* 通常スタイルはGradioのデフォルトを使用 */
    }
    
    /* テーマとフォントサイズ調整UI */
    #theme-selector {
        min-width: 120px;
    }
    #font-size-slider {
        min-width: 150px;
    }
    #font-reset-btn {
        background: linear-gradient(90deg, #6366f1, #4f46e5) !important;
        color: white !important;
    }
    
    /* キューシステム起動ボタン - 緑色スタイル */
    #queue-launch-btn {
        background-color: #10b981 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        cursor: pointer !important;
    }
    
    #queue-launch-btn:hover {
        background-color: #059669 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    }
    
    #queue-launch-btn:active {
        background-color: #047857 !important;
        transform: translateY(0) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }
    
    #queue-launch-btn:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
        transform: none !important;
    }
    
    #queue-launch-btn:focus {
        outline: none !important;
        box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3) !important;
        border: 1px solid #4f46e5 !important;
    }
    #font-reset-btn:hover {
        background: linear-gradient(90deg, #4f46e5, #3730a3) !important;
    }
    
    /* ダークテーマ用CSS */
    .dark-theme {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
    }
    .dark-theme .gradio-container {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
    }
    .dark-theme .gradio-accordion {
        background-color: #2d2d2d !important;
        border: 1px solid #404040 !important;
    }
    .dark-theme .gradio-accordion .label-wrap {
        color: #ffffff !important;
    }
    .dark-theme input, .dark-theme textarea, .dark-theme select {
        background-color: #333333 !important;
        color: #ffffff !important;
        border: 1px solid #555555 !important;
    }
    .dark-theme .gradio-button {
        background-color: #4a4a4a !important;
        color: #ffffff !important;
        border: 1px solid #666666 !important;
    }
    .dark-theme .gradio-button:hover {
        background-color: #5a5a5a !important;
    }
    
    /* テキストフィールドのフォントサイズ調整用クラス */
    .custom-font-size input[type="text"],
    .custom-font-size input[type="number"],
    .custom-font-size textarea,
    .custom-font-size select {
        font-size: var(--custom-font-size, 14px) !important;
    }
    
    #preset_load_btn {
        background: linear-gradient(90deg, #3b82f6, #2563eb) !important;
        color: white !important;
        border: 1px solid #2563eb !important;
    }
    #preset_load_btn:hover {
        background: linear-gradient(90deg, #2563eb, #1d4ed8) !important;
    }
    
    /* トグルボタン用CSS */
    .section-toggle {
        width: 20px !important;
        height: 20px !important;
        min-width: 20px !important;
        min-height: 20px !important;
        font-size: 12px !important;
        border-radius: 4px !important;
        transition: all 0.15s ease !important;
        background: linear-gradient(135deg, #22c55e20, #16a34a20) !important;
        border: 1px solid #22c55e !important;
        color: #22c55e !important;
        font-weight: bold !important;
        margin: 2px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    .section-toggle:hover {
        transform: scale(1.1) !important;
        background: linear-gradient(135deg, #22c55e40, #16a34a40) !important;
        box-shadow: 0 2px 6px rgba(34, 197, 94, 0.3) !important;
    }
    
    .section-toggle:active {
        transform: scale(0.9) !important;
    }
    
    /* アコーディオンヘッダーのスタイリング改善 */
    .gradio-accordion .label-wrap {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #374151 !important;
    }
    
    /* プリセット削除ボタンを赤色に変更 */
    #preset_delete_btn {
        background: linear-gradient(90deg, #ef4444, #dc2626) !important;
        color: white !important;
        border: 1px solid #dc2626 !important;
    }
    #preset_delete_btn:hover {
        background: linear-gradient(90deg, #dc2626, #b91c1c) !important;
        box-shadow: 0 2px 6px rgba(220, 38, 38, 0.3) !important;
    }
    
    /* コマンド生成ボタンをオレンジ色に変更 */
    #generate_command_btn {
        background: linear-gradient(90deg, #f97316, #ea580c) !important;
        color: white !important;
        border: 1px solid #ea580c !important;
    }
    #generate_command_btn:hover {
        background: linear-gradient(90deg, #ea580c, #c2410c) !important;
        box-shadow: 0 2px 6px rgba(234, 88, 12, 0.3) !important;
    }
    """

    with gr.Blocks(
        title="QWEN-Image LoRA GUI v4", css=custom_css, theme=gr.themes.Soft()
    ) as demo:
        # テーマとフォントサイズ調整UI（最上部右上）
        with gr.Row():
            with gr.Column(scale=3):
                gr.Markdown("""
                QWEN-Image LoRA GUI v4
                """)
            with gr.Column(scale=1, min_width=600):
                # 2つのグループを横並びで配置
                with gr.Row():
                    # 左側: キューシステムグループ
                    with gr.Group():
                        queue_launch_btn = gr.Button(
                            "🚀 キューシステム起動",
                            variant="secondary",
                            elem_id="queue-launch-btn",
                        )
                        queue_status = gr.Markdown(
                            "STOPPED: キューシステム停止中", elem_id="queue-status"
                        )

                    # 右側: 表示設定グループ
                    with gr.Group():
                        gr.Markdown("### ⚙️ 表示設定")
                        font_size_slider = gr.Slider(
                            minimum=10,
                            maximum=24,
                            value=14,
                            step=1,
                            label="フォントサイズ",
                            elem_id="font-size-slider",
                        )

        # プリセット管理UI（最上部に配置）
        with gr.Accordion("📁 プリセット管理", open=False):
            preset_ui_components = preset_ui.create_ui()

        gr.Markdown("---")

        with gr.Tabs():
            all_inputs = []

            # タブ1: モデル・出力（トグル機能付き）
            with gr.TabItem("1.モデル・出力"):
                model_params = collector.parameters["モデル・出力"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_model_btn = gr.Button(
                        "🔽",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="expand-all-model",
                    )
                    collapse_all_model_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-model",
                    )

                # 1.1 基本出力設定 (3個のパラメータ)
                with gr.Accordion(
                    "📁 1.1 基本出力設定",
                    open=True,
                    elem_id="basic-output-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_basic_output = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            basic_output_inputs = collector.create_parameters_ui(
                                model_params[4:7], "three_column"
                            )
                            all_inputs.extend(basic_output_inputs)

                # 1.2 モデルパス設定 (4個のパラメータ)
                with gr.Accordion(
                    "🤖 1.2 モデルパス設定",
                    open=True,
                    elem_id="model-path-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_model_path = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            model_path_inputs = collector.create_parameters_ui(
                                model_params[:4], "two_column"
                            )
                            all_inputs.extend(model_path_inputs)

                # 1.3 保存スケジュール設定 (8個のパラメータ)
                with gr.Accordion(
                    "💾 1.3 保存スケジュール設定",
                    open=True,
                    elem_id="save-schedule-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_save_schedule = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            save_schedule_inputs = collector.create_parameters_ui(
                                model_params[7:15], "three_column"
                            )
                            all_inputs.extend(save_schedule_inputs)

                # 1.4 メタデータ設定 (6個のパラメータ)
                with gr.Accordion(
                    "📝 1.4 メタデータ設定",
                    open=True,
                    elem_id="metadata-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_metadata = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            metadata_inputs = collector.create_parameters_ui(
                                model_params[15:], "three_column"
                            )
                            all_inputs.extend(metadata_inputs)

                # トグル機能の実装
                # 1.モデル・出力タブ - 各セクション全チェック機能（JavaScript実装）
                toggle_model_path.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('model-path-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_basic_output.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('basic-output-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_save_schedule.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('save-schedule-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_metadata.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('metadata-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

            # タブ2: 基本学習設定
            with gr.TabItem("2.基本学習設定"):
                basic_params = collector.parameters["基本学習"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_basic_btn = gr.Button(
                        "🔽",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="expand-all-basic",
                    )
                    collapse_all_basic_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-basic",
                    )

                # 2.1 基本パラメータ (6個のパラメータ)
                with gr.Accordion(
                    "⚙️ 2.1 基本パラメータ",
                    open=True,
                    elem_id="basic-parameters-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_basic_param = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            basic_param_inputs = collector.create_parameters_ui(
                                basic_params[:6], "three_column"
                            )
                            all_inputs.extend(basic_param_inputs)

                # 2.2 最適化設定 (5個のパラメータ)
                with gr.Accordion(
                    "🔧 2.2 最適化設定",
                    open=True,
                    elem_id="optimization-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_optimization = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            optimization_inputs = collector.create_parameters_ui(
                                basic_params[8:13], "three_column"
                            )
                            all_inputs.extend(optimization_inputs)

                # 2.3 データローダー設定 (2個のパラメータ)
                with gr.Accordion(
                    "🔄 2.3 データローダー設定",
                    open=True,
                    elem_id="dataloader-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_dataloader = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            dataloader_inputs = collector.create_parameters_ui(
                                basic_params[6:8], "two_column"
                            )
                            all_inputs.extend(dataloader_inputs)

                # 2.4 その他引数 (カスタム引数)
                with gr.Accordion(
                    "📝 2.4 その他引数", open=True, elem_id="other-args-accordion"
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_custom_args = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：カスタム引数入力
                        with gr.Column(scale=1):
                            with gr.Row():
                                custom_args_enabled = gr.Checkbox(
                                    label="有効",
                                    value=False,
                                    interactive=True,
                                    scale=0,
                                    min_width=80,
                                    elem_id="param-custom_args-enabled",
                                )
                                custom_args_input = gr.Textbox(
                                    label="自由引数（コマンド末尾に追加）",
                                    value="",
                                    placeholder="例: --some_new_arg value --another_flag",
                                    info="引数名なしでコマンド末尾に追加されます",
                                    scale=3,
                                    interactive=True,
                                    elem_id="param-custom_args-value",
                                )
                            custom_args_inputs = [
                                custom_args_enabled,
                                custom_args_input,
                            ]
                            all_inputs.extend(custom_args_inputs)

                            # custom_argsをレジストリに登録
                            collector.register_component(
                                "param-custom_args-enabled",
                                custom_args_enabled,
                                "custom_args",
                                "enabled",
                            )
                            collector.register_component(
                                "param-custom_args-value",
                                custom_args_input,
                                "custom_args",
                                "value",
                            )

                # 2.基本学習設定タブ - 各セクション全チェック機能（JavaScript実装）
                toggle_basic_param.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('basic-parameters-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_optimization.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('optimization-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_dataloader.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('dataloader-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_custom_args.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('other-args-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                # 基本学習設定タブ - 一括開閉ボタンイベント
                expand_all_basic_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Expanding all basic learning accordions...');
                        const accordionIds = [
                            'basic-parameters-accordion',
                            'optimization-settings-accordion',
                            'dataloader-settings-accordion',
                            'other-args-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && !button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

                collapse_all_basic_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Collapsing all basic learning accordions...');
                        const accordionIds = [
                            'basic-parameters-accordion',
                            'optimization-settings-accordion',
                            'dataloader-settings-accordion',
                            'other-args-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

            # タブ3: オプティマイザー・学習率設定（新実装）
            with gr.TabItem("3.オプティマイザー・学習率設定"):
                opt_lr_params = collector.parameters["オプティマイザー・学習率"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_optimizer_btn = gr.Button(
                        "🔽",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="expand-all-optimizer",
                    )
                    collapse_all_optimizer_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-optimizer",
                    )

                # 3.1 オプティマイザー設定（テンプレート駆動型）
                with gr.Accordion(
                    "🔧 3.1 オプティマイザー設定",
                    open=True,
                    elem_id="optimizer-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_optimizer_type = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            with gr.Row():
                                with gr.Column(scale=1):
                                    enabled_cb, optimizer_type_comp = (
                                        collector.optimizer_ui.create_optimizer_selection_ui()
                                    )
                                    opt_type_inputs = [enabled_cb, optimizer_type_comp]
                                    all_inputs.extend(opt_type_inputs)

                                    # optimizer_typeをレジストリに登録
                                    collector.register_component(
                                        "param-optimizer_type-enabled",
                                        enabled_cb,
                                        "optimizer_type",
                                        "enabled",
                                        opt_lr_params[0],
                                    )
                                    collector.register_component(
                                        "param-optimizer_type-value",
                                        optimizer_type_comp,
                                        "optimizer_type",
                                        "value",
                                        opt_lr_params[0],
                                    )

                                with gr.Column(scale=1):
                                    # オプティマイザー説明
                                    optimizer_description = gr.Markdown(
                                        "", elem_id="optimizer-description"
                                    )

                # 3.2 optimizer_args UI（テンプレート駆動型・動的UI・トグル付き）
                (
                    optimizer_args_container,
                    optimizer_args_components,
                    toggle_optimizer_args,
                ) = collector.optimizer_ui.create_arguments_container()
                collector.optimizer_args_inputs = optimizer_args_components

                # 3.3 学習率設定
                with gr.Accordion(
                    "📈 3.3 学習率設定",
                    open=True,
                    elem_id="learning-rate-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_lr_settings = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            lr_inputs = collector.create_parameters_ui(
                                opt_lr_params[1:], "three_column"
                            )
                            all_inputs.extend(lr_inputs)

                # 3.オプティマイザー・学習率設定タブ - 各セクション全チェック機能（JavaScript実装）
                toggle_optimizer_type.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('optimizer-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_lr_settings.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('learning-rate-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_optimizer_args.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('optimizer-args-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                # オプティマイザー・学習率設定タブ - 一括開閉ボタンイベント
                expand_all_optimizer_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Expanding all optimizer accordions...');
                        const accordionIds = [
                            'optimizer-settings-accordion',
                            'optimizer-args-accordion',
                            'learning-rate-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && !button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

                collapse_all_optimizer_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Collapsing all optimizer accordions...');
                        const accordionIds = [
                            'optimizer-settings-accordion',
                            'optimizer-args-accordion',
                            'learning-rate-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

            # タブ4: ネットワーク
            with gr.TabItem("4.ネットワーク"):
                network_params = collector.parameters["ネットワーク"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_network_btn = gr.Button(
                        "🔽",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="expand-all-network",
                    )
                    collapse_all_network_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-network",
                    )

                # 4.1 ネットワーク設定（10項目）
                with gr.Accordion(
                    "🔗 4.1 ネットワーク設定",
                    open=True,
                    elem_id="network-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_network_settings = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            network_settings_inputs = collector.create_parameters_ui(
                                network_params[:10], "three_column"
                            )
                            all_inputs.extend(network_settings_inputs)

                # 4.2 タイムステップ設定（12項目）
                with gr.Accordion(
                    "⏱️ 4.2 タイムステップ設定",
                    open=True,
                    elem_id="timestep-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_timestep = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            timestep_inputs = collector.create_parameters_ui(
                                network_params[10:], "three_column"
                            )
                            all_inputs.extend(timestep_inputs)

                # 4.ネットワークタブ - 各セクション全チェック機能（JavaScript実装）
                toggle_network_settings.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('network-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_timestep.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('timestep-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                # ネットワークタブ - 一括開閉ボタンイベント
                expand_all_network_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Expanding all network accordions...');
                        const accordionIds = [
                            'network-settings-accordion',
                            'timestep-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && !button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

                collapse_all_network_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Collapsing all network accordions...');
                        const accordionIds = [
                            'network-settings-accordion',
                            'timestep-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

            # タブ5: パフォーマンス
            with gr.TabItem("5.パフォーマンス"):
                perf_params = collector.parameters["パフォーマンス"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_performance_btn = gr.Button(
                        "🔽",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="expand-all-performance",
                    )
                    collapse_all_performance_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-performance",
                    )

                # 5.1 アテンション最適化（6項目）
                with gr.Accordion(
                    "🔍 5.1 アテンション最適化",
                    open=True,
                    elem_id="attention-optimization-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_attention = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            attention_inputs = collector.create_parameters_ui(
                                perf_params[:6], "three_column"
                            )
                            all_inputs.extend(attention_inputs)

                # 5.2 精度・メモリ最適化（5項目）
                with gr.Accordion(
                    "💾 5.2 精度・メモリ最適化",
                    open=True,
                    elem_id="precision-memory-optimization-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_memory = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            memory_inputs = collector.create_parameters_ui(
                                perf_params[6:11], "three_column"
                            )
                            all_inputs.extend(memory_inputs)

                # 5.3 コンパイル最適化（4項目）
                with gr.Accordion(
                    "⚡ 5.3 コンパイル最適化",
                    open=True,
                    elem_id="compile-optimization-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_compile = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            compile_inputs = collector.create_parameters_ui(
                                perf_params[11:15], "three_column"
                            )
                            all_inputs.extend(compile_inputs)

                # 5.4 分散処理設定（3項目）
                with gr.Accordion(
                    "🌐 5.4 分散処理設定",
                    open=True,
                    elem_id="distributed-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_distributed = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            distributed_inputs = collector.create_parameters_ui(
                                perf_params[15:], "three_column"
                            )
                            all_inputs.extend(distributed_inputs)

                # 5.パフォーマンスタブ - 各セクション全チェック機能（JavaScript実装）
                toggle_attention.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('attention-optimization-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_memory.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('precision-memory-optimization-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_compile.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('compile-optimization-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_distributed.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('distributed-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                # パフォーマンスタブ - 一括開閉ボタンイベント
                expand_all_performance_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Expanding all performance accordions...');
                        const accordionIds = [
                            'attention-optimization-accordion',
                            'precision-memory-optimization-accordion',
                            'compile-optimization-accordion',
                            'distributed-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && !button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

                collapse_all_performance_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Collapsing all performance accordions...');
                        const accordionIds = [
                            'attention-optimization-accordion',
                            'precision-memory-optimization-accordion',
                            'compile-optimization-accordion',
                            'distributed-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

            # タブ6: ログ・監視
            with gr.TabItem("6.ログ・監視"):
                log_params = collector.parameters["ログ・監視"]

                # アコーディオン一括開閉ボタン
                with gr.Row():
                    expand_all_log_btn = gr.Button(
                        "🔽", size="sm", scale=0, min_width=35, elem_id="expand-all-log"
                    )
                    collapse_all_log_btn = gr.Button(
                        "🔼",
                        size="sm",
                        scale=0,
                        min_width=35,
                        elem_id="collapse-all-log",
                    )

                # 6.1 ログ出力設定（8項目）
                with gr.Accordion(
                    "📝 6.1 ログ出力設定",
                    open=True,
                    elem_id="log-output-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_log_output = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            log_output_inputs = collector.create_parameters_ui(
                                log_params[:8], "three_column"
                            )
                            all_inputs.extend(log_output_inputs)

                # 6.2 サンプリング設定（4項目）
                with gr.Accordion(
                    "🎲 6.2 サンプリング設定",
                    open=True,
                    elem_id="sampling-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_sampling = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            sampling_inputs = collector.create_parameters_ui(
                                log_params[8:12], "three_column"
                            )
                            all_inputs.extend(sampling_inputs)

                # 6.3 外部連携設定（8項目）
                with gr.Accordion(
                    "🔗 6.3 外部連携設定（HuggingFace等）",
                    open=True,
                    elem_id="external-integration-settings-accordion",
                ):
                    with gr.Row():
                        # 左列：トグルボタン
                        with gr.Column(scale=0, min_width=30):
                            toggle_external = gr.Button(
                                "☑️",
                                size="sm",
                                variant="secondary",
                                elem_classes="section-toggle",
                            )

                        # 右列：既存のUI
                        with gr.Column(scale=1):
                            external_inputs = collector.create_parameters_ui(
                                log_params[12:], "three_column"
                            )
                            all_inputs.extend(external_inputs)

                # 6.ログ・監視タブ - 各セクション全チェック機能（JavaScript実装）
                toggle_log_output.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('log-output-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_sampling.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('sampling-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                toggle_external.click(
                    fn=None,
                    js="""
                    function() {
                        const accordion = document.getElementById('external-integration-settings-accordion');
                        if (accordion) {
                            const checkboxes = accordion.querySelectorAll('input[type="checkbox"]');
                            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                            checkboxes.forEach(cb => cb.checked = !allChecked);
                            checkboxes.forEach(cb => cb.dispatchEvent(new Event('change')));
                        }
                    }
                    """,
                )

                # ログ・監視タブ - 一括開閉ボタンイベント
                expand_all_log_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Expanding all log accordions...');
                        const accordionIds = [
                            'log-output-settings-accordion',
                            'sampling-settings-accordion',
                            'external-integration-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && !button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

                collapse_all_log_btn.click(
                    fn=None,
                    js="""
                    function() {
                        console.log('Collapsing all log accordions...');
                        const accordionIds = [
                            'log-output-settings-accordion',
                            'sampling-settings-accordion',
                            'external-integration-settings-accordion'
                        ];
                        
                        accordionIds.forEach(accordionId => {
                            const accordion = document.getElementById(accordionId);
                            if (accordion) {
                                const button = accordion.querySelector('button');
                                if (button && button.classList.contains('open')) {
                                    button.click();
                                }
                            }
                        });
                    }
                    """,
                )

        # コマンド生成UI
        with gr.Row():
            newline_option = gr.Checkbox(label="改行あり", value=True)
            generate_btn = gr.Button(
                "🚀 コマンド生成", variant="primary", elem_id="generate_command_btn"
            )

        # 結果表示
        with gr.Column():
            status_output = gr.Textbox(label="📊 生成状況", interactive=False)
            with gr.Tabs():
                with gr.TabItem("1.潜在変数キャッシュ作成"):
                    precache_output = gr.Code(
                        label="Pre-cache コマンド", language="shell", interactive=True
                    )
                with gr.TabItem("2.TEキャッシュ作成"):
                    text_encoder_output = gr.Code(
                        label="Text Encoderキャッシュ コマンド",
                        language="shell",
                        interactive=True,
                    )
                with gr.TabItem("3.学習コマンド"):
                    training_output = gr.Code(
                        label="Training コマンド", language="shell", interactive=True
                    )

        # コマンド実行UI
        with gr.Row():
            gr.Markdown("---")  # 区切り線

        with gr.Row():
            gr.Markdown("### 🚀 コマンド実行")

        with gr.Row():
            with gr.Column(scale=1):
                execute_precache_btn = gr.Button(
                    "▶️ Pre-cache実行", variant="secondary", elem_id="execute-precache"
                )
            with gr.Column(scale=1):
                execute_text_encoder_btn = gr.Button(
                    "▶️ Text Encoder実行",
                    variant="secondary",
                    elem_id="execute-text-encoder",
                )
            with gr.Column(scale=1):
                execute_training_btn = gr.Button(
                    "▶️ Training実行", variant="primary", elem_id="execute-training"
                )

        # 実行状態表示
        # with gr.Row():
        #     execution_status = gr.Markdown("", elem_id="execution-status")  # 未使用のため削除

        # 実行中プロセス管理（ストリーミング表示）
        with gr.Accordion("📊 プロセス実行", open=True):
            # プロセス実行状態表示
            process_status = gr.Textbox(
                label="実行状態",
                value="準備完了",
                lines=2,
                max_lines=3,
                interactive=False,
                elem_id="process-status",
            )

            gr.Markdown(
                """
                **💡 使い方:**
                - コマンド実行ボタンを押すと新しいターミナルウィンドウが開きます
                - プロセスを停止するにはターミナルで **Ctrl+C** を押してください
                - 完了後は5秒で自動的にウィンドウが閉じます
                """
            )

        # all_inputsを登録
        collector.all_inputs = all_inputs

        # ファイルパラメータのコンポーネントを保存
        file_components = {}
        file_param_elem_ids = {
            "dit": "param-dit-value",
            "vae": "param-vae-value",
            "text_encoder": "param-text_encoder-value",
            "config_file": "param-config_file-value",
            "dataset_config": "param-dataset_config-value",
        }

        for param_name, elem_id in file_param_elem_ids.items():
            for component in all_inputs:
                if hasattr(component, "elem_id") and component.elem_id == elem_id:
                    file_components[param_name] = component
                    break

        # オプティマイザー動的更新の設定
        if optimizer_type_comp:

            def update_optimizer_ui_and_description(optimizer_type):
                """オプティマイザー変更時の更新"""
                # 重要: プルダウン変更時にlast_optimizer_typeを更新
                preset_load_controller.last_optimizer_type = optimizer_type

                ui_updates = collector.optimizer_ui.update_optimizer_ui(optimizer_type)
                description_text = collector.optimizer_ui.get_optimizer_description(
                    optimizer_type
                )
                return ui_updates + [description_text]

            # 動的更新設定
            outputs_list = (
                [optimizer_args_container]
                + optimizer_args_components
                + [optimizer_description]
            )
            optimizer_type_comp.change(
                fn=update_optimizer_ui_and_description,
                inputs=[optimizer_type_comp],
                outputs=outputs_list,
            )

            # 初回起動時にデフォルトオプティマイザーのUI表示
            # デフォルト値を取得（値のリストから）
            default_optimizer = (
                collector.template_manager.get_optimizer_choices()[0]
                if collector.template_manager.get_optimizer_choices()
                else None
            )
            if default_optimizer:
                demo.load(
                    fn=lambda: update_optimizer_ui_and_description(default_optimizer),
                    inputs=None,
                    outputs=outputs_list,
                )

        # コマンド生成イベントハンドラー（--dit検証付き）
        def generate_with_validation(*args):
            """コマンド生成と--dit UI更新"""
            # コマンド生成実行
            status, precache, text_encoder, training = collector.generate_commands(
                *args
            )

            # ファイル検証結果でUI更新
            file_updates = {}
            param_args = args[:-1]
            params = collector.collect_parameters(*param_args)

            from core.validation.cli_file_validator import get_cli_file_validator

            validator = get_cli_file_validator()

            # 各ファイルパラメータの検証とUI更新
            for param_name, component in file_components.items():
                if component:
                    file_path = params.get(param_name, "")

                    # 実際のUIコンポーネントから現在の値を取得
                    component_idx = (
                        all_inputs.index(component) if component in all_inputs else -1
                    )
                    actual_value = (
                        param_args[component_idx]
                        if component_idx >= 0 and component_idx < len(param_args)
                        else file_path
                    )

                    # チェックボックスが有効でUIの実際の値がブランクの場合
                    if param_name in params and (
                        not actual_value or not actual_value.strip()
                    ):
                        file_updates[param_name] = gr.update(
                            elem_classes=["error"], visible=True
                        )
                    elif actual_value and actual_value.strip():
                        is_valid, message = validator.validate_file_path(
                            actual_value, param_name
                        )

                        if not is_valid:
                            file_updates[param_name] = gr.update(
                                elem_classes=["error"], visible=True, value=actual_value
                            )
                        else:
                            file_updates[param_name] = gr.update(elem_classes=[])
                    else:
                        file_updates[param_name] = gr.update(elem_classes=[])
                else:
                    file_updates[param_name] = gr.update()

            # 返り値を構築
            return_values = [status, precache, text_encoder, training]
            for param_name in file_param_elem_ids.keys():
                if param_name in file_components and file_components[param_name]:
                    return_values.append(file_updates.get(param_name, gr.update()))

            return tuple(return_values)

        # 出力にファイルコンポーネントを追加
        outputs_list = [
            status_output,
            precache_output,
            text_encoder_output,
            training_output,
        ]
        for param_name in file_param_elem_ids.keys():
            if param_name in file_components and file_components[param_name]:
                outputs_list.append(file_components[param_name])

        generate_btn.click(
            fn=generate_with_validation,
            inputs=all_inputs + optimizer_args_components + [newline_option],
            outputs=outputs_list,
        )

        # 新しいストリーミングシステムを使用


        # ダイレクトターミナル実行ハンドラー
        def execute_precache_terminal(command_text: str):
            """プリキャッシュを新規ターミナルで実行"""
            result = direct_terminal_executor.execute_command("precache", command_text)
            return result["message"]

        def execute_text_encoder_terminal(command_text: str):
            """テキストエンコーダーを新規ターミナルで実行"""
            result = direct_terminal_executor.execute_command(
                "text_encoder", command_text
            )
            return result["message"]

        def execute_training_terminal(command_text: str):
            """トレーニングを新規ターミナルで実行"""
            result = direct_terminal_executor.execute_command("training", command_text)
            return result["message"]

        # イベントハンドラーの設定（ダイレクトターミナル実行方式）
        # Precache実行
        execute_precache_btn.click(
            fn=execute_precache_terminal,
            inputs=[precache_output],
            outputs=[process_status],
        )

        # Text Encoder実行
        execute_text_encoder_btn.click(
            fn=execute_text_encoder_terminal,
            inputs=[text_encoder_output],
            outputs=[process_status],
        )

        # Training実行
        execute_training_btn.click(
            fn=execute_training_terminal,
            inputs=[training_output],
            outputs=[process_status],
        )

        # プリセット機能のイベントハンドラー設定
        # 保存処理
        def save_preset_handler(preset_name_input, *args):
            """プリセット保存ハンドラー（elem_idベース）"""
            elem_id_to_value = {}

            # all_inputsとoptimizer_args_componentsから値を収集
            all_components = list(args)  # 全ての入力値

            # コンポーネントとelem_idのマッピング
            component_idx = 0
            for component in all_inputs + optimizer_args_components:
                if component_idx < len(all_components):
                    value = all_components[component_idx]
                    if hasattr(component, "elem_id") and component.elem_id:
                        elem_id_to_value[component.elem_id] = value
                    component_idx += 1

            return preset_ui.save_preset_with_elem_ids(
                preset_name_input, elem_id_to_value
            )

        preset_ui_components["save_btn"].click(
            fn=save_preset_handler,
            inputs=[preset_ui_components["preset_name"]]
            + all_inputs
            + optimizer_args_components,
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["confirm_row"],
                preset_ui_components["confirm_message"],
                preset_ui_components["confirm_yes"],
                preset_ui_components["confirm_no"],
            ],
        )

        # 上書き確認
        preset_ui_components["confirm_yes"].click(
            fn=preset_ui.confirm_overwrite,
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["confirm_row"],
                preset_ui_components["confirm_message"],
                preset_ui_components["confirm_yes"],
                preset_ui_components["confirm_no"],
            ],
        )

        preset_ui_components["confirm_no"].click(
            fn=preset_ui.cancel_overwrite,
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["confirm_row"],
                preset_ui_components["confirm_message"],
                preset_ui_components["confirm_yes"],
                preset_ui_components["confirm_no"],
            ],
        )

        # 段階的プリセット読み込み処理（設計方針: 段階的更新アプローチ）
        def safe_preset_load(filename):
            """
            段階的プリセット読み込み - 設計方針に基づく実装
            1. 第1段階: 基本パラメータ（optimizer_args以外）を読み込み
            2. 第2段階: optimizer_argsを遅延適用（0.2秒待機付き）
            """
            try:
                result = preset_load_controller.load_preset_unified(
                    filename, optimizer_type_comp, all_inputs, optimizer_args_components
                )
                return result
            except Exception:
                import traceback

                traceback.print_exc()
                raise

        # 段階的更新アプローチの実装
        preset_ui_components["load_btn"].click(
            fn=safe_preset_load,
            inputs=[preset_ui_components["dropdown"]],
            outputs=[preset_ui_components["status"]]
            + [preset_ui_components["preset_name"]]
            + all_inputs
            + optimizer_args_components,
        ).then(
            # 第2段階: optimizer_args専用遅延適用（段階的更新アプローチ）
            fn=lambda: preset_load_controller.apply_delayed_args_with_wait(
                optimizer_args_components
            ),
            inputs=[],
            outputs=optimizer_args_components,
        )

        # 削除処理
        preset_ui_components["delete_btn"].click(
            fn=preset_ui.delete_preset,
            inputs=[preset_ui_components["dropdown"]],
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["delete_confirm_row"],
                preset_ui_components["delete_confirm_message"],
                preset_ui_components["delete_confirm_yes"],
                preset_ui_components["delete_confirm_no"],
            ],
        )

        # 削除確認ボタンのイベント設定
        preset_ui_components["delete_confirm_yes"].click(
            fn=preset_ui.confirm_delete,
            inputs=[],
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["delete_confirm_row"],
                preset_ui_components["delete_confirm_message"],
                preset_ui_components["delete_confirm_yes"],
                preset_ui_components["delete_confirm_no"],
            ],
        )

        preset_ui_components["delete_confirm_no"].click(
            fn=preset_ui.cancel_delete,
            inputs=[],
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["dropdown"],
                preset_ui_components["delete_confirm_row"],
                preset_ui_components["delete_confirm_message"],
                preset_ui_components["delete_confirm_yes"],
                preset_ui_components["delete_confirm_no"],
            ],
        )

        # インポート処理ハンドラー（段階的更新アプローチ対応）
        def handle_import(uploaded_file):
            """
            インポートファイルを処理 - 段階的更新アプローチ対応
            設計方針: プリセットインポート時も段階的更新を適用
            """
            if not uploaded_file:
                return ("❌ ファイルが選択されていません",) + tuple(
                    gr.update() for _ in all_inputs + optimizer_args_components
                )

            try:
                # preset_load_controllerを使用してインポートファイルを読み込み
                import_result = preset_load_controller.load_preset_unified(
                    uploaded_file.name,
                    optimizer_type_comp,
                    all_inputs,
                    optimizer_args_components,
                )

                # 成功メッセージを先頭に追加（段階的更新の第1段階完了）
                if isinstance(import_result, tuple) and len(import_result) > 0:
                    return (
                        "✅ プリセットをインポートしました（第1段階完了）",
                    ) + import_result[1:]
                else:
                    return import_result

            except Exception as e:
                return (f"❌ インポートエラー: {str(e)}",) + tuple(
                    gr.update() for _ in all_inputs + optimizer_args_components
                )

        # インポートボタンのイベント（段階的更新アプローチ）
        preset_ui_components["import_btn"].upload(
            fn=handle_import,
            inputs=[preset_ui_components["import_btn"]],
            outputs=[preset_ui_components["status"]]
            + all_inputs
            + optimizer_args_components,
        ).then(
            # 第2段階: optimizer_args専用遅延適用（インポート時も段階的更新）
            fn=lambda: preset_load_controller.apply_delayed_args_with_wait(
                optimizer_args_components
            ),
            inputs=[],
            outputs=optimizer_args_components,
        )

        # エクスポート処理ハンドラー
        def handle_export(selected_preset):
            """エクスポート処理"""
            if not selected_preset:
                return "❌ エクスポートするプリセットを選択してください", None

            status_msg, export_path = preset_ui.export_preset(selected_preset)

            if export_path:
                # ファイルダウンロード用のFileコンポーネント更新
                return status_msg, gr.update(value=export_path, visible=True)
            else:
                return status_msg, gr.update(visible=False)

        # エクスポートボタンのイベント
        preset_ui_components["export_btn"].click(
            fn=handle_export,
            inputs=[preset_ui_components["dropdown"]],
            outputs=[
                preset_ui_components["status"],
                preset_ui_components["export_file"],
            ],
        )

        # 初期表示時にプリセット一覧を更新
        demo.load(
            fn=preset_ui.refresh_preset_list,
            outputs=[preset_ui_components["dropdown"]],
        )

        # キューシステム関連のイベントハンドラー
        # 初回状態更新
        demo.load(fn=collector.update_queue_status, outputs=[queue_status])

        # キューシステム起動ボタン
        queue_launch_btn.click(
            fn=collector.launch_queue_system_callback, outputs=[queue_status]
        )

        # フォントサイズ調整のイベントハンドラーを設定

        font_size_slider.change(
            fn=None,
            inputs=[font_size_slider],
            js="""
            function(size) {
                document.documentElement.style.setProperty('--custom-font-size', size + 'px');
                document.body.classList.add('custom-font-size');
                
                // フォントサイズに基づく比率計算（14pxを基準）
                const baseSize = 14;
                const sizeRatio = size / baseSize;
                
                // テキストフィールドにフォントサイズと枠サイズを適用
                const selectors = [
                    'input[type="text"]',
                    'input[type="number"]',
                    'textarea',
                    'select'
                ];
                
                selectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(element => {
                        // フォントサイズ
                        element.style.fontSize = size + 'px';
                        
                        // 行の高さ（フォントサイズの1.2倍）
                        element.style.lineHeight = (size * 1.2) + 'px';
                        
                        // 要素タイプ別の高さ調整
                        if (element.tagName.toLowerCase() === 'textarea') {
                            // textareaは最小高さのみ調整（複数行対応）
                            element.style.minHeight = (size * 2.5) + 'px';
                        } else if (element.tagName.toLowerCase() === 'select') {
                            // selectは固定高さ
                            element.style.height = (size * 2.2) + 'px';
                        } else {
                            // input要素は固定高さ
                            element.style.height = (size * 2) + 'px';
                        }
                        
                        // パディング調整（フォントサイズに比例）
                        const basePadding = 8; // 基準パディング
                        const newPadding = Math.max(4, basePadding * sizeRatio);
                        element.style.paddingTop = newPadding + 'px';
                        element.style.paddingBottom = newPadding + 'px';
                        element.style.paddingLeft = newPadding + 'px';
                        element.style.paddingRight = newPadding + 'px';
                    });
                });
                
                console.log('Font and field size adjusted to:', size + 'px', 'ratio:', sizeRatio);
            }
            """,
        )

        # アコーディオン一括開閉のイベントハンドラー（1.モデル・出力タブ）
        expand_all_model_btn.click(
            fn=None,
            js="""
            function() {
                console.log('Expanding all model accordions...');
                const accordionIds = [
                    'model-path-settings-accordion',
                    'basic-output-settings-accordion',
                    'save-schedule-settings-accordion',
                    'metadata-settings-accordion'
                ];
                
                accordionIds.forEach(accordionId => {
                    const accordion = document.getElementById(accordionId);
                    if (accordion) {
                        const button = accordion.querySelector('button');
                        if (button && !button.classList.contains('open')) {
                            button.click();
                        }
                    }
                });
            }
            """,
        )

        collapse_all_model_btn.click(
            fn=None,
            js="""
            function() {
                console.log('Collapsing all model accordions...');
                const accordionIds = [
                    'model-path-settings-accordion',
                    'basic-output-settings-accordion',
                    'save-schedule-settings-accordion',
                    'metadata-settings-accordion'
                ];
                
                accordionIds.forEach(accordionId => {
                    const accordion = document.getElementById(accordionId);
                    if (accordion) {
                        const button = accordion.querySelector('button');
                        if (button && button.classList.contains('open')) {
                            button.click();
                        }
                    }
                });
            }
            """,
        )

        # リアルタイムログ表示用CSS（黒背景・緑文字）+ 初期化
        demo.load(
            fn=lambda: None,
            js="""
            function() {
                
                // 初期フォントサイズの設定（同じロジックを使用）
                const initializeFieldSizes = (size) => {
                    document.documentElement.style.setProperty('--custom-font-size', size + 'px');
                    document.body.classList.add('custom-font-size');
                    
                    const baseSize = 14;
                    const sizeRatio = size / baseSize;
                    
                    const selectors = [
                        'input[type="text"]',
                        'input[type="number"]',
                        'textarea',
                        'select'
                    ];
                    
                    selectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(element => {
                            element.style.fontSize = size + 'px';
                            element.style.lineHeight = (size * 1.2) + 'px';
                            
                            if (element.tagName.toLowerCase() === 'textarea') {
                                element.style.minHeight = (size * 2.5) + 'px';
                            } else if (element.tagName.toLowerCase() === 'select') {
                                element.style.height = (size * 2.2) + 'px';
                            } else {
                                element.style.height = (size * 2) + 'px';
                            }
                            
                            const basePadding = 8;
                            const newPadding = Math.max(4, basePadding * sizeRatio);
                            element.style.paddingTop = newPadding + 'px';
                            element.style.paddingBottom = newPadding + 'px';
                            element.style.paddingLeft = newPadding + 'px';
                            element.style.paddingRight = newPadding + 'px';
                        });
                    });
                };
                
                // 初期化実行
                initializeFieldSizes(14);
            }
            """,
        )


    return demo


# 互換性のためのエクスポート関数
def create_parameter_ui() -> gr.Blocks:
    """
    パラメータ収集UI v4を作成（互換性維持）

    設計方針に基づく実装:
    - 識別子ベース静的UI実装を採用
    - 現在の見た目を完全に維持
    - プリセット/コマンド生成の完全互換性維持
    - optimizer_argsは動的実装を維持（テンプレート駆動型）
    - 段階的更新アプローチでoptimizer_args値設定を確実に実行
    """
    return create_interface_v4()


if __name__ == "__main__":
    """
    V4のテスト実行 - 識別子ベース静的UI実装
    
    設計方針:
    1. 識別子ベース静的UI実装を採用（改修案1を完全実装）
    2. プリセット/コマンド生成の完全互換性維持
    3. 現在の見た目を完全に維持
    4. optimizer_argsは動的実装を維持（テンプレート駆動型）
    5. 段階的更新アプローチでoptimizer_args値設定を確実に実行
    """
    demo = create_interface_v4()
    demo.launch(debug=True, share=False)
