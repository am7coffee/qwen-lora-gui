"""
オプティマイザーテンプレート管理システム v2
テンプレート駆動型のオプティマイザー管理
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class UIComponentType(Enum):
    """UIコンポーネントタイプ"""

    NUMBER_INPUT = "number_input"
    # TUPLE_INPUT = "tuple_input"  # 未使用のため削除
    # CHECKBOX = "checkbox"  # dropdownに統合
    DROPDOWN = "dropdown"
    # SCIENTIFIC_INPUT = "scientific_input"  # number_inputに統合
    TEXT = "text"
    TEXT_INPUT = "text_input"


@dataclass
class ArgumentConfig:
    """オプティマイザー引数設定"""

    name: str
    display_name: str
    type: str  # "float", "int", "bool", "str", "tuple_float", "choice"
    default: Any
    required: bool
    description: str
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    ui_component: Optional[str] = None
    labels: Optional[List[str]] = None
    step: Optional[Union[float, str]] = None
    precision: Optional[int] = None

    def get_ui_component_type(self) -> UIComponentType:
        """UIコンポーネントタイプを取得"""
        if self.ui_component:
            # 旧タイプから新タイプへの自動変換
            if self.ui_component == "checkbox":
                return UIComponentType.DROPDOWN
            elif self.ui_component == "scientific_input":
                return UIComponentType.NUMBER_INPUT
            elif self.ui_component == "tuple_input":
                return UIComponentType.TEXT_INPUT  # タプルは文字列として扱う

            try:
                return UIComponentType(self.ui_component)
            except ValueError:
                pass

        # デフォルトマッピング（新設計に基づく）
        if self.type in ["bool", "choice"]:
            return UIComponentType.DROPDOWN
        elif self.type == "tuple_float":
            return UIComponentType.TEXT_INPUT  # タプルは文字列として扱う
        elif self.ui_component == "text_input":
            return UIComponentType.TEXT_INPUT
        elif self.type in ["float", "int"]:
            return UIComponentType.NUMBER_INPUT
        elif self.type in ["string", "str"]:
            return UIComponentType.TEXT_INPUT
        else:
            return UIComponentType.TEXT

    def format_value_for_command(self, value: Any) -> str:
        """コマンドライン用に値をフォーマット"""
        if self.type == "tuple_float":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return f"({value[0]}, {value[1]})"
            return str(value)
        elif self.type == "bool":
            # bool型は廃止されたが、後方互換性のため処理を残す
            return "true" if value else "false"
        elif self.type == "choice":
            # choice型の値はそのまま文字列として返す
            return str(value)
        else:
            return str(value)


@dataclass
class OptimizerConfig:
    """オプティマイザー設定"""

    name: str
    display_name: str
    command_value: str
    description: str
    category: str
    arguments: List[ArgumentConfig]

    def get_argument(self, name: str) -> Optional[ArgumentConfig]:
        """引数名から設定を取得"""
        for arg in self.arguments:
            if arg.name == name:
                return arg
        return None


class OptimizerTemplateManager:
    """オプティマイザーテンプレート管理クラス"""

    def __init__(self, template_path: Optional[str] = None):
        """
        Args:
            template_path: テンプレートファイルのパス
        """
        if template_path is None:
            # デフォルトパスを使用
            template_path = "data/config/templates/optimizer_templates_v2.json"

        self.template_path = Path(template_path)
        self.config: Dict[str, Any] = {}
        self.optimizers: Dict[str, OptimizerConfig] = {}
        self._load_and_parse()

    def _load_and_parse(self) -> None:
        """テンプレートを読み込んで解析"""
        try:
            self.config = self._load_template()
            self.optimizers = self._parse_optimizers()
        except Exception as e:
            print(f"テンプレート読み込みエラー: {e}")
            self.config = self._get_fallback_config()
            self.optimizers = self._parse_optimizers()

    def _load_template(self) -> Dict[str, Any]:
        """テンプレートファイルを読み込む"""
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"テンプレートファイルが見つかりません: {self.template_path}"
            )

        with open(self.template_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_fallback_config(self) -> Dict[str, Any]:
        """フォールバック設定を取得"""
        return {
            "version": "2.0",
            "optimizers": {
                "AdamW8bit": {
                    "display_name": "AdamW8bit (メモリ効率)",
                    "command_value": "bitsandbytes.optim.AdamW8bit",
                    "description": "8ビット量子化による省メモリ版AdamW",
                    "category": "quantized",
                    "arguments": [
                        {
                            "name": "betas",
                            "display_name": "モーメンタム係数",
                            "type": "tuple_float",
                            "default": [0.9, 0.999],
                            "required": False,
                            "description": "モーメント推定の指数減衰率",
                            "ui_component": "tuple_input",
                            "labels": ["β1", "β2"],
                        },
                        {
                            "name": "eps",
                            "display_name": "イプシロン",
                            "type": "float",
                            "default": 1e-8,
                            "required": False,
                            "description": "数値安定性のための定数",
                            "ui_component": "scientific_input",
                        },
                        {
                            "name": "weight_decay",
                            "display_name": "Weight Decay",
                            "type": "float",
                            "default": 0.01,
                            "required": False,
                            "description": "L2正則化の強度",
                            "ui_component": "number_input",
                        },
                    ],
                }
            },
        }

    def _parse_optimizers(self) -> Dict[str, OptimizerConfig]:
        """オプティマイザー設定をパース"""
        optimizers = {}

        for opt_name, opt_data in self.config.get("optimizers", {}).items():
            arguments = []
            for arg_data in opt_data.get("arguments", []):
                arg_config = ArgumentConfig(
                    name=arg_data["name"],
                    display_name=arg_data.get("display_name", arg_data["name"]),
                    type=arg_data.get("type", "str"),
                    default=arg_data.get("default"),
                    required=arg_data.get("required", False),
                    description=arg_data.get("description", ""),
                    min_value=arg_data.get("min"),
                    max_value=arg_data.get("max"),
                    choices=arg_data.get("choices"),
                    ui_component=arg_data.get("ui_component"),
                    labels=arg_data.get("labels"),
                    step=arg_data.get("step"),
                    precision=arg_data.get("precision"),
                )
                arguments.append(arg_config)

            optimizer = OptimizerConfig(
                name=opt_name,
                display_name=opt_data.get("display_name", opt_name),
                command_value=opt_data.get("command_value", opt_name),
                description=opt_data.get("description", ""),
                category=opt_data.get("category", "standard"),
                arguments=arguments,
            )
            optimizers[opt_name] = optimizer

        return optimizers

    def get_optimizer(self, name: str) -> Optional[OptimizerConfig]:
        """オプティマイザー設定を取得

        Args:
            name: オプティマイザー名またはcommand_value

        Returns:
            オプティマイザー設定、見つからない場合はNone
        """
        # まずキー名で検索
        if name in self.optimizers:
            return self.optimizers[name]

        # command_valueで検索
        for opt_name, opt_config in self.optimizers.items():
            if opt_config.command_value == name:
                return opt_config

        return None

    def get_optimizer_list(self) -> List[Tuple[str, str]]:
        """オプティマイザーリストを取得（Gradio形式: value, label）"""
        return [(name, opt.display_name) for name, opt in self.optimizers.items()]

    def get_optimizer_choices(self) -> List[str]:
        """オプティマイザーの選択肢リストを取得（command_value使用）"""
        choices = []
        for name, opt in self.optimizers.items():
            if name == "Custom...":
                choices.append(name)
            else:
                # command_valueを使用（なければキー名をフォールバック）
                choices.append(opt.command_value if opt.command_value else name)
        return choices

    def get_optimizer_names(self) -> List[str]:
        """オプティマイザー名のリストを取得"""
        return list(self.optimizers.keys())

    def get_optimizer_display_names(self) -> Dict[str, str]:
        """オプティマイザー名と表示名のマッピングを取得"""
        return {name: opt.display_name for name, opt in self.optimizers.items()}

    def validate_arguments(
        self, optimizer_name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """引数の妥当性を検証

        Args:
            optimizer_name: オプティマイザー名
            arguments: 検証する引数

        Returns:
            (有効性, エラーメッセージリスト)
        """
        errors = []
        optimizer = self.get_optimizer(optimizer_name)

        if not optimizer:
            return False, [f"オプティマイザー '{optimizer_name}' が見つかりません"]

        for arg_config in optimizer.arguments:
            if arg_config.required and arg_config.name not in arguments:
                errors.append(f"必須引数 '{arg_config.name}' が指定されていません")
                continue

            if arg_config.name in arguments:
                value = arguments[arg_config.name]

                # 型チェック
                if arg_config.type == "float":
                    try:
                        float_val = float(value)
                        if (
                            arg_config.min_value is not None
                            and float_val < arg_config.min_value
                        ):
                            errors.append(
                                f"{arg_config.name}: 値が最小値 {arg_config.min_value} より小さいです"
                            )
                        if (
                            arg_config.max_value is not None
                            and float_val > arg_config.max_value
                        ):
                            errors.append(
                                f"{arg_config.name}: 値が最大値 {arg_config.max_value} より大きいです"
                            )
                    except (TypeError, ValueError):
                        errors.append(f"{arg_config.name}: float型に変換できません")

                elif arg_config.type == "int":
                    try:
                        int(value)
                    except (TypeError, ValueError):
                        errors.append(f"{arg_config.name}: int型に変換できません")

                elif arg_config.type == "choice" and arg_config.choices:
                    if value not in arg_config.choices:
                        errors.append(
                            f"{arg_config.name}: 値 '{value}' は選択肢にありません"
                        )

        return len(errors) == 0, errors

    def format_arguments_for_command(
        self, optimizer_name: str, arguments: Dict[str, Any]
    ) -> List[str]:
        """コマンドライン用に引数をフォーマット

        Args:
            optimizer_name: オプティマイザー名
            arguments: 引数辞書

        Returns:
            ["--optimizer_args", "key=value", ...] 形式のリスト
        """
        optimizer = self.get_optimizer(optimizer_name)
        if not optimizer:
            return []

        formatted = []
        for arg_name, value in arguments.items():
            arg_config = optimizer.get_argument(arg_name)
            if arg_config:
                formatted_value = arg_config.format_value_for_command(value)
                formatted.extend(["--optimizer_args", f"{arg_name}={formatted_value}"])

        return formatted
