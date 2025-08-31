"""
オプティマイザーUIコンポーネント v3 (修正版)
完全テンプレート駆動型の実装
"""

import gradio as gr  # type: ignore
from typing import Any, Dict, List, Optional, Tuple

from apps.gui.components.optimizer_args_registry import OptimizerArgsRegistry
from core.presets.optimizer_template_manager import (
    ArgumentConfig,
    OptimizerTemplateManager,
    UIComponentType,
)


class OptimizerUIV3:
    """テンプレート駆動型オプティマイザーUI"""

    def __init__(self, template_manager: Optional[OptimizerTemplateManager] = None):
        """
        Args:
            template_manager: テンプレート管理インスタンス
        """
        self.template_manager = template_manager or OptimizerTemplateManager()
        self.args_registry = OptimizerArgsRegistry()  # レジストリを追加
        self.current_optimizer: Optional[str] = None
        self.current_components: Dict[str, Any] = {}  # arg_name -> component
        self.max_args = 20  # 最大引数数

    def create_optimizer_selection_ui(self) -> Tuple[Any, Any]:
        """オプティマイザー選択UIを作成"""
        # 値のリストのみを使用（表示名の問題を回避）
        optimizer_choices = self.template_manager.get_optimizer_choices()

        # 有効チェックボックス
        enabled_checkbox = gr.Checkbox(
            label="有効",
            value=True,
            scale=0,
            min_width=80,
            interactive=True,
            elem_id="param-optimizer_type-enabled",
        )

        # オプティマイザー選択ドロップダウン
        # 値のみのリストを使用
        default_value = optimizer_choices[0] if optimizer_choices else None
        optimizer_dropdown = gr.Dropdown(
            label="--optimizer_type",
            choices=optimizer_choices,
            value=default_value,
            scale=3,
            interactive=True,
            elem_id="param-optimizer_type-value",
        )

        return enabled_checkbox, optimizer_dropdown

    def create_arguments_container(self) -> Tuple[gr.Column, List[Any], Any]:
        """引数UIコンテナを作成（動的コンテンツ用）

        Returns:
            (コンテナ, コンポーネントリスト)
        """
        all_components = []

        with gr.Column(visible=False, elem_id="optimizer-args-container") as container:
            with gr.Accordion(
                "🔧 3.2 オプティマイザー引数",
                open=True,
                elem_id="optimizer-args-accordion",
            ):
                with gr.Row():
                    # 左列：トグルボタン
                    with gr.Column(scale=0, min_width=30):
                        toggle_optimizer_args = gr.Button(
                            "☑️",
                            size="sm",
                            variant="secondary",
                            elem_classes="section-toggle",
                        )

                    # 右列：引数UI
                    with gr.Column(scale=1):
                        # 3列レイアウト用に3つずつグループ化
                        for i in range(0, self.max_args, 3):
                            with gr.Row():
                                for j in range(3):
                                    arg_idx = i + j
                                    if arg_idx >= self.max_args:
                                        break

                                    with gr.Column():
                                        with gr.Row():
                                            # 有効チェックボックス
                                            enabled = gr.Checkbox(
                                                label="有効",
                                                value=False,
                                                scale=0,
                                                min_width=80,
                                                elem_id=f"opt-arg-{arg_idx}-enabled",
                                            )

                                            # Number入力
                                            number_input = gr.Number(
                                                label="",
                                                value=0,
                                                scale=3,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-number",
                                            )

                                            # Textbox（文字列・科学記法用）
                                            text_input = gr.Textbox(
                                                label="",
                                                value="",
                                                scale=3,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-text",
                                            )

                                            # Checkbox（bool用）
                                            checkbox_input = gr.Checkbox(
                                                label="",
                                                value=False,
                                                scale=3,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-checkbox",
                                            )

                                            # Dropdown（選択肢用）
                                            dropdown_input = gr.Dropdown(
                                                label="",
                                                choices=[],
                                                value=None,
                                                scale=3,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-dropdown",
                                            )

                                            # タプル入力用（2つの数値）
                                            tuple_input1 = gr.Number(
                                                label="値1",
                                                value=0.9,
                                                scale=1,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-tuple-1",
                                            )
                                            tuple_input2 = gr.Number(
                                                label="値2",
                                                value=0.999,
                                                scale=1,
                                                visible=False,
                                                elem_id=f"opt-arg-{arg_idx}-tuple-2",
                                            )

                                        all_components.extend(
                                            [
                                                enabled,
                                                number_input,
                                                text_input,
                                                checkbox_input,
                                                dropdown_input,
                                                tuple_input1,
                                                tuple_input2,
                                            ]
                                        )

        return container, all_components, toggle_optimizer_args

    def update_optimizer_ui(
        self,
        optimizer_type: str,
        preset_values: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Any]:
        """オプティマイザー変更時のUI更新

        Args:
            optimizer_type: 選択されたオプティマイザー名
            preset_values: プリセット値 {"arg_name": {"enabled": bool, "value": any}}

        Returns:
            各UIコンポーネントの更新情報
        """
        updates = []

        # コンテナの表示/非表示
        if not optimizer_type or optimizer_type == "Custom...":
            self.current_optimizer = None
            updates.append(gr.update(visible=False))  # container
            # すべての引数行を非表示
            for i in range(self.max_args):
                # 各行のコンポーネント（7個）
                updates.extend(
                    [
                        gr.update(visible=False),  # enabled
                        gr.update(visible=False),  # number
                        gr.update(visible=False),  # text
                        gr.update(visible=False, value=None),  # checkbox - valueをリセット
                        gr.update(visible=False),  # dropdown
                        gr.update(visible=False),  # tuple1
                        gr.update(visible=False),  # tuple2
                    ]
                )
            return updates

        # オプティマイザー設定を取得
        optimizer_config = self.template_manager.get_optimizer(optimizer_type)
        if not optimizer_config:
            updates.append(gr.update(visible=False))
            for i in range(self.max_args):
                updates.extend([gr.update(visible=False)] * 7)
            return updates

        # レジストリに引数を登録
        self.args_registry.register_args(optimizer_type, optimizer_config.arguments)

        # コンテナを表示
        self.current_optimizer = optimizer_type
        updates.append(gr.update(visible=True))

        # 引数UIを更新
        for i in range(self.max_args):
            if i < len(optimizer_config.arguments):
                arg = optimizer_config.arguments[i]
                # プリセット値があれば使用
                preset_value = None
                if preset_values and arg.name in preset_values:
                    preset_value = preset_values[arg.name]
                arg_updates = self._create_argument_ui_updates(arg, i, preset_value)
                updates.extend(arg_updates)
            else:
                # 未使用の行は非表示
                updates.extend(
                    [
                        gr.update(visible=False),  # enabled
                        gr.update(visible=False),  # number
                        gr.update(visible=False),  # text
                        gr.update(visible=False, value=None),  # checkbox - valueをリセット
                        gr.update(visible=False),  # dropdown
                        gr.update(visible=False),  # tuple1
                        gr.update(visible=False),  # tuple2
                    ]
                )

        return updates

    def _create_argument_ui_updates(
        self,
        arg: ArgumentConfig,
        arg_idx: int,
        preset_value: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """引数用UIの更新情報を作成

        Args:
            arg: 引数設定
            arg_idx: 引数インデックス
            preset_value: プリセット値 {"enabled": bool, "value": any}

        Returns:
            [enabled, number, text, checkbox, dropdown, tuple1, tuple2]の更新
        """
        ui_type = arg.get_ui_component_type()
        updates = []

        # プリセット値から取得、なければデフォルト
        enabled_value = preset_value.get("enabled", False) if preset_value else False
        actual_value = preset_value.get("value") if preset_value else arg.default

        # 有効チェックボックス（常に表示）
        updates.append(
            gr.update(
                visible=True, value=enabled_value, elem_id=f"opt-arg-{arg_idx}-enabled"
            )
        )

        # 各UIコンポーネントの表示/非表示
        if ui_type == UIComponentType.NUMBER_INPUT:
            # 数値入力
            value = (
                actual_value
                if actual_value is not None
                else (arg.default if arg.default is not None else 0)
            )
            updates.append(
                gr.update(
                    visible=True,
                    label=f"--{arg.name}",
                    value=value,
                    info=arg.display_name,  # infoでツールチップとして表示
                    elem_id=f"opt-arg-{arg_idx}-number",
                )
            )
            updates.extend(
                [
                    gr.update(visible=False),  # text
                    gr.update(visible=False, value=None),  # checkbox - valueをリセット
                    gr.update(visible=False),  # dropdown
                    gr.update(visible=False),  # tuple1
                    gr.update(visible=False),  # tuple2
                ]
            )

        elif ui_type == UIComponentType.TEXT_INPUT:
            # テキスト入力（betasなど）
            updates.append(gr.update(visible=False))  # number
            value = (
                str(actual_value)
                if actual_value is not None
                else (str(arg.default) if arg.default is not None else "")
            )
            text_update_args = {
                "visible": True,
                "label": f"--{arg.name}",
                "value": value,
                "info": arg.display_name,  # infoでツールチップとして表示
                "elem_id": f"opt-arg-{arg_idx}-text",
            }
            # Textboxの場合のみplaceholderを追加
            placeholder_value = getattr(arg, "placeholder", getattr(arg, "description", ""))
            if placeholder_value:
                text_update_args["placeholder"] = placeholder_value
            updates.append(gr.update(**text_update_args))
            updates.extend(
                [
                    gr.update(visible=False, value=None),  # checkbox - valueをリセット
                    gr.update(visible=False),  # dropdown
                    gr.update(visible=False),  # tuple1
                    gr.update(visible=False),  # tuple2
                ]
            )

        # SCIENTIFIC_INPUTはNUMBER_INPUTに統合されたため削除
        # CHECKBOXはDROPDOWNに統合されたため削除

        elif ui_type == UIComponentType.DROPDOWN:
            # 選択肢がある場合のみドロップダウン
            updates.extend(
                [
                    gr.update(visible=False),  # number
                    gr.update(visible=False),  # text
                    gr.update(visible=False, value=None),  # checkbox - valueをリセット
                ]
            )
            # Dropdownの値を文字列に変換
            default_value = arg.default
            if default_value is not None:
                default_value = str(default_value)
            elif arg.choices:
                default_value = arg.choices[0]
            else:
                default_value = None
                
            updates.append(
                gr.update(
                    visible=True,
                    label=f"--{arg.name}",
                    choices=arg.choices or [],
                    value=default_value,
                    info=arg.display_name,  # infoでツールチップとして表示
                    elem_id=f"opt-arg-{arg_idx}-dropdown",
                )
            )
            updates.extend(
                [
                    gr.update(visible=False),  # tuple1
                    gr.update(visible=False),  # tuple2
                ]
            )

        # TUPLE_INPUTは未使用のため削除

        else:
            # デフォルト（テキスト入力）
            updates.append(gr.update(visible=False))  # number
            updates.append(
                gr.update(
                    visible=True,
                    label=f"--{arg.name}",
                    value=str(arg.default) if arg.default is not None else "",
                    info=arg.display_name,  # infoでツールチップとして表示
                    elem_id=f"opt-arg-{arg_idx}-text",
                )
            )
            updates.extend(
                [
                    gr.update(visible=False, value=None),  # checkbox - valueをリセット
                    gr.update(visible=False),  # dropdown
                    gr.update(visible=False),  # tuple1
                    gr.update(visible=False),  # tuple2
                ]
            )

        return updates

    def get_optimizer_description(self, optimizer_type: str) -> str:
        """オプティマイザーの説明を取得"""
        if not optimizer_type or optimizer_type == "Custom...":
            return ""

        optimizer_config = self.template_manager.get_optimizer(optimizer_type)
        if optimizer_config:
            return (
                f"### {optimizer_config.display_name}\n\n{optimizer_config.description}"
            )
        return ""

    def collect_optimizer_args(self, *args) -> Dict[str, Any]:
        """オプティマイザー引数を収集

        Args:
            *args: UIコンポーネントの値（順序はcreate_arguments_containerと同じ）

        Returns:
            引数名と値の辞書
        """
        if not self.current_optimizer:
            return {}

        optimizer_config = self.template_manager.get_optimizer(self.current_optimizer)
        if not optimizer_config:
            return {}

        collected_args = {}
        components_per_arg = 7  # 各引数につき7個のコンポーネント

        for i, arg in enumerate(optimizer_config.arguments):
            base_idx = i * components_per_arg

            if base_idx >= len(args):
                break

            # 有効チェック
            enabled = args[base_idx] if base_idx < len(args) else False
            if not enabled:
                continue

            # UIタイプに応じて値を取得
            ui_type = arg.get_ui_component_type()

            if ui_type == UIComponentType.NUMBER_INPUT:
                value = args[base_idx + 1] if base_idx + 1 < len(args) else None
            elif ui_type == UIComponentType.DROPDOWN:
                value = args[base_idx + 4] if base_idx + 4 < len(args) else None
            elif (
                ui_type == UIComponentType.TEXT_INPUT or ui_type == UIComponentType.TEXT
            ):
                # テキスト入力
                value = args[base_idx + 2] if base_idx + 2 < len(args) else ""
            else:
                # その他（デフォルト）
                value = args[base_idx + 2] if base_idx + 2 < len(args) else ""

            if value is not None and value != "":
                collected_args[arg.name] = value

        return collected_args

    def apply_preset_values(
        self, optimizer_type: str, args_values: Dict[str, Any]
    ) -> List[Any]:
        """プリセット値を適用

        Args:
            optimizer_type: オプティマイザー名
            args_values: 引数値の辞書

        Returns:
            UIコンポーネントの更新リスト
        """
        # まずUIを更新
        updates = self.update_optimizer_ui(optimizer_type)

        if not optimizer_type or optimizer_type == "Custom...":
            return updates

        optimizer_config = self.template_manager.get_optimizer(optimizer_type)
        if not optimizer_config:
            return updates

        # 値を適用（updatesの既存値を上書き）
        components_per_arg = 7
        for i, arg in enumerate(optimizer_config.arguments):
            if arg.name in args_values:
                base_idx = 1 + i * components_per_arg  # container分の+1
                value = args_values[arg.name]

                # 有効フラグをTrueに
                updates[base_idx] = gr.update(visible=True, value=True)

                ui_type = arg.get_ui_component_type()
                if ui_type == UIComponentType.NUMBER_INPUT:
                    updates[base_idx + 1] = gr.update(
                        visible=True, value=float(value) if value is not None else 0
                    )
                elif ui_type == UIComponentType.DROPDOWN:
                    updates[base_idx + 4] = gr.update(visible=True, value=value)
                elif (
                    ui_type == UIComponentType.TEXT_INPUT
                    or ui_type == UIComponentType.TEXT
                ):
                    updates[base_idx + 2] = gr.update(visible=True, value=str(value))
                # SCIENTIFIC_INPUT, CHECKBOX, TUPLE_INPUTは削除済み

        return updates
