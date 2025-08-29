"""
OptimizerArgs専用の管理クラス
プリセット機能でoptimizer_argsの保存・復元を正しく処理するための専用マネージャー
"""

from typing import Any, Dict, List, Tuple
from .optimizer_args_registry import OptimizerArgsRegistry
from .optimizer_template_manager import (
    OptimizerTemplateManager,
    ArgumentConfig,
)


class OptimizerArgsManager:
    """optimizer_args専用の管理クラス"""

    def __init__(
        self,
        template_manager: OptimizerTemplateManager,
        args_registry: OptimizerArgsRegistry,
    ):
        """
        Args:
            template_manager: OptimizerTemplateManagerインスタンス
            args_registry: OptimizerArgsRegistryインスタンス
        """
        self.template_manager = template_manager
        self.args_registry = args_registry

    def get_template_for_optimizer(self, optimizer_type: str) -> List[ArgumentConfig]:
        """指定されたオプティマイザーのテンプレートを取得

        Args:
            optimizer_type: オプティマイザータイプ

        Returns:
            ArgumentConfigのリスト
        """
        config = self.template_manager.get_optimizer(optimizer_type)
        if config:
            return config.arguments
        return []

    def create_mapping_for_optimizer(self, optimizer_type: str) -> Dict[str, int]:
        """オプティマイザー用のarg_name→インデックスマッピングを作成

        Args:
            optimizer_type: オプティマイザータイプ

        Returns:
            arg_name → インデックスのマッピング辞書
        """
        template = self.get_template_for_optimizer(optimizer_type)
        mapping = {}

        for idx, arg_config in enumerate(template):
            mapping[arg_config.name] = idx

        return mapping

    def convert_preset_to_ui_values(
        self, optimizer_type: str, preset_args: Dict[str, Any]
    ) -> List[Tuple[bool, Any]]:
        """プリセットのoptimizer_argsをUI用の値リストに変換

        Args:
            optimizer_type: オプティマイザータイプ
            preset_args: プリセットから読み込んだoptimizer_args

        Returns:
            [(enabled, value), ...]形式のリスト
        """
        template = self.get_template_for_optimizer(optimizer_type)
        ui_values = []

        for arg_config in template:
            arg_name = arg_config.name
            if arg_name in preset_args:
                # プリセットに値がある場合
                enabled = True
                value = preset_args[arg_name]

                # choice型の特別処理
                if arg_config.type == "choice":
                    # 文字列として扱う
                    value = str(value)
            else:
                # プリセットに値がない場合はデフォルト値を使用
                enabled = False
                value = arg_config.default

            ui_values.append((enabled, value))

        return ui_values

    def convert_ui_to_preset_values(
        self, optimizer_type: str, ui_values: List[Tuple[bool, Any]]
    ) -> Dict[str, Any]:
        """UI値をプリセット保存用のoptimizer_args形式に変換

        Args:
            optimizer_type: オプティマイザータイプ
            ui_values: UIから収集した値のリスト

        Returns:
            {arg_name: value}形式の辞書
        """
        template = self.get_template_for_optimizer(optimizer_type)
        preset_args = {}

        for idx, (enabled, value) in enumerate(ui_values):
            if enabled and idx < len(template):
                arg_config = template[idx]
                preset_args[arg_config.name] = value

        return preset_args

    def sync_registry_with_template(self, optimizer_type: str) -> None:
        """レジストリをテンプレートと同期

        Args:
            optimizer_type: オプティマイザータイプ
        """
        # テンプレートを取得してレジストリに登録
        template = self.get_template_for_optimizer(optimizer_type)
        self.args_registry.register_args(optimizer_type, template)

    def validate_optimizer_args(
        self, optimizer_type: str, args: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """optimizer_argsの妥当性を検証

        Args:
            optimizer_type: オプティマイザータイプ
            args: 検証する引数辞書

        Returns:
            (有効フラグ, エラーメッセージリスト)
        """
        errors = []
        template = self.get_template_for_optimizer(optimizer_type)

        # テンプレートに定義された引数名を取得
        valid_arg_names = {arg.name for arg in template}

        # 不明な引数をチェック
        for arg_name in args.keys():
            if arg_name not in valid_arg_names:
                errors.append(f"Unknown argument: {arg_name}")

        # 必須引数をチェック
        for arg_config in template:
            if arg_config.required and arg_config.name not in args:
                errors.append(f"Required argument missing: {arg_config.name}")

        # 型と範囲をチェック
        for arg_config in template:
            if arg_config.name in args:
                value = args[arg_config.name]

                # 型チェック
                if arg_config.type == "float":
                    try:
                        float_val = float(value)
                        # 範囲チェック
                        if (
                            arg_config.min_value is not None
                            and float_val < arg_config.min_value
                        ):
                            errors.append(
                                f"{arg_config.name}: Value {value} is below minimum {arg_config.min_value}"
                            )
                        if (
                            arg_config.max_value is not None
                            and float_val > arg_config.max_value
                        ):
                            errors.append(
                                f"{arg_config.name}: Value {value} is above maximum {arg_config.max_value}"
                            )
                    except (ValueError, TypeError):
                        errors.append(
                            f"{arg_config.name}: Invalid float value: {value}"
                        )

                elif arg_config.type == "choice":
                    if arg_config.choices and str(value) not in [
                        str(c) for c in arg_config.choices
                    ]:
                        errors.append(f"{arg_config.name}: Invalid choice: {value}")

        return len(errors) == 0, errors

    def get_default_args(self, optimizer_type: str) -> Dict[str, Any]:
        """指定されたオプティマイザーのデフォルト引数を取得

        Args:
            optimizer_type: オプティマイザータイプ

        Returns:
            デフォルト引数の辞書
        """
        template = self.get_template_for_optimizer(optimizer_type)
        default_args = {}

        for arg_config in template:
            if not arg_config.required:  # オプション引数のみ
                default_args[arg_config.name] = arg_config.default

        return default_args
